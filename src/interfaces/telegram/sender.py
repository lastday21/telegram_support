from pathlib import Path
from typing import BinaryIO, Union

import requests

from src.settings import get_settings

DEFAULT_CAPTION = ""


class TelegramSender:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        http_post=requests.post,
        timeout: int = 30,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.http_post = http_post
        self.timeout = timeout

    def _build_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def send_photo(
        self, photo: Union[str, Path, bytes, BinaryIO], caption: str | None = None
    ) -> None:
        data = {
            "chat_id": self.chat_id,
            "caption": caption if caption is not None else DEFAULT_CAPTION,
        }
        if isinstance(photo, bytes):
            files: dict[str, tuple[str, bytes]] = {"photo": ("shot.png", photo)}
        elif isinstance(photo, (str, Path)):
            with open(photo, "rb") as fh:
                files = {"photo": ("shot.png", fh.read())}
        else:
            files = {"photo": ("shot.png", photo.read())}

        resp = self.http_post(
            self._build_url("sendPhoto"),
            data=data,
            files=files,
            timeout=self.timeout,
        )
        resp.raise_for_status()

    def send_message(self, text: str) -> None:
        resp = self.http_post(
            self._build_url("sendMessage"),
            data={"chat_id": self.chat_id, "text": text},
            timeout=self.timeout,
        )
        resp.raise_for_status()


def build_sender() -> TelegramSender:
    settings = get_settings()
    return TelegramSender(settings.tg_bot_token, settings.tg_chat_id)


def send_photo(
    photo: Union[str, Path, bytes, BinaryIO], caption: str | None = None
) -> None:
    build_sender().send_photo(photo, caption=caption)


def send_message(text: str) -> None:
    build_sender().send_message(text)
