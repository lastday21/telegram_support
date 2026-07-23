from app.domain.telegram_delivery import TelegramDeliveryQueue


def test_delivery_retries_and_then_succeeds():
    attempts = []
    delays = []

    def send(text):
        attempts.append(text)
        if len(attempts) < 3:
            raise RuntimeError("temporary")

    delivery = TelegramDeliveryQueue(
        send,
        retry_delays=(1, 2),
        sleeper=delays.append,
    )

    delivery._send_with_retry(lambda: send("Ответ"))

    assert attempts == ["Ответ", "Ответ", "Ответ"]
    assert delays == [1, 2]


def test_delivery_failure_does_not_escape():
    delivery = TelegramDeliveryQueue(
        lambda _text: (_ for _ in ()).throw(RuntimeError("telegram unavailable")),
        retry_delays=(),
    )

    delivery._send_with_retry(lambda: delivery._send_message("Ответ"))


def test_delivery_groups_photos_by_ten_and_keeps_order():
    calls = []
    delivery = TelegramDeliveryQueue(
        lambda text: calls.append(("message", text)),
        send_photo=lambda photo, caption: calls.append(("photo", (photo,), caption)),
        send_media_group=lambda photos, caption: calls.append(
            ("album", tuple(photos), caption)
        ),
        retry_delays=(),
    )
    photos = tuple(f"PAGE_{index}".encode() for index in range(1, 13))

    assert delivery.submit_photos(photos, "Снимки задания") is True
    delivery._queue.join()

    assert calls == [
        (
            "album",
            photos[:10],
            "Снимки задания (1–10 из 12)",
        ),
        (
            "album",
            photos[10:],
            "Снимки задания (11–12 из 12)",
        ),
    ]


def test_delivery_sends_one_photo_without_album():
    calls = []
    delivery = TelegramDeliveryQueue(
        lambda _text: None,
        send_photo=lambda photo, caption: calls.append((photo, caption)),
        send_media_group=lambda _photos, _caption: None,
        retry_delays=(),
    )

    assert delivery.submit_photos([b"SCREEN"], "Снимок задания") is True
    delivery._queue.join()

    assert calls == [(b"SCREEN", "Снимок задания")]
