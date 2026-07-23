from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.settings import load_env


class RequestBodyTooLargeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RequestGuardConfig:
    max_concurrent: int = 16
    requests_per_window: int = 120
    rate_window_seconds: float = 60
    max_body_bytes: int = 22 * 1024 * 1024
    auth_failure_limit: int = 5
    auth_failure_window_seconds: float = 60
    auth_block_seconds: float = 300


class RequestGuard:
    def __init__(
        self,
        config: RequestGuardConfig = RequestGuardConfig(),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            min(
                config.max_concurrent,
                config.requests_per_window,
                config.max_body_bytes,
                config.auth_failure_limit,
            )
            < 1
        ):
            raise ValueError("Ограничения запросов должны быть положительными")
        if (
            min(
                config.rate_window_seconds,
                config.auth_failure_window_seconds,
                config.auth_block_seconds,
            )
            <= 0
        ):
            raise ValueError("Периоды ограничений должны быть положительными")
        self.config = config
        self.clock = clock
        self._semaphore = threading.BoundedSemaphore(config.max_concurrent)
        self._lock = threading.Lock()
        self._requests: dict[str, deque[float]] = {}
        self._auth_failures: dict[str, deque[float]] = {}
        self._blocked_until: dict[str, float] = {}
        self._last_cleanup = self.clock()

    @staticmethod
    def client_key(scope: Scope) -> str:
        client = scope.get("client")
        if not client:
            return "unknown"
        return str(client[0])

    def try_acquire(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        self._semaphore.release()

    def check_rate(self, client_key: str) -> int | None:
        now = self.clock()
        cutoff = now - self.config.rate_window_seconds
        with self._lock:
            self._cleanup(now)
            requests = self._requests.setdefault(client_key, deque())
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.config.requests_per_window:
                return max(
                    1, math.ceil(requests[0] + self.config.rate_window_seconds - now)
                )
            requests.append(now)
            return None

    def auth_block_remaining(self, client_key: str) -> int | None:
        now = self.clock()
        with self._lock:
            blocked_until = self._blocked_until.get(client_key)
            if blocked_until is None:
                return None
            if blocked_until <= now:
                self._blocked_until.pop(client_key, None)
                return None
            return max(1, math.ceil(blocked_until - now))

    def record_auth_failure(self, client_key: str) -> int | None:
        now = self.clock()
        cutoff = now - self.config.auth_failure_window_seconds
        with self._lock:
            failures = self._auth_failures.setdefault(client_key, deque())
            while failures and failures[0] <= cutoff:
                failures.popleft()
            failures.append(now)
            if len(failures) < self.config.auth_failure_limit:
                return None
            blocked_until = now + self.config.auth_block_seconds
            self._blocked_until[client_key] = blocked_until
            failures.clear()
            return max(1, math.ceil(self.config.auth_block_seconds))

    def record_auth_success(self, client_key: str) -> None:
        with self._lock:
            self._auth_failures.pop(client_key, None)

    def _cleanup(self, now: float) -> None:
        cleanup_interval = max(
            self.config.rate_window_seconds,
            self.config.auth_failure_window_seconds,
        )
        if now - self._last_cleanup < cleanup_interval:
            return
        request_cutoff = now - self.config.rate_window_seconds
        auth_cutoff = now - self.config.auth_failure_window_seconds
        self._requests = {
            key: values
            for key, values in self._requests.items()
            if values and values[-1] > request_cutoff
        }
        self._auth_failures = {
            key: values
            for key, values in self._auth_failures.items()
            if values and values[-1] > auth_cutoff
        }
        self._blocked_until = {
            key: blocked_until
            for key, blocked_until in self._blocked_until.items()
            if blocked_until > now
        }
        self._last_cleanup = now


class RequestProtectionMiddleware:
    EXEMPT_PATHS = frozenset({"/live", "/ready", "/health"})

    def __init__(self, app: ASGIApp, guard: RequestGuard) -> None:
        self.app = app
        self.guard = guard

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        client_key = self.guard.client_key(scope)
        blocked_for = self.guard.auth_block_remaining(client_key)
        if blocked_for is not None:
            await self._send_error(
                send,
                429,
                "Слишком много ошибок доступа, повторите позже",
                blocked_for,
            )
            return

        retry_after = self.guard.check_rate(client_key)
        if retry_after is not None:
            await self._send_error(
                send,
                429,
                "Слишком много запросов, повторите позже",
                retry_after,
            )
            return

        content_length = self._content_length(scope)
        if content_length is None:
            await self._send_error(send, 400, "Некорректный размер запроса")
            return
        if content_length > self.guard.config.max_body_bytes:
            await self._send_error(send, 413, "Запрос слишком большой")
            return
        if not self.guard.try_acquire():
            await self._send_error(
                send,
                503,
                "Сервер занят, повторите позже",
                1,
            )
            return

        received_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.guard.config.max_body_bytes:
                    raise RequestBodyTooLargeError
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLargeError:
            if response_started:
                raise
            await self._send_error(send, 413, "Запрос слишком большой")
        finally:
            self.guard.release()

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() != b"content-length":
                continue
            try:
                length = int(value)
            except ValueError:
                return None
            return length if length >= 0 else None
        return 0

    @staticmethod
    async def _send_error(
        send: Send,
        status_code: int,
        detail: str,
        retry_after: int | None = None,
    ) -> None:
        body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        headers = [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        if retry_after is not None:
            headers.append((b"retry-after", str(retry_after).encode("ascii")))
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body})


def _integer_setting(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} должен быть целым числом") from exc
    if value < 1:
        raise RuntimeError(f"{name} должен быть положительным")
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


def build_request_guard() -> RequestGuard:
    load_env()
    return RequestGuard(
        RequestGuardConfig(
            max_concurrent=_integer_setting("HTTP_MAX_CONCURRENT", 16),
            requests_per_window=_integer_setting("HTTP_REQUEST_LIMIT", 120),
            rate_window_seconds=_float_setting("HTTP_RATE_WINDOW", 60),
            max_body_bytes=_integer_setting("HTTP_MAX_BODY_SIZE", 22 * 1024 * 1024),
            auth_failure_limit=_integer_setting("AUTH_FAILURE_LIMIT", 5),
            auth_failure_window_seconds=_float_setting("AUTH_FAILURE_WINDOW", 60),
            auth_block_seconds=_float_setting("AUTH_BLOCK_SECONDS", 300),
        )
    )
