from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueuedAction:
    target: Callable[..., Any]
    args: tuple[Any, ...]


class SerialActionQueue:
    def __init__(
        self,
        max_pending: int = 12,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._queue: queue.Queue[QueuedAction | None] = queue.Queue(maxsize=max_pending)
        self._on_error = on_error
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._closed = False

    def submit(self, target: Callable[..., Any], args: tuple[Any, ...] = ()) -> bool:
        if self._closed:
            return False
        self._ensure_started()
        try:
            self._queue.put_nowait(QueuedAction(target=target, args=args))
        except queue.Full:
            return False
        return True

    def close(self) -> None:
        self._closed = True
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

    def _ensure_started(self) -> None:
        if self._thread is not None:
            return
        with self._start_lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run,
                name="smarthelper-actions",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        while True:
            action = self._queue.get()
            try:
                if action is None:
                    return
                action.target(*action.args)
            except Exception as exc:
                if self._on_error is not None:
                    self._on_error(exc)
            finally:
                self._queue.task_done()
            if self._closed and self._queue.empty():
                return
