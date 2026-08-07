from pathlib import Path

from app.infra import remote_client
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
    assert calls["kwargs"]["json"] == {
        "text": "Вопрос",
        "model": "qwen3-235b-a22b-fp8/latest",
    }


def test_remote_client_can_change_model():
    calls = {}

    def fake_post(url, **kwargs):
        calls["json"] = kwargs["json"]
        return _FakeResponse({"answer": "Ответ"})

    client = RemoteServiceClient("http://server", "SECRET", http_post=fake_post)
    client.set_model("aliceai-llm/latest")

    client.solve_text("Вопрос")

    assert calls["json"]["model"] == "aliceai-llm/latest"


def test_remote_client_recognizes_image_and_sends_reading_context():
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/v1/ocr"):
            return _FakeResponse({"text": "Распознанный текст"})
        return _FakeResponse({"answer": "Ответ"})

    client = RemoteServiceClient("http://server", "SECRET", http_post=fake_post)

    assert client.recognize_image(b"PAGE") == "Распознанный текст"
    assert (
        client.solve_image(b"QUESTION", "Ответь", "Большой исходный текст") == "Ответ"
    )
    assert calls[0][0] == "http://server/v1/ocr"
    assert calls[0][1]["files"]["image"][1] == b"PAGE"
    assert calls[1][0] == "http://server/v1/image"
    assert calls[1][1]["data"] == {
        "prompt": "Ответь",
        "model": "qwen3-235b-a22b-fp8/latest",
        "context_text": "Большой исходный текст",
    }
    assert calls[1][1]["files"]["image"][1] == b"QUESTION"


def test_remote_client_sends_single_image_to_vision_endpoint():
    calls = {}

    def fake_post(url, **kwargs):
        calls.update(url=url, kwargs=kwargs)
        return _FakeResponse({"answer": "Ответ по изображению"})

    client = RemoteServiceClient("http://server", "SECRET", http_post=fake_post)

    answer = client.solve_vision_image(b"ONE_SCREEN", "Реши задачу")

    assert answer == "Ответ по изображению"
    assert calls["url"] == "http://server/v1/vision"
    assert calls["kwargs"]["data"] == {"prompt": "Реши задачу"}
    assert calls["kwargs"]["files"] == {
        "image": ("screenshot.png", b"ONE_SCREEN", "image/png")
    }


def test_remote_client_sends_audio_file(tmp_path: Path):
    wav_path = tmp_path / "voice.wav"
    wav_path.write_bytes(b"WAV")
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["audio"] = kwargs["files"]["audio"][1].read()
        calls["timeout"] = kwargs["timeout"]
        return _FakeResponse({"text": "Речь"})

    client = RemoteServiceClient("http://server", "SECRET", http_post=fake_post)

    assert client.transcribe(wav_path) == "Речь"
    assert calls == {
        "url": "http://server/v1/transcribe",
        "audio": b"WAV",
        "timeout": 600,
    }


def test_remote_client_proxies_photo_to_all_messengers():
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["data"] = kwargs["data"]
        calls["photo"] = kwargs["files"]["photo"][1]
        return _FakeResponse({"sent": True})

    client = RemoteServiceClient("http://server", "SECRET", http_post=fake_post)
    client.send_photo(b"PNG", "Подпись")

    assert calls == {
        "url": "http://server/v1/messengers/photo",
        "data": {"caption": "Подпись"},
        "photo": b"PNG",
    }


def test_remote_client_proxies_media_group_to_all_messengers():
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["data"] = kwargs["data"]
        calls["photos"] = [file[1][1] for file in kwargs["files"]]
        return _FakeResponse({"sent": True})

    client = RemoteServiceClient(
        "http://server",
        "SECRET",
        http_post=fake_post,
        tg_chat_id="-123456",
    )
    client.send_media_group([b"PAGE_1", b"PAGE_2"], "Снимки задания")

    assert calls == {
        "url": "http://server/v1/messengers/media-group",
        "data": {"caption": "Снимки задания", "chat_id": "-123456"},
        "photos": [b"PAGE_1", b"PAGE_2"],
    }


def test_remote_client_sends_message_to_all_messengers():
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs["json"]
        return _FakeResponse({"sent": True})

    client = RemoteServiceClient(
        "http://server", "SECRET", http_post=fake_post, tg_chat_id="-123456"
    )
    client.send_message("Ответ")

    assert calls == {
        "url": "http://server/v1/messengers/message",
        "json": {"text": "Ответ", "chat_id": "-123456"},
    }


def test_remote_client_checks_protected_ping():
    calls = {}

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return _FakeResponse({"status": "ok"})

    client = RemoteServiceClient(
        "http://server",
        "SECRET",
        http_get=fake_get,
    )

    assert client.ping() is True
    assert calls == {
        "url": "http://server/v1/ping",
        "kwargs": {
            "headers": {"Authorization": "Bearer SECRET"},
            "timeout": 5,
        },
    }


def test_remote_client_bypasses_system_proxy_for_loopback(monkeypatch):
    class _FakeSession:
        trust_env = True

        def post(self, *_args, **_kwargs):
            raise AssertionError("not called")

        def get(self, *_args, **_kwargs):
            return _FakeResponse({"status": "ok"})

    session = _FakeSession()
    monkeypatch.setattr(remote_client.requests, "Session", lambda: session)

    client = RemoteServiceClient("http://127.0.0.1:8000", "SECRET")

    assert session.trust_env is False
    assert client.ping() is True


def test_remote_client_keeps_system_proxy_for_external_server(monkeypatch):
    class _FakeSession:
        trust_env = True

        def post(self, *_args, **_kwargs):
            raise AssertionError("not called")

        def get(self, *_args, **_kwargs):
            raise AssertionError("not called")

    session = _FakeSession()
    monkeypatch.setattr(remote_client.requests, "Session", lambda: session)

    RemoteServiceClient("https://helper.example.ru", "SECRET")

    assert session.trust_env is True
