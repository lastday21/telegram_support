from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial

logger = logging.getLogger(__name__)
MAX_ALBUM_SIZE = 10


@dataclass(frozen=True)
class _Delivery:
    text: str | None = None
    photos: tuple[bytes, ...] = ()
    caption: str | None = None


class TelegramDeliveryQueue:
    def __init__(
        self,
        send_message: Callable[[str], None],
        send_photo: Callable[[bytes, str | None], None] | None = None,
        send_media_group: Callable[[Sequence[bytes], str | None], None] | None = None,
        retry_delays: Sequence[float] = (1, 3),
        max_pending: int = 16,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._send_message = send_message
        self._send_photo = send_photo
        self._send_media_group = send_media_group
        self._retry_delays = tuple(retry_delays)
        self._sleeper = sleeper
        self._queue: queue.Queue[_Delivery | None] = queue.Queue(maxsize=max_pending)
        self._start_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._closed = False

    def submit(self, text: str) -> bool:
        if self._closed or not text.strip():
            return False
        return self._submit(_Delivery(text=text))

    def submit_photos(
        self,
        photos: Sequence[bytes],
        caption: str | None = None,
    ) -> bool:
        photo_group = tuple(photos)
        if (
            self._closed
            or not photo_group
            or any(not photo for photo in photo_group)
            or self._send_photo is None
        ):
            return False
        if len(photo_group) > 1 and self._send_media_group is None:
            return False
        return self._submit(_Delivery(photos=photo_group, caption=caption))

    def _submit(self, delivery: _Delivery) -> bool:
        self._ensure_started()
        try:
            self._queue.put_nowait(delivery)
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
            delivery = self._queue.get()
            try:
                if delivery is None:
                    return
                self._deliver(delivery)
            finally:
                self._queue.task_done()
            if self._closed and self._queue.empty():
                return

    def _deliver(self, delivery: _Delivery) -> None:
        text = delivery.text
        if text is not None:
            self._send_with_retry(partial(self._send_message, text))
            return

        total = len(delivery.photos)
        for start in range(0, total, MAX_ALBUM_SIZE):
            photos = delivery.photos[start : start + MAX_ALBUM_SIZE]
            caption = delivery.caption
            if total > MAX_ALBUM_SIZE:
                end = start + len(photos)
                caption = (
                    f"{caption or 'Снимки задания'} ({start + 1}–{end} из {total})"
                )
            if len(photos) == 1:
                send_photo = self._send_photo
                assert send_photo is not None
                self._send_with_retry(partial(send_photo, photos[0], caption))
            else:
                send_media_group = self._send_media_group
                assert send_media_group is not None
                self._send_with_retry(partial(send_media_group, photos, caption))

    def _send_with_retry(self, send: Callable[[], None]) -> None:
        attempts = len(self._retry_delays) + 1
        for attempt in range(attempts):
            try:
                send()
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
