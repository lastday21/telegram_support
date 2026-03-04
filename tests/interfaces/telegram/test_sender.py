from app.interfaces.telegram.sender import TelegramSender


class _FakeResp:
    def __init__(self, calls):
        self.calls = calls

    def raise_for_status(self):
        self.calls["raised"] = True


def test_send_photo_with_bytes():
    calls = {}

    def _fake_http(url, data=None, files=None, timeout=None):
        calls.update(url=url, data=data, files=files, timeout=timeout)
        return _FakeResp(calls)

    sender = TelegramSender(bot_token="TOKEN123", chat_id=777, http_post=_fake_http)

    sender.send_photo(b"PNG_BYTES", caption="hi!")

    assert "/sendPhoto" in calls["url"]
    assert calls["data"]["chat_id"] == 777
    assert calls["data"]["caption"] == "hi!"
    name, payload = calls["files"]["photo"]
    assert payload == b"PNG_BYTES" and name.endswith(".png")
    assert calls["raised"] and calls["timeout"] == 30


def test_send_message():
    calls = {}

    def _fake_http(url, data=None, files=None, timeout=None):
        calls.update(url=url, data=data, files=files, timeout=timeout)
        return _FakeResp(calls)

    sender = TelegramSender(bot_token="TOKEN123", chat_id=777, http_post=_fake_http)

    sender.send_message("hello world")

    assert "/sendMessage" in calls["url"]
    assert calls["data"] == {"chat_id": 777, "text": "hello world"}
    assert calls.get("files") is None
    assert calls["raised"] and calls["timeout"] == 30
