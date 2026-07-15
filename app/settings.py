from __future__ import annotations

import os
import pathlib
import sys
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent
ENV_PATH = ROOT.parent / ".env"
CLIENT_ENV_NAME = "SMARTHELPER_ENV_FILE"


@dataclass(frozen=True)
class Settings:
    yc_api_key: str
    yc_folder_id: str
    tg_bot_token: str
    tg_chat_id: str
    mic_device: str | None
    mix_device: str | None
    app_access_token: str = ""


@dataclass(frozen=True)
class ClientSettings:
    server_url: str
    app_access_token: str
    mic_device: str | None
    mix_device: str | None


def client_env_path() -> pathlib.Path:
    explicit_path = os.getenv(CLIENT_ENV_NAME)
    if explicit_path:
        return pathlib.Path(explicit_path).expanduser().resolve()

    app_data = os.getenv("APPDATA")
    base_dir = pathlib.Path(app_data) if app_data else pathlib.Path.home()
    app_data_path = base_dir / "SmartHelper" / ".env"
    if getattr(sys, "frozen", False) or app_data_path.exists():
        return app_data_path

    return ENV_PATH


def load_env(path: pathlib.Path | None = None) -> None:
    env_path = path or ENV_PATH
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _require(name: str, env_path: pathlib.Path = ENV_PATH) -> str:
    load_env(env_path)
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} не задан. Заполните файл настроек: {env_path}")
    return value


def env_flag(name: str, default: bool = False) -> bool:
    load_env()
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def load_settings() -> Settings:
    settings = Settings(
        yc_api_key=_require("YC_API_KEY"),
        yc_folder_id=_require("YC_FOLDER_ID"),
        tg_bot_token=_require("TG_BOT_TOKEN"),
        tg_chat_id=_require("TG_CHAT_ID"),
        mic_device=os.getenv("MIC_DEVICE"),
        mix_device=os.getenv("MIX_DEVICE"),
        app_access_token=_require("APP_ACCESS_TOKEN"),
    )
    os.environ["YC_FOLDER_ID"] = settings.yc_folder_id
    return settings


def load_client_settings() -> ClientSettings:
    env_path = client_env_path()
    load_env(env_path)
    return ClientSettings(
        server_url=_require("SERVER_URL", env_path).rstrip("/"),
        app_access_token=_require("APP_ACCESS_TOKEN", env_path),
        mic_device=os.getenv("MIC_DEVICE"),
        mix_device=os.getenv("MIX_DEVICE"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_client_settings() -> ClientSettings:
    return load_client_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
    get_client_settings.cache_clear()
