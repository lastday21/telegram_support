from pathlib import Path

from app.infra.remote_client import RemoteServiceClient


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_remote_client_sends_token_and_text():
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return _FakeResponse({"answer": "Ответ"})

    client = RemoteServiceClient(
        "https://helper.example/", "SECRET", http_post=fake_post
    )

    assert client.solve_text("Вопрос") == "Ответ"
    assert calls["url"] == "https://helper.example/v1/text"
    assert calls["kwargs"]["headers"] == {"Authorization": "Bearer SECRET"}
    assert calls["kwargs"]["json"] == {"text": "Вопрос"}


def test_remote_client_sends_audio_file(tmp_path: Path):
    wav_path = tmp_path / "voice.wav"
    wav_path.write_bytes(b"WAV")
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["audio"] = kwargs["files"]["audio"][1].read()
        return _FakeResponse({"text": "Речь"})

    client = RemoteServiceClient("http://server", "SECRET", http_post=fake_post)

    assert client.transcribe(wav_path) == "Речь"
    assert calls == {"url": "http://server/v1/transcribe", "audio": b"WAV"}


def test_remote_client_proxies_telegram_photo():
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["data"] = kwargs["data"]
        calls["photo"] = kwargs["files"]["photo"][1]
        return _FakeResponse({"sent": True})

    client = RemoteServiceClient("http://server", "SECRET", http_post=fake_post)
    client.send_photo(b"PNG", "Подпись")

    assert calls == {
        "url": "http://server/v1/telegram/photo",
        "data": {"caption": "Подпись"},
        "photo": b"PNG",
    }
