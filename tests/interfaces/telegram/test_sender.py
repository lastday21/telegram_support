"""
Проверяем send_photo() и send_message() в interfaces.telegram.sender.
"""

import sys
import types
import importlib
import pytest


@pytest.fixture
def sender(monkeypatch):
    """Возвращает (module, call_dict) с «свежим» sender.py и мок-HTTP."""
    calls: dict[str, object] = {}


    fake_settings = types.ModuleType("settings")
    fake_settings.TG_BOT_TOKEN = "TOKEN123"
    fake_settings.TG_CHAT_ID = 777
    sys.modules["settings"] = fake_settings
    sys.modules["src.settings"] = fake_settings

    class _FakeResp:
        def raise_for_status(self):
            calls["raised"] = True

    def _fake_http(url, data=None, files=None, timeout=None):
        calls.update(url=url, data=data, files=files, timeout=timeout)
        return _FakeResp()

    fake_requests = types.ModuleType("requests")
    fake_requests.post = _fake_http
    fake_requests.get = _fake_http
    sys.modules["requests"] = fake_requests


    sys.modules.pop("src.interfaces.telegram.sender", None)   # ключевой сброс
    mod = importlib.import_module("src.interfaces.telegram.sender")

    return mod, calls


def test_send_photo_with_bytes(sender):
    mod, call = sender

    mod.send_photo(b"PNG_BYTES", caption="hi!")

    assert "/sendPhoto" in call["url"]
    assert call["data"]["chat_id"] == 777
    assert call["data"]["caption"] == "hi!"
    name, payload = call["files"]["photo"]
    assert payload == b"PNG_BYTES" and name.endswith(".png")
    assert call["raised"] and call["timeout"] == 30


def test_send_message(sender):
    mod, call = sender

    mod.send_message("hello world")

    assert "/sendMessage" in call["url"]
    assert call["data"] == {"chat_id": 777, "text": "hello world"}
    assert call["files"] is None
    assert call["raised"] and call["timeout"] == 30
