import base64
import json
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
        print(
            f"[ocr] sending {len(payload)} bytes to Yandex OCR "
            f"(mime={resolved_mime_type}, model={model})"
        )
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
        status_code = getattr(resp, "status_code", "<unknown>")
        print(f"[ocr] http status: {status_code}")
        try:
            payload_json = resp.json()
        except Exception:
            payload_json = None

        if getattr(resp, "status_code", 200) >= 400:
            response_text = getattr(resp, "text", "")
            print(f"[ocr] error body: {response_text[:500] or '<empty>'}")
            resp.raise_for_status()

        resp.raise_for_status()

        if payload_json is None:
            raise RuntimeError("OCR response is not valid JSON")

        annotation = self._get_text_annotation(payload_json)
        text = self._extract_text(annotation)
        print(f"[ocr] recognized {len(text)} chars")
        if not text:
            preview = json.dumps(payload_json, ensure_ascii=False)[:1000]
            print(f"[ocr] empty OCR response: {preview}")
        return text

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

    def _get_text_annotation(self, payload_json: dict) -> dict:
        if "textAnnotation" in payload_json:
            return payload_json["textAnnotation"]
        return payload_json.get("result", {}).get("textAnnotation", {})

    def _extract_text(self, annotation: dict) -> str:
        full_text = annotation.get("fullText", "").strip()
        if full_text:
            return full_text

        blocks = annotation.get("blocks", [])
        block_texts: list[str] = []
        for block in blocks:
            line_texts: list[str] = []
            for line in block.get("lines", []):
                line_text = str(line.get("text", "")).strip()
                if not line_text:
                    words = [
                        str(word.get("text", "")).strip()
                        for word in line.get("words", [])
                        if str(word.get("text", "")).strip()
                    ]
                    line_text = " ".join(words)
                if line_text:
                    line_texts.append(line_text)
            if line_texts:
                block_texts.append("\n".join(line_texts))
        return "\n\n".join(block_texts).strip()


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
