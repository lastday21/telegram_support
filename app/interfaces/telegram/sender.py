import json
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO, Union

import requests

from app.settings import get_settings

DEFAULT_CAPTION = ""
MAX_MESSAGE_LENGTH = 4096
MIN_MEDIA_GROUP_SIZE = 2
MAX_MEDIA_GROUP_SIZE = 10


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > limit:
        newline_at = remaining.rfind("\n", 0, limit + 1)
        space_at = remaining.rfind(" ", 0, limit + 1)
        split_at = max(newline_at, space_at)
        if split_at < limit // 2:
            split_at = limit
        chunk = remaining[:split_at].rstrip()
        chunks.append(chunk or remaining[:limit])
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


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
        self,
        photo: Union[str, Path, bytes, BinaryIO],
        caption: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        data = {
            "chat_id": chat_id or self.chat_id,
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

    def send_media_group(
        self,
        photos: Sequence[bytes],
        caption: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        if not MIN_MEDIA_GROUP_SIZE <= len(photos) <= MAX_MEDIA_GROUP_SIZE:
            raise ValueError("Альбом должен содержать от 2 до 10 снимков")

        files = {}
        media = []
        for index, photo in enumerate(photos, start=1):
            field_name = f"photo_{index}"
            files[field_name] = (
                f"shot-{index}.png",
                photo,
                "image/png",
            )
            item = {
                "type": "photo",
                "media": f"attach://{field_name}",
            }
            if index == 1 and caption:
                item["caption"] = caption
            media.append(item)

        resp = self.http_post(
            self._build_url("sendMediaGroup"),
            data={
                "chat_id": chat_id or self.chat_id,
                "media": json.dumps(media, ensure_ascii=False),
            },
            files=files,
            timeout=self.timeout,
        )
        resp.raise_for_status()

    def send_message(self, text: str, chat_id: str | None = None) -> None:
        for chunk in split_message(text):
            resp = self.http_post(
                self._build_url("sendMessage"),
                data={"chat_id": chat_id or self.chat_id, "text": chunk},
                timeout=self.timeout,
            )
            resp.raise_for_status()


def build_sender() -> TelegramSender:
    settings = get_settings()
    return TelegramSender(settings.tg_bot_token, settings.tg_chat_id)


def send_photo(
    photo: Union[str, Path, bytes, BinaryIO],
    caption: str | None = None,
    chat_id: str | None = None,
) -> None:
    build_sender().send_photo(photo, caption=caption, chat_id=chat_id)


def send_media_group(
    photos: Sequence[bytes],
    caption: str | None = None,
    chat_id: str | None = None,
) -> None:
    build_sender().send_media_group(photos, caption=caption, chat_id=chat_id)


def send_message(text: str, chat_id: str | None = None) -> None:
    build_sender().send_message(text, chat_id=chat_id)
