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

    delivery._send_with_retry("Ответ")

    assert attempts == ["Ответ", "Ответ", "Ответ"]
    assert delays == [1, 2]


def test_delivery_failure_does_not_escape():
    delivery = TelegramDeliveryQueue(
        lambda _text: (_ for _ in ()).throw(RuntimeError("telegram unavailable")),
        retry_delays=(),
    )

    delivery._send_with_retry("Ответ")
