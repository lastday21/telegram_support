from __future__ import annotations

import logging
import secrets
import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.infra.yandex_gpt import solve_image, solve_text
from app.infra.yandex_stt import transcribe
from app.interfaces.telegram.sender import send_message, send_photo
from app.settings import get_settings

logger = logging.getLogger(__name__)
MAX_AUDIO_SIZE = 20 * 1024 * 1024
MAX_IMAGE_SIZE = 10 * 1024 * 1024


class TextRequest(BaseModel):
    text: str = Field(min_length=3, max_length=50_000)


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)


def _read_limited(upload: UploadFile, limit: int) -> bytes:
    payload = upload.file.read(limit + 1)
    if len(payload) > limit:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    if not payload:
        raise HTTPException(status_code=400, detail="Получен пустой файл")
    return payload


def create_app(
    access_token: str | None = None,
    solve_text_fn: Callable[[str], str] = solve_text,
    solve_image_fn: Callable[[bytes, str], str] = solve_image,
    transcribe_fn: Callable[[Path], str] = transcribe,
    send_message_fn: Callable[[str], None] = send_message,
    send_photo_fn: Callable[[bytes, str | None], None] = send_photo,
) -> FastAPI:
    application = FastAPI(title="SmartHelper", docs_url=None, redoc_url=None)

    def require_access(request: Request) -> None:
        expected_token = access_token or get_settings().app_access_token
        authorization = request.headers.get("Authorization", "")
        scheme, _, supplied_token = authorization.partition(" ")
        is_valid = scheme.lower() == "bearer" and secrets.compare_digest(
            supplied_token, expected_token
        )
        if not is_valid:
            raise HTTPException(status_code=401, detail="Доступ запрещён")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/v1/ping", dependencies=[Depends(require_access)])
    def protected_ping() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/v1/text", dependencies=[Depends(require_access)])
    def text_answer(request: TextRequest) -> dict[str, str]:
        return {"answer": solve_text_fn(request.text)}

    @application.post("/v1/image", dependencies=[Depends(require_access)])
    def image_answer(
        image: UploadFile = File(...), prompt: str = Form(...)
    ) -> dict[str, str]:
        image_bytes = _read_limited(image, MAX_IMAGE_SIZE)
        return {"answer": solve_image_fn(image_bytes, prompt)}

    @application.post("/v1/transcribe", dependencies=[Depends(require_access)])
    def audio_text(audio: UploadFile = File(...)) -> dict[str, str]:
        audio_bytes = _read_limited(audio, MAX_AUDIO_SIZE)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = Path(temp_file.name)
            return {"text": transcribe_fn(temp_path)}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Не удалось распознать аудио")
            raise HTTPException(
                status_code=502, detail="Не удалось распознать аудио"
            ) from exc
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @application.post("/v1/telegram/message", dependencies=[Depends(require_access)])
    def telegram_message(request: MessageRequest) -> dict[str, bool]:
        send_message_fn(request.text)
        return {"sent": True}

    @application.post("/v1/telegram/photo", dependencies=[Depends(require_access)])
    def telegram_photo(
        photo: UploadFile = File(...), caption: str = Form("")
    ) -> dict[str, bool]:
        photo_bytes = _read_limited(photo, MAX_IMAGE_SIZE)
        send_photo_fn(photo_bytes, caption or None)
        return {"sent": True}

    return application


app = create_app()
