from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import Any

import requests

from app.interfaces.telegram.sender import split_message
from app.settings import get_settings

VK_API_URL = "https://api.vk.com/method"
MAX_MESSAGE_LENGTH = 4096
MAX_PHOTOS = 10


class VkApiError(RuntimeError):
    pass


class VkSender:
    def __init__(
        self,
        group_token: str,
        user_id: str,
        api_version: str = "5.199",
        http_get: Callable[..., Any] = requests.get,
        http_post: Callable[..., Any] = requests.post,
        timeout: int = 30,
    ) -> None:
        self.group_token = group_token
        self.user_id = user_id
        self.api_version = api_version
        self.http_get = http_get
        self.http_post = http_post
        self.timeout = timeout

    def _call(self, method: str, **params: Any) -> Any:
        response = self.http_post(
            f"{VK_API_URL}/{method}",
            data={
                **params,
                "access_token": self.group_token,
                "v": self.api_version,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise VkApiError("ВКонтакте вернул неожиданный ответ")
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("error_code", "unknown")
            message = error.get("error_msg", "неизвестная ошибка")
            raise VkApiError(f"Ошибка ВКонтакте {code}: {message}")
        if "response" not in payload:
            raise VkApiError("В ответе ВКонтакте нет результата")
        return payload["response"]

    def send_message(self, text: str, user_id: str | None = None) -> None:
        peer_id = user_id or self.user_id
        for chunk in split_message(text, limit=MAX_MESSAGE_LENGTH):
            self._call(
                "messages.send",
                peer_id=peer_id,
                random_id=random.randint(1, 2_147_483_647),
                message=chunk,
            )

    def _upload_photo(self, photo: bytes, peer_id: str) -> str:
        upload_data = self._call(
            "photos.getMessagesUploadServer",
            peer_id=peer_id,
        )
        if not isinstance(upload_data, dict) or not upload_data.get("upload_url"):
            raise VkApiError("ВКонтакте не вернул адрес загрузки фотографии")

        upload_response = self.http_post(
            str(upload_data["upload_url"]),
            files={"photo": ("screenshot.png", photo, "image/png")},
            timeout=self.timeout,
        )
        upload_response.raise_for_status()
        uploaded = upload_response.json()
        if not isinstance(uploaded, dict):
            raise VkApiError("ВКонтакте не подтвердил загрузку фотографии")

        saved = self._call(
            "photos.saveMessagesPhoto",
            photo=uploaded.get("photo", ""),
            server=uploaded.get("server", ""),
            hash=uploaded.get("hash", ""),
        )
        if not isinstance(saved, list) or not saved or not isinstance(saved[0], dict):
            raise VkApiError("ВКонтакте не сохранил фотографию")
        item = saved[0]
        attachment = f"photo{item['owner_id']}_{item['id']}"
        access_key = item.get("access_key")
        if access_key:
            attachment += f"_{access_key}"
        return attachment

    def send_photo(
        self,
        photo: bytes,
        caption: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self.send_media_group([photo], caption=caption, user_id=user_id)

    def send_media_group(
        self,
        photos: Sequence[bytes],
        caption: str | None = None,
        user_id: str | None = None,
    ) -> None:
        if not 1 <= len(photos) <= MAX_PHOTOS:
            raise ValueError("Сообщение должно содержать от 1 до 10 снимков")
        peer_id = user_id or self.user_id
        attachments = [self._upload_photo(photo, peer_id) for photo in photos]
        self._call(
            "messages.send",
            peer_id=peer_id,
            random_id=random.randint(1, 2_147_483_647),
            message=caption or "",
            attachment=",".join(attachments),
        )


def build_sender() -> VkSender:
    settings = get_settings()
    if not settings.vk_group_token or not settings.vk_user_id:
        raise RuntimeError("ВКонтакте не настроен")
    return VkSender(
        group_token=settings.vk_group_token,
        user_id=settings.vk_user_id,
        api_version=settings.vk_api_version,
    )


def send_message(text: str, user_id: str | None = None) -> None:
    build_sender().send_message(text, user_id=user_id)


def send_photo(
    photo: bytes,
    caption: str | None = None,
    user_id: str | None = None,
) -> None:
    build_sender().send_photo(photo, caption=caption, user_id=user_id)


def send_media_group(
    photos: Sequence[bytes],
    caption: str | None = None,
    user_id: str | None = None,
) -> None:
    build_sender().send_media_group(photos, caption=caption, user_id=user_id)
