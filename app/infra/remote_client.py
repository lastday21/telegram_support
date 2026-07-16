from __future__ import annotations

from pathlib import Path

import requests

from app.settings import DEFAULT_YC_MODEL, ClientSettings, get_client_settings


class RemoteServiceClient:
    def __init__(
        self,
        server_url: str,
        access_token: str,
        http_post=requests.post,
        http_get=requests.get,
        timeout: int = 120,
        audio_timeout: int = 600,
        ping_timeout: int = 5,
        model: str = DEFAULT_YC_MODEL,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.http_post = http_post
        self.http_get = http_get
        self.timeout = timeout
        self.audio_timeout = audio_timeout
        self.ping_timeout = ping_timeout
        self.model = model
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

    def solve_image(self, image: bytes, prompt: str) -> str:
        response = self._post(
            "/v1/image",
            data={"prompt": prompt, "model": self.model},
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
        self._post("/v1/telegram/message", json={"text": text})

    def send_photo(self, photo: bytes, caption: str | None = None) -> None:
        self._post(
            "/v1/telegram/photo",
            data={"caption": caption or ""},
            files={"photo": ("screenshot.png", photo, "image/png")},
        )


def build_remote_client(settings: ClientSettings | None = None) -> RemoteServiceClient:
    selected_settings = settings or get_client_settings()
    return RemoteServiceClient(
        selected_settings.server_url,
        selected_settings.app_access_token,
        model=selected_settings.yc_model,
    )
