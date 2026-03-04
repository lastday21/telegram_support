from src.interfaces.telegram import sender
from src.settings import Settings


def test_build_sender_uses_settings_credentials(monkeypatch):
    monkeypatch.setattr(
        sender,
        "get_settings",
        lambda: Settings(
            yc_api_key="KEY",
            yc_folder_id="FOLDER",
            tg_bot_token="BOT_TOKEN",
            tg_chat_id="CHAT_ID",
            mic_device=None,
            mix_device=None,
        ),
    )

    built = sender.build_sender()

    assert built.bot_token == "BOT_TOKEN"
    assert built.chat_id == "CHAT_ID"


def test_send_message_builds_sender_and_delegates(monkeypatch):
    calls = {}

    class _FakeSender:
        def send_message(self, text):
            calls["text"] = text

    monkeypatch.setattr(sender, "build_sender", lambda: _FakeSender())

    sender.send_message("hello")

    assert calls["text"] == "hello"


def test_send_photo_builds_sender_and_delegates(monkeypatch):
    calls = {}

    class _FakeSender:
        def send_photo(self, photo, caption=None):
            calls["photo"] = photo
            calls["caption"] = caption

    monkeypatch.setattr(sender, "build_sender", lambda: _FakeSender())

    sender.send_photo(b"PNG_BYTES", caption="prompt")

    assert calls["photo"] == b"PNG_BYTES"
    assert calls["caption"] == "prompt"
