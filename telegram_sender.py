# telegram_sender.py
import json
import requests
from pathlib import Path

# Читаем config.json, но defaultCaption может не быть
_cfg = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
BOT_TOKEN = _cfg["botToken"]
CHAT_ID   = _cfg["chatID"]
CAPTION   = _cfg.get("defaultCaption", "")  # ← здесь

def send_photo(photo_path: str, caption: str | None = None) -> None:
    """
    Отправляет картинку в Telegram с подписью.
    Если caption не указан — берётся из config.json → defaultCaption, или пустая строка.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": CHAT_ID,
        "caption": caption if caption is not None else CAPTION
    }
    with open(photo_path, "rb") as img:
        files = {"photo": img}
        resp = requests.post(url, data=data, files=files, timeout=30)
        resp.raise_for_status()

def send_message(text: str) -> None:
    """
    Отправляет текстовое сообщение в Telegram.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
