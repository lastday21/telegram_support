from __future__ import annotations

import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import ParamSpec, TypeVar

from app.settings import load_env

P = ParamSpec("P")
R = TypeVar("R")


class YandexQueueFullError(RuntimeError):
    pass


class YandexQueueTimeoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueueStats:
    active: int
    waiting: int
    max_concurrent: int
    max_waiting: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class YandexRequestQueue:
    def __init__(
        self,
        max_concurrent: int = 2,
        max_waiting: int = 8,
        wait_timeout: float = 300,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("Число одновременных запросов должно быть положительным")
        if max_waiting < 0:
            raise ValueError("Размер очереди не может быть отрицательным")
        if wait_timeout <= 0:
            raise ValueError("Время ожидания должно быть положительным")

        self.max_concurrent = max_concurrent
        self.max_waiting = max_waiting
        self.wait_timeout = wait_timeout
        self._active = 0
        self._waiting: deque[object] = deque()
        self._condition = threading.Condition()

    def stats(self) -> QueueStats:
        with self._condition:
            return QueueStats(
                active=self._active,
                waiting=len(self._waiting),
                max_concurrent=self.max_concurrent,
                max_waiting=self.max_waiting,
            )

    def execute(
        self, operation: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        self._acquire_slot()
        try:
            return operation(*args, **kwargs)
        finally:
            with self._condition:
                self._active -= 1
                self._condition.notify_all()

    def _acquire_slot(self) -> None:
        with self._condition:
            if self._active < self.max_concurrent and not self._waiting:
                self._active += 1
                return
            if len(self._waiting) >= self.max_waiting:
                raise YandexQueueFullError("Очередь запросов к Яндексу заполнена")

            ticket = object()
            self._waiting.append(ticket)
            deadline = time.monotonic() + self.wait_timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._waiting.remove(ticket)
                    self._condition.notify_all()
                    raise YandexQueueTimeoutError(
                        "Истекло время ожидания в очереди запросов к Яндексу"
                    )
                self._condition.wait(timeout=remaining)
                if (
                    self._waiting
                    and self._waiting[0] is ticket
                    and self._active < self.max_concurrent
                ):
                    self._waiting.popleft()
                    self._active += 1
                    return


def _integer_setting(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} должен быть целым числом") from exc
    if value < minimum:
        raise RuntimeError(f"{name} должен быть не меньше {minimum}")
    return value


def _float_setting(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} должен быть числом") from exc
    if value <= 0:
        raise RuntimeError(f"{name} должен быть положительным")
    return value


def build_yandex_queue() -> YandexRequestQueue:
    load_env()
    return YandexRequestQueue(
        max_concurrent=_integer_setting("YANDEX_MAX_CONCURRENT", 2, 1),
        max_waiting=_integer_setting("YANDEX_QUEUE_SIZE", 8, 0),
        wait_timeout=_float_setting("YANDEX_QUEUE_TIMEOUT", 300),
    )
