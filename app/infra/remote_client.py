from __future__ import annotations

import ipaddress
import logging
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlsplit

import requests

from app.settings import DEFAULT_YC_MODEL, ClientSettings, get_client_settings

logger = logging.getLogger(__name__)


def _is_loopback_url(url: str) -> bool:
    hostname = urlsplit(url).hostname
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


class RemoteServiceClient:
    def __init__(
        self,
        server_url: str,
        access_token: str,
        http_post=None,
        http_get=None,
        timeout: int = 120,
        audio_timeout: int = 600,
        ping_timeout: int = 5,
        model: str = DEFAULT_YC_MODEL,
        tg_chat_id: str | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        session = requests.Session()
        if _is_loopback_url(self.server_url):
            session.trust_env = False
            logger.info("Системный прокси отключён для локального сервера")
        self.http_post = http_post or session.post
        self.http_get = http_get or session.get
        self.timeout = timeout
        self.audio_timeout = audio_timeout
        self.ping_timeout = ping_timeout
        self.model = model
        self.tg_chat_id = tg_chat_id
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def set_model(self, model: str) -> None:
        self.model = model

    def _post(self, path: str, **kwargs):
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}))
        timeout = kwargs.pop("timeout", self.timeout)
        response = self.http_post(
            f"{self.server_url}{path}",
            headers=headers,
            timeout=timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def ping(self) -> bool:
        response = self.http_get(
            f"{self.server_url}/v1/ping",
            headers=self.headers,
            timeout=self.ping_timeout,
        )
        response.raise_for_status()
        return response.json().get("status") == "ok"

    def solve_text(self, text: str) -> str:
        response = self._post("/v1/text", json={"text": text, "model": self.model})
        return str(response.json()["answer"])

    def recognize_image(self, image: bytes) -> str:
        response = self._post(
            "/v1/ocr",
            files={"image": ("screenshot.png", image, "image/png")},
        )
        return str(response.json()["text"])

    def solve_image(
        self,
        image: bytes,
        prompt: str,
        context_text: str = "",
    ) -> str:
        data = {
            "prompt": prompt,
            "model": self.model,
        }
        if context_text:
            data["context_text"] = context_text
        response = self._post(
            "/v1/image",
            data=data,
            files={"image": ("screenshot.png", image, "image/png")},
        )
        return str(response.json()["answer"])

    def solve_vision_image(self, image: bytes, prompt: str) -> str:
        response = self._post(
            "/v1/vision",
            data={"prompt": prompt},
            files={"image": ("screenshot.png", image, "image/png")},
        )
        return str(response.json()["answer"])

    def transcribe(self, wav_path: Path) -> str:
        with wav_path.open("rb") as wav_file:
            response = self._post(
                "/v1/transcribe",
                files={"audio": (wav_path.name, wav_file, "audio/wav")},
                timeout=self.audio_timeout,
            )
        return str(response.json()["text"])

    def send_message(self, text: str) -> None:
        payload = {"text": text}
        if self.tg_chat_id:
            payload["chat_id"] = self.tg_chat_id
        self._post("/v1/messengers/message", json=payload)

    def send_photo(self, photo: bytes, caption: str | None = None) -> None:
        data = {"caption": caption or ""}
        if self.tg_chat_id:
            data["chat_id"] = self.tg_chat_id
        self._post(
            "/v1/messengers/photo",
            data=data,
            files={"photo": ("screenshot.png", photo, "image/png")},
        )

    def send_media_group(
        self,
        photos: Sequence[bytes],
        caption: str | None = None,
    ) -> None:
        data = {"caption": caption or ""}
        if self.tg_chat_id:
            data["chat_id"] = self.tg_chat_id
        files = [
            (
                "photos",
                (f"screenshot-{index}.png", photo, "image/png"),
            )
            for index, photo in enumerate(photos, start=1)
        ]
        self._post("/v1/messengers/media-group", data=data, files=files)


def build_remote_client(settings: ClientSettings | None = None) -> RemoteServiceClient:
    selected_settings = settings or get_client_settings()
    return RemoteServiceClient(
        selected_settings.server_url,
        selected_settings.app_access_token,
        model=selected_settings.yc_model,
        tg_chat_id=selected_settings.tg_chat_id,
    )
