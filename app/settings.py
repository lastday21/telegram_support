from __future__ import annotations

import json
import os
import pathlib
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from dotenv import dotenv_values, load_dotenv

from app.prompts import PROMPTS

ROOT = pathlib.Path(__file__).resolve().parent
ENV_PATH = ROOT.parent / ".env"
CLIENT_ENV_NAME = "SMARTHELPER_ENV_FILE"
PREFERENCES_ENV_NAME = "SMARTHELPER_SETTINGS_FILE"
DEFAULT_YC_MODEL = "qwen3-235b-a22b-fp8/latest"
DEFAULT_SERVER_URL = "http://127.0.0.1:8000"
DEFAULT_RECORD_HOTKEY = "alt+q"
DEFAULT_MOUSE_PROMPT = PROMPTS[0]
DEFAULT_ACTION_HOTKEYS = tuple(f"ctrl+{index}" for index in range(1, 6))
DEFAULT_ACTION_PROMPTS = (PROMPTS[1], PROMPTS[2], PROMPTS[3], PROMPTS[5], PROMPTS[6])
MODEL_OPTIONS = (
    ("Qwen3 235B — сложные задачи", "qwen3-235b-a22b-fp8/latest"),
    ("Alice AI — быстрый точный ответ", "aliceai-llm/latest"),
    ("Alice AI Flash — максимальная скорость", "aliceai-llm-flash/latest"),
    ("DeepSeek V3.2 — расчёты и программирование", "deepseek-v32/latest"),
)
SUPPORTED_YC_MODELS = frozenset(model for _label, model in MODEL_OPTIONS)


@dataclass(frozen=True)
class Settings:
    yc_api_key: str
    yc_folder_id: str
    tg_bot_token: str
    tg_chat_id: str
    mic_device: str | None
    mix_device: str | None
    app_access_token: str = ""
    yc_model: str = DEFAULT_YC_MODEL


@dataclass(frozen=True)
class ClientSettings:
    server_url: str
    app_access_token: str
    mic_device: str | None
    mix_device: str | None
    yc_model: str = DEFAULT_YC_MODEL
    record_hotkey: str = DEFAULT_RECORD_HOTKEY
    mouse_prompt: str = DEFAULT_MOUSE_PROMPT
    action_hotkeys: tuple[str, ...] = DEFAULT_ACTION_HOTKEYS
    action_prompts: tuple[str, ...] = DEFAULT_ACTION_PROMPTS
    show_answer_overlay: bool = True


@dataclass(frozen=True)
class UserPreferences:
    yc_model: str = DEFAULT_YC_MODEL
    record_hotkey: str = DEFAULT_RECORD_HOTKEY
    mouse_prompt: str = DEFAULT_MOUSE_PROMPT
    action_hotkeys: tuple[str, ...] = DEFAULT_ACTION_HOTKEYS
    action_prompts: tuple[str, ...] = DEFAULT_ACTION_PROMPTS
    show_answer_overlay: bool = True


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


def writable_client_env_path() -> pathlib.Path:
    explicit_path = os.getenv(CLIENT_ENV_NAME)
    if explicit_path:
        return pathlib.Path(explicit_path).expanduser().resolve()
    app_data = pathlib.Path(os.getenv("APPDATA") or pathlib.Path.home())
    return app_data / "SmartHelper" / ".env"


def client_preferences_path() -> pathlib.Path:
    explicit_path = os.getenv(PREFERENCES_ENV_NAME)
    if explicit_path:
        return pathlib.Path(explicit_path).expanduser().resolve()
    app_data = pathlib.Path(os.getenv("APPDATA") or pathlib.Path.home())
    return app_data / "SmartHelper" / "settings.json"


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


def _read_client_env() -> tuple[dict[str, str], pathlib.Path]:
    env_path = client_env_path()
    values: dict[str, str] = {}
    if env_path.is_file():
        values.update(
            {
                name: value
                for name, value in dotenv_values(env_path).items()
                if value is not None
            }
        )
    for name in ("SERVER_URL", "APP_ACCESS_TOKEN", "MIC_DEVICE", "MIX_DEVICE"):
        value = os.getenv(name)
        if value is not None:
            values[name] = value
    return values, env_path


def validate_client_connection(server_url: str, access_token: str) -> tuple[str, str]:
    normalized_url = server_url.strip().rstrip("/")
    parsed_url = urlsplit(normalized_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("Укажите полный адрес сервера, начиная с http:// или https://")
    if parsed_url.query or parsed_url.fragment:
        raise ValueError("Адрес сервера не должен содержать параметры или якорь")

    normalized_token = access_token.strip()
    if not normalized_token:
        raise ValueError("Укажите ключ доступа к серверу")
    if "\n" in normalized_token or "\r" in normalized_token:
        raise ValueError("Ключ доступа содержит недопустимые символы")
    return normalized_url, normalized_token


def env_flag(name: str, default: bool = False) -> bool:
    load_env()
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def validate_hotkeys(
    record_hotkey: str, action_hotkeys: Sequence[str]
) -> tuple[str, tuple[str, ...]]:
    record = record_hotkey.strip().lower()
    actions = tuple(hotkey.strip().lower() for hotkey in action_hotkeys)
    if not record or len(actions) != 5 or any(not hotkey for hotkey in actions):
        raise ValueError("Нужно задать клавишу микрофона и пять сочетаний команд")
    all_hotkeys = (record, *actions)
    if len(set(all_hotkeys)) != len(all_hotkeys):
        raise ValueError("Сочетания клавиш не должны повторяться")
    return record, actions


def _text(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def load_user_preferences() -> UserPreferences:
    path = client_preferences_path()
    if not path.exists():
        return UserPreferences()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UserPreferences()
    if not isinstance(data, Mapping):
        return UserPreferences()

    model = _text(data.get("model"), DEFAULT_YC_MODEL)
    if model not in SUPPORTED_YC_MODELS:
        model = DEFAULT_YC_MODEL
    record_hotkey = _text(data.get("record_hotkey"), DEFAULT_RECORD_HOTKEY).lower()
    mouse_prompt = _text(data.get("mouse_prompt"), DEFAULT_MOUSE_PROMPT)
    show_answer_overlay = data.get("show_answer_overlay", True)
    if not isinstance(show_answer_overlay, bool):
        show_answer_overlay = True

    action_hotkeys = list(DEFAULT_ACTION_HOTKEYS)
    action_prompts = list(DEFAULT_ACTION_PROMPTS)
    actions = data.get("actions")
    if isinstance(actions, list):
        for index, action in enumerate(actions[:5]):
            if not isinstance(action, Mapping):
                continue
            action_hotkeys[index] = _text(
                action.get("hotkey"), DEFAULT_ACTION_HOTKEYS[index]
            ).lower()
            action_prompts[index] = _text(
                action.get("prompt"), DEFAULT_ACTION_PROMPTS[index]
            )

    try:
        record_hotkey, validated_hotkeys = validate_hotkeys(
            record_hotkey, action_hotkeys
        )
    except ValueError:
        record_hotkey = DEFAULT_RECORD_HOTKEY
        validated_hotkeys = DEFAULT_ACTION_HOTKEYS

    return UserPreferences(
        yc_model=model,
        record_hotkey=record_hotkey,
        mouse_prompt=mouse_prompt,
        action_hotkeys=validated_hotkeys,
        action_prompts=tuple(action_prompts),
        show_answer_overlay=show_answer_overlay,
    )


def load_settings() -> Settings:
    settings = Settings(
        yc_api_key=_require("YC_API_KEY"),
        yc_folder_id=_require("YC_FOLDER_ID"),
        tg_bot_token=_require("TG_BOT_TOKEN"),
        tg_chat_id=_require("TG_CHAT_ID"),
        mic_device=os.getenv("MIC_DEVICE"),
        mix_device=os.getenv("MIX_DEVICE"),
        app_access_token=_require("APP_ACCESS_TOKEN"),
        yc_model=os.getenv("YC_MODEL", DEFAULT_YC_MODEL).strip() or DEFAULT_YC_MODEL,
    )
    os.environ["YC_FOLDER_ID"] = settings.yc_folder_id
    return settings


def load_client_settings(require_connection: bool = True) -> ClientSettings:
    values, env_path = _read_client_env()
    preferences = load_user_preferences()
    server_url = values.get("SERVER_URL", "").strip().rstrip("/")
    access_token = values.get("APP_ACCESS_TOKEN", "").strip()
    if require_connection:
        if not server_url:
            raise RuntimeError(
                f"SERVER_URL не задан. Заполните файл настроек: {env_path}"
            )
        if not access_token:
            raise RuntimeError(
                f"APP_ACCESS_TOKEN не задан. Заполните файл настроек: {env_path}"
            )
    else:
        server_url = server_url or DEFAULT_SERVER_URL
    return ClientSettings(
        server_url=server_url,
        app_access_token=access_token,
        mic_device=values.get("MIC_DEVICE") or None,
        mix_device=values.get("MIX_DEVICE") or None,
        yc_model=preferences.yc_model,
        record_hotkey=preferences.record_hotkey,
        mouse_prompt=preferences.mouse_prompt,
        action_hotkeys=preferences.action_hotkeys,
        action_prompts=preferences.action_prompts,
        show_answer_overlay=preferences.show_answer_overlay,
    )


def save_client_connection_settings(
    server_url: str,
    access_token: str,
    mic_device: str | None = None,
    mix_device: str | None = None,
) -> ClientSettings:
    normalized_url, normalized_token = validate_client_connection(
        server_url, access_token
    )
    path = writable_client_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(
        "\n".join(
            (
                f"SERVER_URL={normalized_url}",
                f"APP_ACCESS_TOKEN={normalized_token}",
                f"MIC_DEVICE={(mic_device or '').strip()}",
                f"MIX_DEVICE={(mix_device or '').strip()}",
                "",
            )
        ),
        encoding="utf-8",
    )
    temp_path.replace(path)
    get_client_settings.cache_clear()
    return load_client_settings()


def save_client_preferences(
    yc_model: str,
    record_hotkey: str,
    mouse_prompt: str,
    actions: Sequence[tuple[str, str]],
    show_answer_overlay: bool = True,
) -> UserPreferences:
    if yc_model not in SUPPORTED_YC_MODELS:
        raise ValueError("Выбрана неподдерживаемая модель")
    if len(actions) != 5:
        raise ValueError("Нужно настроить пять команд")

    record_hotkey, action_hotkeys = validate_hotkeys(
        record_hotkey, [hotkey for hotkey, _prompt in actions]
    )
    normalized_mouse_prompt = mouse_prompt.strip()
    action_prompts = tuple(prompt.strip() for _hotkey, prompt in actions)
    if not normalized_mouse_prompt or any(not prompt for prompt in action_prompts):
        raise ValueError("Подсказки не могут быть пустыми")

    data = {
        "model": yc_model,
        "record_hotkey": record_hotkey,
        "mouse_prompt": normalized_mouse_prompt,
        "show_answer_overlay": show_answer_overlay,
        "actions": [
            {"hotkey": hotkey, "prompt": prompt}
            for hotkey, prompt in zip(action_hotkeys, action_prompts, strict=True)
        ],
    }
    path = client_preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
    get_client_settings.cache_clear()
    return load_user_preferences()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=1)
def get_client_settings() -> ClientSettings:
    return load_client_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
    get_client_settings.cache_clear()
