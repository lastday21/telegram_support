from __future__ import annotations

from typing import Any

import pytest

from app.interfaces.vk.sender import VkApiError, VkSender


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


def test_vk_sender_sends_text_to_configured_user():
    calls = []

    def post(url: str, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"response": 1})

    sender = VkSender("TOKEN", "114676356", http_post=post)
    sender.send_message("Ответ")

    assert calls[0][0].endswith("/messages.send")
    assert calls[0][1]["data"]["peer_id"] == "114676356"
    assert calls[0][1]["data"]["message"] == "Ответ"
    assert calls[0][1]["data"]["access_token"] == "TOKEN"


def test_vk_sender_uploads_and_sends_photo():
    calls = []

    def post(url: str, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/photos.getMessagesUploadServer"):
            return FakeResponse({"response": {"upload_url": "https://upload.vk/test"}})
        if url == "https://upload.vk/test":
            return FakeResponse({"photo": "data", "server": 1, "hash": "hash"})
        if url.endswith("/photos.saveMessagesPhoto"):
            return FakeResponse(
                {"response": [{"owner_id": 10, "id": 20, "access_key": "key"}]}
            )
        return FakeResponse({"response": 1})

    sender = VkSender("TOKEN", "114676356", http_post=post)
    sender.send_photo(b"PNG", "Подпись")

    assert calls[1][1]["files"]["photo"][1] == b"PNG"
    send_call = calls[-1][1]["data"]
    assert send_call["message"] == "Подпись"
    assert send_call["attachment"] == "photo10_20_key"


def test_vk_sender_hides_token_from_error():
    def post(_url: str, **_kwargs):
        return FakeResponse(
            {"error": {"error_code": 5, "error_msg": "User authorization failed"}}
        )

    sender = VkSender("VERY_SECRET", "1", http_post=post)

    with pytest.raises(VkApiError) as error:
        sender.send_message("Тест")

    assert "VERY_SECRET" not in str(error.value)
