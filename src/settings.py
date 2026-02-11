import os
import pathlib
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent
ENV_PATH =  ROOT.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)


def _optional(name: str) -> str:
    return os.getenv(name, "")


def require_settings(*names: str) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Не заданы переменные: {joined}. "
            "Скопируйте .env.example → .env и впишите ключи."
        )


YC_API_KEY = _optional("YC_API_KEY")
YC_FOLDER_ID = _optional("YC_FOLDER_ID")
TG_BOT_TOKEN = _optional("TG_BOT_TOKEN")
TG_CHAT_ID = _optional("TG_CHAT_ID")

if YC_FOLDER_ID:
    os.environ["YC_FOLDER_ID"] = YC_FOLDER_ID
