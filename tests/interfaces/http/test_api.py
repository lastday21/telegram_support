from pathlib import Path

from fastapi.testclient import TestClient

from app.interfaces.http.api import MAX_AUDIO_SIZE, create_app

AUTH = {"Authorization": "Bearer SECRET"}


def test_audio_limit_allows_ten_minutes():
    ten_minutes_pcm = 10 * 60 * 16_000 * 2 + 44

    assert MAX_AUDIO_SIZE >= ten_minutes_pcm


def _build_client(calls: dict) -> TestClient:
    def transcribe(path: Path) -> str:
        calls["audio"] = path.read_bytes()
        return "Распознанный текст"

    application = create_app(
        access_token="SECRET",
        solve_text_fn=lambda text, model: (
            calls.update(text=text, model=model) or "Ответ"
        ),
        solve_image_fn=lambda image, prompt, model: (
            calls.update(image=image, prompt=prompt, model=model) or "Ответ по снимку"
        ),
        transcribe_fn=transcribe,
        send_message_fn=lambda text: calls.setdefault("message", text),
        send_photo_fn=lambda photo, caption: calls.update(photo=photo, caption=caption),
    )
    return TestClient(application)


def test_health_does_not_require_token():
    client = _build_client({})

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_ping_requires_token():
    client = _build_client({})

    denied = client.get("/v1/ping")
    allowed = client.get("/v1/ping", headers=AUTH)

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json() == {"status": "ok"}


def test_text_endpoint_requires_valid_token():
    calls = {}
    client = _build_client(calls)

    denied = client.post("/v1/text", json={"text": "Вопрос"})
    allowed = client.post(
        "/v1/text",
        headers=AUTH,
        json={"text": "Вопрос", "model": "aliceai-llm/latest"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json() == {"answer": "Ответ"}
    assert calls["text"] == "Вопрос"
    assert calls["model"] == "aliceai-llm/latest"


def test_image_and_audio_are_passed_to_services():
    calls = {}
    client = _build_client(calls)

    image_response = client.post(
        "/v1/image",
        headers=AUTH,
        data={"prompt": "Объясни", "model": "deepseek-v32/latest"},
        files={"image": ("screen.png", b"PNG", "image/png")},
    )
    audio_response = client.post(
        "/v1/transcribe",
        headers=AUTH,
        files={"audio": ("voice.wav", b"WAV", "audio/wav")},
    )

    assert image_response.json() == {"answer": "Ответ по снимку"}
    assert audio_response.json() == {"text": "Распознанный текст"}
    assert calls["image"] == b"PNG"
    assert calls["prompt"] == "Объясни"
    assert calls["model"] == "deepseek-v32/latest"
    assert calls["audio"] == b"WAV"


def test_unknown_model_is_rejected():
    client = _build_client({})

    response = client.post(
        "/v1/text",
        headers=AUTH,
        json={"text": "Вопрос", "model": "unknown/latest"},
    )

    assert response.status_code == 422


def test_telegram_actions_are_proxied():
    calls = {}
    client = _build_client(calls)

    message_response = client.post(
        "/v1/telegram/message",
        headers=AUTH,
        json={"text": "Сообщение"},
    )
    photo_response = client.post(
        "/v1/telegram/photo",
        headers=AUTH,
        data={"caption": "Подпись"},
        files={"photo": ("screen.png", b"PNG", "image/png")},
    )

    assert message_response.json() == {"sent": True}
    assert photo_response.json() == {"sent": True}
    assert calls["message"] == "Сообщение"
    assert calls["photo"] == b"PNG"
    assert calls["caption"] == "Подпись"
