import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.domain.yandex_queue import (
    YandexQueueFullError,
    YandexQueueTimeoutError,
    YandexRequestQueue,
)


def test_queue_limits_concurrent_operations_and_rejects_overflow():
    queue = YandexRequestQueue(max_concurrent=1, max_waiting=1, wait_timeout=1)
    entered = threading.Event()
    release = threading.Event()

    def slow_operation(value: str) -> str:
        entered.set()
        assert release.wait(timeout=1)
        return value

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(queue.execute, slow_operation, "first")
        assert entered.wait(timeout=1)
        second = executor.submit(queue.execute, lambda: "second")
        deadline = time.monotonic() + 1
        while queue.stats().waiting != 1 and time.monotonic() < deadline:
            time.sleep(0.001)
        assert queue.stats().waiting == 1

        with pytest.raises(YandexQueueFullError):
            queue.execute(lambda: "third")

        release.set()
        assert first.result(timeout=1) == "first"
        assert second.result(timeout=1) == "second"

    assert queue.stats().active == 0
    assert queue.stats().waiting == 0


def test_queue_stops_waiting_after_timeout():
    queue = YandexRequestQueue(max_concurrent=1, max_waiting=1, wait_timeout=0.01)
    entered = threading.Event()
    release = threading.Event()

    def slow_operation() -> None:
        entered.set()
        assert release.wait(timeout=1)

    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(queue.execute, slow_operation)
        assert entered.wait(timeout=1)

        with pytest.raises(YandexQueueTimeoutError):
            queue.execute(lambda: None)

        release.set()
        running.result(timeout=1)


def test_queue_can_disable_waiting():
    queue = YandexRequestQueue(max_concurrent=1, max_waiting=0)
    entered = threading.Event()
    release = threading.Event()

    def slow_operation() -> None:
        entered.set()
        assert release.wait(timeout=1)

    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(queue.execute, slow_operation)
        assert entered.wait(timeout=1)

        with pytest.raises(YandexQueueFullError):
            queue.execute(lambda: None)

        release.set()
        running.result(timeout=1)
