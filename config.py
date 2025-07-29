import os
import pathlib
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)

def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"{name} не задан. "
            "Скопируйте .env.example → .env и впишите ключи."
        )
    return val

YC_API_KEY   = _require("YC_API_KEY")
YC_FOLDER_ID = _require("YC_FOLDER_ID")
TG_BOT_TOKEN = _require("TG_BOT_TOKEN")
TG_CHAT_ID   = _require("TG_CHAT_ID")

os.environ["YC_FOLDER_ID"] = YC_FOLDER_ID
