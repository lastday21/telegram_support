from __future__ import annotations

from pathlib import Path

import requests

from app.settings import get_client_settings


class RemoteServiceClient:
    def __init__(
        self,
        server_url: str,
        access_token: str,
        http_post=requests.post,
        timeout: int = 120,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.http_post = http_post
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def _post(self, path: str, **kwargs):
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}))
        response = self.http_post(
            f"{self.server_url}{path}",
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def solve_text(self, text: str) -> str:
        response = self._post("/v1/text", json={"text": text})
        return str(response.json()["answer"])

    def solve_image(self, image: bytes, prompt: str) -> str:
        response = self._post(
            "/v1/image",
            data={"prompt": prompt},
            files={"image": ("screenshot.png", image, "image/png")},
        )
        return str(response.json()["answer"])

    def transcribe(self, wav_path: Path) -> str:
        with wav_path.open("rb") as wav_file:
            response = self._post(
                "/v1/transcribe",
                files={"audio": (wav_path.name, wav_file, "audio/wav")},
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


def build_remote_client() -> RemoteServiceClient:
    settings = get_client_settings()
    return RemoteServiceClient(settings.server_url, settings.app_access_token)
