from threading import Event, Thread

import pytest

from app.interfaces.messengers import sender


def test_vk_receives_message_when_telegram_is_unavailable(monkeypatch):
    calls = []
    monkeypatch.setattr(
        sender,
        "send_telegram_message",
        lambda *_args: (_ for _ in ()).throw(ConnectionError("blocked")),
    )
    monkeypatch.setattr(sender, "send_vk_message", lambda text: calls.append(text))
    monkeypatch.setattr(sender, "_vk_enabled", lambda: True)

    sender.send_message("Ответ")

    assert calls == ["Ответ"]


def test_delivery_fails_only_when_all_channels_are_unavailable(monkeypatch):
    monkeypatch.setattr(
        sender,
        "send_telegram_message",
        lambda *_args: (_ for _ in ()).throw(ConnectionError("telegram")),
    )
    monkeypatch.setattr(
        sender,
        "send_vk_message",
        lambda *_args: (_ for _ in ()).throw(ConnectionError("vk")),
    )
    monkeypatch.setattr(sender, "_vk_enabled", lambda: True)

    with pytest.raises(sender.MessengerDeliveryError):
        sender.send_message("Ответ")


def test_slow_telegram_does_not_delay_vk(monkeypatch):
    release_telegram = Event()
    vk_called = Event()

    monkeypatch.setattr(
        sender,
        "send_telegram_message",
        lambda *_args: release_telegram.wait(2),
    )
    monkeypatch.setattr(
        sender,
        "send_vk_message",
        lambda _text: vk_called.set(),
    )
    monkeypatch.setattr(sender, "_vk_enabled", lambda: True)

    delivery = Thread(target=sender.send_message, args=("Ответ",))
    delivery.start()
    try:
        assert vk_called.wait(0.5) is True
    finally:
        release_telegram.set()
        delivery.join(timeout=2)

    assert delivery.is_alive() is False
