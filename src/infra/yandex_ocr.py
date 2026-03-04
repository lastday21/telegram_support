import base64
from pathlib import Path
from typing import Union

import requests

from src.settings import get_settings

OCR_API_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"
DEFAULT_LANGUAGES = ("ru", "en")
DEFAULT_MODEL = "page"
_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
}


class YandexOCRClient:
    def __init__(
        self,
        api_key: str,
        http_post=requests.post,
        timeout: int = 60,
    ) -> None:
        self.http_post = http_post
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
        }

    def recognize_text(
        self,
        image: Union[str, Path, bytes],
        mime_type: str | None = None,
        language_codes: tuple[str, ...] = DEFAULT_LANGUAGES,
        model: str = DEFAULT_MODEL,
    ) -> str:
        payload, resolved_mime_type = self._load_payload(image, mime_type)
        body = {
            "mimeType": resolved_mime_type,
            "languageCodes": list(language_codes),
            "model": model,
            "content": base64.b64encode(payload).decode("ascii"),
        }
        resp = self.http_post(
            OCR_API_URL,
            headers=self.headers,
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()

        return resp.json().get("textAnnotation", {}).get("fullText", "").strip()

    def _load_payload(
        self,
        image: Union[str, Path, bytes],
        mime_type: str | None,
    ) -> tuple[bytes, str]:
        if isinstance(image, bytes):
            return image, mime_type or "image/png"

        path = Path(image)
        resolved_mime_type = mime_type or _MIME_TYPES.get(path.suffix.lower())
        if resolved_mime_type is None:
            raise RuntimeError(
                f"Unsupported image format for OCR: {path.suffix or '<no extension>'}"
            )
        return path.read_bytes(), resolved_mime_type


def build_ocr_client() -> YandexOCRClient:
    settings = get_settings()
    return YandexOCRClient(settings.yc_api_key)


def recognize_text(
    image: Union[str, Path, bytes],
    mime_type: str | None = None,
    language_codes: tuple[str, ...] = DEFAULT_LANGUAGES,
    model: str = DEFAULT_MODEL,
) -> str:
    return build_ocr_client().recognize_text(
        image=image,
        mime_type=mime_type,
        language_codes=language_codes,
        model=model,
    )
