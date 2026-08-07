from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.interfaces.telegram.sender import (
    send_media_group as send_telegram_media_group,
)
from app.interfaces.telegram.sender import send_message as send_telegram_message
from app.interfaces.telegram.sender import send_photo as send_telegram_photo
from app.interfaces.vk.sender import send_media_group as send_vk_media_group
from app.interfaces.vk.sender import send_message as send_vk_message
from app.interfaces.vk.sender import send_photo as send_vk_photo
from app.settings import get_settings

logger = logging.getLogger(__name__)


class MessengerDeliveryError(RuntimeError):
    pass


def _deliver(operations: Sequence[tuple[str, Callable[[], None]]]) -> None:
    delivered = False
    errors: list[Exception] = []
    with ThreadPoolExecutor(
        max_workers=len(operations),
        thread_name_prefix="messenger-delivery",
    ) as executor:
        futures = {
            executor.submit(operation): channel for channel, operation in operations
        }
        for future in as_completed(futures):
            channel = futures[future]
            try:
                future.result()
                delivered = True
            except Exception as exc:
                logger.warning(
                    "Не удалось отправить сообщение через %s: %s",
                    channel,
                    type(exc).__name__,
                )
                errors.append(exc)
    if not delivered:
        raise MessengerDeliveryError("Не удалось отправить сообщение") from (
            errors[-1] if errors else None
        )


def _vk_enabled() -> bool:
    settings = get_settings()
    return bool(settings.vk_group_token and settings.vk_user_id)


def send_message(text: str, chat_id: str | None = None) -> None:
    operations: list[tuple[str, Callable[[], None]]] = [
        ("Telegram", lambda: send_telegram_message(text, chat_id))
    ]
    if _vk_enabled():
        operations.append(("ВКонтакте", lambda: send_vk_message(text)))
    _deliver(operations)


def send_photo(
    photo: bytes,
    caption: str | None = None,
    chat_id: str | None = None,
) -> None:
    operations: list[tuple[str, Callable[[], None]]] = [
        ("Telegram", lambda: send_telegram_photo(photo, caption, chat_id))
    ]
    if _vk_enabled():
        operations.append(("ВКонтакте", lambda: send_vk_photo(photo, caption)))
    _deliver(operations)


def send_media_group(
    photos: list[bytes],
    caption: str | None = None,
    chat_id: str | None = None,
) -> None:
    operations: list[tuple[str, Callable[[], None]]] = [
        (
            "Telegram",
            lambda: send_telegram_media_group(photos, caption, chat_id),
        )
    ]
    if _vk_enabled():
        operations.append(("ВКонтакте", lambda: send_vk_media_group(photos, caption)))
    _deliver(operations)
