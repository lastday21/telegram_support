from typing import Union, BinaryIO
import requests
from config import TG_BOT_TOKEN, TG_CHAT_ID

DEFAULT_CAPTION = ""          # Можно задать TG_DEFAULT_CAPTION в .env

def send_photo(photo: Union[str, bytes, BinaryIO],
               caption: str | None = None) -> None:
    """
    Отправляет картинку в Telegram.
    """
    url  = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TG_CHAT_ID,
        "caption": caption if caption is not None else DEFAULT_CAPTION
    }
    if isinstance(photo, bytes):
        files = {"photo": ("shot.png", photo)}
    elif isinstance(photo, str):
        files = {"photo": open(photo, "rb")}
    else:
        files = {"photo": photo}

    resp = requests.post(url, data=data, files=files, timeout=30)
    resp.raise_for_status()


def send_message(text: str) -> None:
    """
    Отправляет текстовое сообщение в Telegram.
    """
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": TG_CHAT_ID, "text": text}, timeout=30)
    resp.raise_for_status()
