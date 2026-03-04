import os
import pathlib
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent
ENV_PATH = ROOT.parent / ".env"
_ENV_LOADED = False


@dataclass(frozen=True)
class Settings:
    yc_api_key: str
    yc_folder_id: str
    tg_bot_token: str
    tg_chat_id: str
    mic_device: str | None
    mix_device: str | None


def load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)
    _ENV_LOADED = True


def _require(name: str) -> str:
    load_env()
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"{name} не задан. " "Скопируйте .env.example -> .env и заполните значения."
        )
    return val


def load_settings() -> Settings:
    settings = Settings(
        yc_api_key=_require("YC_API_KEY"),
        yc_folder_id=_require("YC_FOLDER_ID"),
        tg_bot_token=_require("TG_BOT_TOKEN"),
        tg_chat_id=_require("TG_CHAT_ID"),
        mic_device=os.getenv("MIC_DEVICE"),
        mix_device=os.getenv("MIX_DEVICE"),
    )
    os.environ["YC_FOLDER_ID"] = settings.yc_folder_id
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
