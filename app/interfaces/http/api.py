from __future__ import annotations

import logging
import secrets
import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.domain.yandex_queue import (
    YandexQueueFullError,
    YandexQueueTimeoutError,
    YandexRequestQueue,
    build_yandex_queue,
)
from app.domain.request_guard import (
    RequestGuard,
    RequestProtectionMiddleware,
    build_request_guard,
)
from app.infra.readiness import ExternalReadinessChecker, build_readiness_checker
from app.infra.yandex_resilience import YandexCircuitOpenError
from app.infra.yandex_gpt import solve_image, solve_text, solve_vision_image
from app.infra.yandex_ocr import recognize_text
from app.infra.yandex_stt import transcribe
from app.interfaces.telegram.sender import send_media_group, send_message, send_photo
from app.settings import SUPPORTED_YC_MODELS, get_settings

logger = logging.getLogger(__name__)
MAX_AUDIO_SIZE = 20 * 1024 * 1024
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_CONTEXT_TEXT_SIZE = 120_000


class TextRequest(BaseModel):
    text: str = Field(min_length=3, max_length=50_000)
    model: str | None = None


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50_000)
    chat_id: str | None = None


def _read_limited(upload: UploadFile, limit: int) -> bytes:
    payload = upload.file.read(limit + 1)
    if len(payload) > limit:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    if not payload:
        raise HTTPException(status_code=400, detail="Получен пустой файл")
    return payload


def create_app(
    access_token: str | None = None,
    solve_text_fn: Callable[[str, str | None], str] = solve_text,
    solve_image_fn: Callable[[bytes, str, str, str | None], str] = solve_image,
    solve_vision_image_fn: Callable[[bytes, str], str] = solve_vision_image,
    recognize_image_fn: Callable[[bytes], str] = recognize_text,
    transcribe_fn: Callable[[Path], str] = transcribe,
    send_message_fn: Callable[[str, str | None], None] = send_message,
    send_photo_fn: Callable[[bytes, str | None, str | None], None] = send_photo,
    send_media_group_fn: Callable[
        [list[bytes], str | None, str | None], None
    ] = send_media_group,
    yandex_queue: YandexRequestQueue | None = None,
    readiness_checker: ExternalReadinessChecker | None = None,
    request_guard: RequestGuard | None = None,
) -> FastAPI:
    application = FastAPI(title="SmartHelper", docs_url=None, redoc_url=None)
    request_queue = yandex_queue or build_yandex_queue()
    service_checker = readiness_checker or build_readiness_checker()
    guard = request_guard or build_request_guard()
    application.add_middleware(RequestProtectionMiddleware, guard=guard)

    def require_access(request: Request) -> None:
        client_key = guard.client_key(request.scope)
        blocked_for = guard.auth_block_remaining(client_key)
        if blocked_for is not None:
            raise HTTPException(
                status_code=429,
                detail="Слишком много ошибок доступа, повторите позже",
                headers={"Retry-After": str(blocked_for)},
            )
        expected_token = access_token or get_settings().app_access_token
        authorization = request.headers.get("Authorization", "")
        scheme, _, supplied_token = authorization.partition(" ")
        is_valid = scheme.lower() == "bearer" and secrets.compare_digest(
            supplied_token, expected_token
        )
        if not is_valid:
            blocked_for = guard.record_auth_failure(client_key)
            if blocked_for is not None:
                raise HTTPException(
                    status_code=429,
                    detail="Слишком много ошибок доступа, повторите позже",
                    headers={"Retry-After": str(blocked_for)},
                )
            raise HTTPException(status_code=401, detail="Доступ запрещён")
        guard.record_auth_success(client_key)

    @application.get("/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready")
    def ready() -> JSONResponse:
        return readiness_response()

    @application.get("/health")
    def health() -> JSONResponse:
        return readiness_response()

    @application.get("/v1/ping", dependencies=[Depends(require_access)])
    def protected_ping() -> JSONResponse:
        return readiness_response()

    def readiness_response() -> JSONResponse:
        report = service_checker.check()
        content = {
            "status": "ok" if report.ready else "unavailable",
            "checks": report.checks,
            "queue": request_queue.stats().as_dict(),
        }
        return JSONResponse(content=content, status_code=200 if report.ready else 503)

    def execute_yandex(operation, *args):
        try:
            return request_queue.execute(operation, *args)
        except YandexQueueFullError as exc:
            raise HTTPException(
                status_code=429,
                detail="Очередь запросов к Яндексу заполнена",
                headers={"Retry-After": "5"},
            ) from exc
        except YandexQueueTimeoutError as exc:
            raise HTTPException(
                status_code=503,
                detail="Сервис Яндекса занят, попробуйте позже",
                headers={"Retry-After": "5"},
            ) from exc
        except YandexCircuitOpenError as exc:
            raise HTTPException(
                status_code=503,
                detail="Яндекс временно недоступен, повторите позже",
                headers={"Retry-After": "30"},
            ) from exc

    def validate_model(model: str | None) -> str | None:
        if model is not None and model not in SUPPORTED_YC_MODELS:
            raise HTTPException(status_code=422, detail="Модель не поддерживается")
        return model

    @application.post("/v1/text", dependencies=[Depends(require_access)])
    def text_answer(request: TextRequest) -> dict[str, str]:
        try:
            answer = execute_yandex(
                solve_text_fn, request.text, validate_model(request.model)
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Не удалось получить текстовый ответ")
            raise HTTPException(
                status_code=502, detail="Не удалось получить ответ от Яндекса"
            ) from exc
        return {"answer": answer}

    @application.post("/v1/image", dependencies=[Depends(require_access)])
    def image_answer(
        image: UploadFile = File(...),
        prompt: str = Form(...),
        context_text: str = Form("", max_length=MAX_CONTEXT_TEXT_SIZE),
        model: str | None = Form(None),
    ) -> dict[str, str]:
        image_bytes = _read_limited(image, MAX_IMAGE_SIZE)
        try:
            answer = execute_yandex(
                solve_image_fn,
                image_bytes,
                prompt,
                context_text,
                validate_model(model),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Не удалось обработать изображение")
            raise HTTPException(
                status_code=502, detail="Не удалось обработать изображение"
            ) from exc
        return {"answer": answer}

    @application.post("/v1/vision", dependencies=[Depends(require_access)])
    def vision_answer(
        image: UploadFile = File(...),
        prompt: str = Form(..., min_length=1, max_length=20_000),
    ) -> dict[str, str]:
        image_bytes = _read_limited(image, MAX_IMAGE_SIZE)
        try:
            answer = execute_yandex(
                solve_vision_image_fn,
                image_bytes,
                prompt,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Не удалось обработать изображение зрительной моделью")
            raise HTTPException(
                status_code=502, detail="Не удалось обработать изображение"
            ) from exc
        return {"answer": answer}

    @application.post("/v1/ocr", dependencies=[Depends(require_access)])
    def image_text(image: UploadFile = File(...)) -> dict[str, str]:
        image_bytes = _read_limited(image, MAX_IMAGE_SIZE)
        try:
            text = execute_yandex(recognize_image_fn, image_bytes)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Не удалось распознать изображение")
            raise HTTPException(
                status_code=502, detail="Не удалось распознать изображение"
            ) from exc
        return {"text": text}

    @application.post("/v1/transcribe", dependencies=[Depends(require_access)])
    def audio_text(audio: UploadFile = File(...)) -> dict[str, str]:
        audio_bytes = _read_limited(audio, MAX_AUDIO_SIZE)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = Path(temp_file.name)
            return {"text": execute_yandex(transcribe_fn, temp_path)}
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
        send_message_fn(request.text, request.chat_id)
        return {"sent": True}

    @application.post("/v1/telegram/photo", dependencies=[Depends(require_access)])
    def telegram_photo(
        photo: UploadFile = File(...),
        caption: str = Form(""),
        chat_id: str = Form(""),
    ) -> dict[str, bool]:
        photo_bytes = _read_limited(photo, MAX_IMAGE_SIZE)
        send_photo_fn(photo_bytes, caption or None, chat_id or None)
        return {"sent": True}

    @application.post(
        "/v1/telegram/media-group",
        dependencies=[Depends(require_access)],
    )
    def telegram_media_group(
        photos: list[UploadFile] = File(...),
        caption: str = Form(""),
        chat_id: str = Form(""),
    ) -> dict[str, bool]:
        if not 2 <= len(photos) <= 10:
            raise HTTPException(
                status_code=422,
                detail="Альбом должен содержать от 2 до 10 снимков",
            )
        photo_bytes = [_read_limited(photo, MAX_IMAGE_SIZE) for photo in photos]
        send_media_group_fn(photo_bytes, caption or None, chat_id or None)
        return {"sent": True}

    return application


app = create_app()
