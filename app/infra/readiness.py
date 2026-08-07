from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

from app.settings import (
    SUPPORTED_YC_MODELS,
    SUPPORTED_YC_VISION_MODELS,
    Settings,
    get_settings,
    load_env,
)

logger = logging.getLogger(__name__)
YANDEX_MODELS_URL = "https://ai.api.cloud.yandex.net/v1/models"
TELEGRAM_API_URL = "https://api.telegram.org"
VK_API_URL = "https://api.vk.com/method"


@dataclass(frozen=True)
class ReadinessReport:
    ready: bool
    checks: dict[str, str]


class ExternalReadinessChecker:
    def __init__(
        self,
        settings_provider: Callable[[], Settings] = get_settings,
        http_get: Callable[..., Any] = requests.get,
        cache_seconds: float = 30,
        timeout: float = 5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if cache_seconds < 0:
            raise ValueError("Срок хранения проверки не может быть отрицательным")
        if timeout <= 0:
            raise ValueError("Время проверки должно быть положительным")
        self.settings_provider = settings_provider
        self.http_get = http_get
        self.cache_seconds = cache_seconds
        self.timeout = timeout
        self.clock = clock
        self._lock = threading.Lock()
        self._cached: tuple[float, ReadinessReport] | None = None

    def check(self) -> ReadinessReport:
        now = self.clock()
        with self._lock:
            if self._cached is not None:
                checked_at, report = self._cached
                if now - checked_at < self.cache_seconds:
                    return report

            report = self._perform_check()
            self._cached = (self.clock(), report)
            return report

    def _perform_check(self) -> ReadinessReport:
        try:
            settings = self.settings_provider()
            self._validate_settings(settings)
        except Exception as exc:
            logger.warning("Настройки сервера недоступны: %s", type(exc).__name__)
            return ReadinessReport(
                ready=False,
                checks={
                    "settings": "unavailable",
                    "yandex": "not_checked",
                    "telegram": "not_checked",
                },
            )

        checks: dict[str, str] = {
            "settings": "ok",
            "yandex": self._check_yandex(settings),
            "telegram": self._check_telegram(settings),
        }
        if settings.vk_group_token:
            checks["vk"] = self._check_vk(settings)
        messenger_checks = [checks["telegram"]]
        if "vk" in checks:
            messenger_checks.append(checks["vk"])
        return ReadinessReport(
            ready=(
                checks["settings"] == "ok"
                and checks["yandex"] == "ok"
                and any(state == "ok" for state in messenger_checks)
            ),
            checks=checks,
        )

    @staticmethod
    def _validate_settings(settings: Settings) -> None:
        if settings.yc_model not in SUPPORTED_YC_MODELS:
            raise ValueError("Выбрана неподдерживаемая модель")
        if settings.yc_vision_model not in SUPPORTED_YC_VISION_MODELS:
            raise ValueError("Выбрана неподдерживаемая зрительная модель")
        if not settings.tg_chat_id.lstrip("-").isdigit():
            raise ValueError("Идентификатор чата Telegram должен быть числом")

        if settings.vk_group_token:
            if not settings.vk_group_id.isdigit():
                raise ValueError("VK_GROUP_ID должен быть числом")
            if not settings.vk_user_id.isdigit():
                raise ValueError("VK_USER_ID должен быть числом")

    def _check_yandex(self, settings: Settings) -> str:
        try:
            response = self.http_get(
                YANDEX_MODELS_URL,
                headers={
                    "Authorization": f"Api-Key {settings.yc_api_key}",
                    "OpenAI-Project": settings.yc_folder_id,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(
                payload.get("data"), list
            ):
                raise ValueError("Яндекс вернул неожиданный ответ")
        except Exception as exc:
            logger.warning("Яндекс недоступен: %s", type(exc).__name__)
            return "unavailable"
        return "ok"

    def _check_telegram(self, settings: Settings) -> str:
        try:
            response = self.http_get(
                f"{TELEGRAM_API_URL}/bot{settings.tg_bot_token}/getMe",
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise ValueError("Telegram не подтвердил токен")
        except Exception as exc:
            logger.warning("Telegram недоступен: %s", type(exc).__name__)
            return "unavailable"
        return "ok"

    def _check_vk(self, settings: Settings) -> str:
        try:
            response = self.http_get(
                f"{VK_API_URL}/groups.getById",
                params={
                    "group_id": settings.vk_group_id,
                    "access_token": settings.vk_group_token,
                    "v": settings.vk_api_version,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if (
                not isinstance(payload, dict)
                or "error" in payload
                or "response" not in payload
            ):
                raise ValueError("ВКонтакте не подтвердил ключ сообщества")
        except Exception as exc:
            logger.warning("ВКонтакте недоступен: %s", type(exc).__name__)
            return "unavailable"
        return "ok"


def _float_setting(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} должен быть числом") from exc
    if value < minimum:
        raise RuntimeError(f"{name} должен быть не меньше {minimum}")
    return value


def build_readiness_checker() -> ExternalReadinessChecker:
    load_env()
    return ExternalReadinessChecker(
        cache_seconds=_float_setting("HEALTH_CACHE_SECONDS", 30, 0),
        timeout=_float_setting("HEALTH_TIMEOUT", 5, 0.1),
    )
