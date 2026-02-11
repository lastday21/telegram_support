from typing import BinaryIO, Union

import requests

from src.settings import TG_BOT_TOKEN, TG_CHAT_ID

DEFAULT_CAPTION = ""


def send_photo(photo: Union[str, bytes, BinaryIO], caption: str | None = None) -> None:
    send_photo_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    request_data = {
        "chat_id": TG_CHAT_ID,
        "caption": caption if caption is not None else DEFAULT_CAPTION,
    }

    if isinstance(photo, bytes):
        files_payload: dict[str, tuple[str, bytes]] = {"photo": ("shot.png", photo)}
    elif isinstance(photo, str):
        with open(photo, "rb") as file_handle:
            file_content = file_handle.read()
        files_payload = {"photo": ("shot.png", file_content)}
    else:
        files_payload = {"photo": ("shot.png", photo.read())}

    response = requests.post(
        send_photo_url,
        data=request_data,
        files=files_payload,
        timeout=30,
    )
    response.raise_for_status()


def send_message(text: str) -> None:
    send_message_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    request_data = {"chat_id": TG_CHAT_ID, "text": text}

    response = requests.post(send_message_url, data=request_data, timeout=30)
    response.raise_for_status()
