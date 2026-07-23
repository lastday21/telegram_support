import asyncio

from app.domain.request_guard import (
    RequestGuard,
    RequestGuardConfig,
    RequestProtectionMiddleware,
)


def _config(**changes) -> RequestGuardConfig:
    values = {
        "max_concurrent": 2,
        "requests_per_window": 3,
        "rate_window_seconds": 10,
        "max_body_bytes": 100,
        "auth_failure_limit": 2,
        "auth_failure_window_seconds": 10,
        "auth_block_seconds": 30,
    }
    values.update(changes)
    return RequestGuardConfig(**values)


def test_request_guard_limits_concurrent_requests():
    guard = RequestGuard(_config(max_concurrent=1))

    assert guard.try_acquire() is True
    assert guard.try_acquire() is False

    guard.release()
    assert guard.try_acquire() is True
    guard.release()


def test_request_guard_limits_request_rate():
    now = [100.0]
    guard = RequestGuard(
        _config(requests_per_window=2),
        clock=lambda: now[0],
    )

    assert guard.check_rate("client") is None
    assert guard.check_rate("client") is None
    assert guard.check_rate("client") == 10

    now[0] += 11
    assert guard.check_rate("client") is None


def test_request_guard_temporarily_blocks_repeated_auth_failures():
    now = [100.0]
    guard = RequestGuard(_config(), clock=lambda: now[0])

    assert guard.record_auth_failure("client") is None
    assert guard.record_auth_failure("client") == 30
    assert guard.auth_block_remaining("client") == 30

    now[0] += 31
    assert guard.auth_block_remaining("client") is None


def test_request_middleware_limits_streamed_body_without_content_length():
    guard = RequestGuard(_config(max_body_bytes=5))
    received_messages = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"def", "more_body": False},
    ]
    sent_messages = []

    async def application(_scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return received_messages.pop(0)

    async def send(message):
        sent_messages.append(message)

    scope = {
        "type": "http",
        "path": "/v1/text",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    middleware = RequestProtectionMiddleware(application, guard)

    asyncio.run(middleware(scope, receive, send))

    assert sent_messages[0]["status"] == 413
