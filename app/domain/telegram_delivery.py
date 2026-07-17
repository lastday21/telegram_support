from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Sequence

logger = logging.getLogger(__name__)


class TelegramDeliveryQueue:
    def __init__(
        self,
        send_message: Callable[[str], None],
        retry_delays: Sequence[float] = (1, 3),
        max_pending: int = 16,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._send_message = send_message
        self._retry_delays = tuple(retry_delays)
        self._sleeper = sleeper
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=max_pending)
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._closed = False

    def submit(self, text: str) -> bool:
        if self._closed or not text.strip():
            return False
        self._ensure_started()
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            return False
        return True

    def close(self) -> None:
        self._closed = True
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            return

    def _ensure_started(self) -> None:
        if self._thread is not None:
            return
        with self._start_lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run,
                name="smarthelper-telegram",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        while True:
            text = self._queue.get()
            try:
                if text is None:
                    return
                self._send_with_retry(text)
            finally:
                self._queue.task_done()
            if self._closed and self._queue.empty():
                return

    def _send_with_retry(self, text: str) -> None:
        attempts = len(self._retry_delays) + 1
        for attempt in range(attempts):
            try:
                self._send_message(text)
                return
            except Exception:
                if attempt == attempts - 1:
                    logger.exception(
                        "Не удалось отправить сообщение в Telegram после %s попыток",
                        attempts,
                    )
                    return
                logger.warning(
                    "Не удалось отправить сообщение в Telegram, повторяю попытку",
                    exc_info=True,
                )
                self._sleeper(self._retry_delays[attempt])
