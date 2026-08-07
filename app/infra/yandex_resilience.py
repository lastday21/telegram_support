from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Sequence
from typing import TypeVar

import requests

from app.settings import load_env

logger = logging.getLogger(__name__)
R = TypeVar("R")


class YandexCircuitOpenError(RuntimeError):
    pass


class YandexCallPolicy:
    def __init__(
        self,
        retry_delays: Sequence[float] = (0.5, 1.5),
        failure_limit: int = 5,
        recovery_seconds: float = 30,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_limit < 1 or recovery_seconds <= 0:
            raise ValueError("Параметры защиты Яндекса должны быть положительными")
        if any(delay < 0 for delay in retry_delays):
            raise ValueError("Задержки повторных запросов не могут быть отрицательными")
        self.retry_delays = tuple(retry_delays)
        self.failure_limit = failure_limit
        self.recovery_seconds = recovery_seconds
        self.sleeper = sleeper
        self.clock = clock
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._blocked_until = 0.0
        self._probe_in_progress = False

    def execute(self, operation: Callable[[], R]) -> R:
        self._before_call()
        try:
            for attempt in range(len(self.retry_delays) + 1):
                try:
                    result = operation()
                except Exception as exc:
                    if not self._is_transient(exc):
                        self._record_success()
                        raise
                    if attempt == len(self.retry_delays):
                        self._record_failure()
                        raise
                    delay = self.retry_delays[attempt]
                    logger.warning(
                        "Временная ошибка Яндекса (%s), повтор через %.1f с",
                        type(exc).__name__,
                        delay,
                    )
                    self.sleeper(delay)
                    continue
                self._record_success()
                return result
        finally:
            self._finish_probe()
        raise RuntimeError("Запрос к Яндексу завершился без результата")

    def blocked_for(self) -> int:
        with self._lock:
            return max(0, int(self._blocked_until - self.clock() + 0.999))

    def _before_call(self) -> None:
        now = self.clock()
        with self._lock:
            if self._blocked_until <= now:
                if self._blocked_until > 0:
                    if self._probe_in_progress:
                        raise YandexCircuitOpenError(
                            "Проверка восстановления Яндекса уже выполняется"
                        )
                    self._probe_in_progress = True
                return
            remaining = max(1, int(self._blocked_until - now + 0.999))
            raise YandexCircuitOpenError(
                f"Запросы к Яндексу приостановлены ещё на {remaining} с"
            )

    def _record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._blocked_until = 0

    def _record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures < self.failure_limit:
                return
            self._blocked_until = self.clock() + self.recovery_seconds
            logger.error(
                "Запросы к Яндексу приостановлены на %.0f с после %s сбоев",
                self.recovery_seconds,
                self._consecutive_failures,
            )

    def _finish_probe(self) -> None:
        with self._lock:
            self._probe_in_progress = False

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            return True
        if not isinstance(exc, requests.HTTPError):
            return False
        response = exc.response
        status_code = getattr(response, "status_code", None)
        return status_code == 429 or (
            isinstance(status_code, int) and status_code >= 500
        )


def _retry_delays() -> tuple[float, ...]:
    raw = os.getenv("YANDEX_RETRY_DELAYS", "0.5")
    try:
        delays = tuple(
            float(value.strip()) for value in raw.split(",") if value.strip()
        )
    except ValueError as exc:
        raise RuntimeError("YANDEX_RETRY_DELAYS должен содержать числа") from exc
    if any(delay < 0 for delay in delays):
        raise RuntimeError("YANDEX_RETRY_DELAYS не может содержать отрицательные числа")
    return delays


def _integer_setting(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError as exc:
        raise RuntimeError(f"{name} должен быть целым числом") from exc
    if value < 1:
        raise RuntimeError(f"{name} должен быть положительным")
    return value


def _float_setting(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        value = float(raw) if raw is not None else default
    except ValueError as exc:
        raise RuntimeError(f"{name} должен быть числом") from exc
    if value <= 0:
        raise RuntimeError(f"{name} должен быть положительным")
    return value


def build_yandex_call_policy() -> YandexCallPolicy:
    load_env()
    return YandexCallPolicy(
        retry_delays=_retry_delays(),
        failure_limit=_integer_setting("YANDEX_FAILURE_LIMIT", 5),
        recovery_seconds=_float_setting("YANDEX_RECOVERY_SECONDS", 30),
    )


default_yandex_call_policy = build_yandex_call_policy()
