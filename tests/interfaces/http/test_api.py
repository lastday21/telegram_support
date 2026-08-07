from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.request_guard import RequestGuard, RequestGuardConfig
from app.domain.yandex_queue import YandexRequestQueue
from app.infra.readiness import ExternalReadinessChecker, ReadinessReport
from app.infra.yandex_resilience import YandexCircuitOpenError
from app.interfaces.http.api import (
    MAX_AUDIO_SIZE,
    MAX_CONTEXT_TEXT_SIZE,
    create_app,
)

AUTH = {"Authorization": "Bearer SECRET"}


class ReadyChecker(ExternalReadinessChecker):
    def __init__(self) -> None:
        pass

    def check(self) -> ReadinessReport:
        return ReadinessReport(
            ready=True,
            checks={"settings": "ok", "yandex": "ok", "telegram": "ok"},
        )


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
        solve_image_fn=lambda image, prompt, context_text, model: (
            calls.update(
                image=image,
                prompt=prompt,
                context_text=context_text,
                model=model,
            )
            or "Ответ по снимку"
        ),
        solve_vision_image_fn=lambda image, prompt: (
            calls.update(vision_image=image, vision_prompt=prompt)
            or "Ответ зрительной модели"
        ),
        recognize_image_fn=lambda image: (
            calls.update(recognized_image=image) or "Распознанный снимок"
        ),
        transcribe_fn=transcribe,
        send_messenger_message_fn=lambda text, chat_id: calls.update(
            messenger_message=text,
            messenger_message_chat_id=chat_id,
        ),
        send_messenger_photo_fn=lambda photo, caption, chat_id: calls.update(
            messenger_photo=photo,
            messenger_caption=caption,
            messenger_photo_chat_id=chat_id,
        ),
        send_messenger_media_group_fn=lambda photos, caption, chat_id: calls.update(
            messenger_photos=photos,
            messenger_album_caption=caption,
            messenger_album_chat_id=chat_id,
        ),
        yandex_queue=YandexRequestQueue(),
        readiness_checker=ReadyChecker(),
    )
    return TestClient(application)


def test_health_does_not_require_token():
    client = _build_client({})

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"settings": "ok", "yandex": "ok", "telegram": "ok"},
        "queue": {
            "active": 0,
            "waiting": 0,
            "max_concurrent": 2,
            "max_waiting": 8,
        },
    }


def test_live_stays_available_when_external_service_is_down():
    class UnavailableChecker(ReadyChecker):
        def check(self) -> ReadinessReport:
            return ReadinessReport(
                ready=False,
                checks={
                    "settings": "ok",
                    "yandex": "unavailable",
                    "telegram": "ok",
                },
            )

    client = TestClient(
        create_app(
            access_token="SECRET",
            readiness_checker=UnavailableChecker(),
        )
    )

    assert client.get("/live").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 503


def test_protected_ping_requires_token():
    client = _build_client({})

    denied = client.get("/v1/ping")
    allowed = client.get("/v1/ping", headers=AUTH)

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "ok"


def test_health_returns_service_unavailable_when_dependency_is_down():
    class UnavailableChecker(ReadyChecker):
        def check(self) -> ReadinessReport:
            return ReadinessReport(
                ready=False,
                checks={
                    "settings": "ok",
                    "yandex": "unavailable",
                    "telegram": "ok",
                },
            )

    application = create_app(
        access_token="SECRET", readiness_checker=UnavailableChecker()
    )
    response = TestClient(application).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["checks"]["yandex"] == "unavailable"


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


def test_image_ocr_and_audio_are_passed_to_services():
    calls = {}
    client = _build_client(calls)

    image_response = client.post(
        "/v1/image",
        headers=AUTH,
        data={
            "prompt": "Объясни",
            "context_text": "Большой исходный текст",
            "model": "deepseek-v32/latest",
        },
        files={"image": ("screen.png", b"PNG", "image/png")},
    )
    vision_response = client.post(
        "/v1/vision",
        headers=AUTH,
        data={"prompt": "Реши по изображению"},
        files={"image": ("screen.png", b"VISION_PNG", "image/png")},
    )
    ocr_response = client.post(
        "/v1/ocr",
        headers=AUTH,
        files={"image": ("screen.png", b"PNG2", "image/png")},
    )
    audio_response = client.post(
        "/v1/transcribe",
        headers=AUTH,
        files={"audio": ("voice.wav", b"WAV", "audio/wav")},
    )

    assert image_response.json() == {"answer": "Ответ по снимку"}
    assert vision_response.json() == {"answer": "Ответ зрительной модели"}
    assert ocr_response.json() == {"text": "Распознанный снимок"}
    assert audio_response.json() == {"text": "Распознанный текст"}
    assert calls["image"] == b"PNG"
    assert calls["prompt"] == "Объясни"
    assert calls["context_text"] == "Большой исходный текст"
    assert calls["model"] == "deepseek-v32/latest"
    assert calls["vision_image"] == b"VISION_PNG"
    assert calls["vision_prompt"] == "Реши по изображению"
    assert calls["recognized_image"] == b"PNG2"
    assert calls["audio"] == b"WAV"


def test_image_context_size_is_limited():
    client = _build_client({})

    response = client.post(
        "/v1/image",
        headers=AUTH,
        data={
            "prompt": "Объясни",
            "context_text": "x" * (MAX_CONTEXT_TEXT_SIZE + 1),
        },
        files={"image": ("screen.png", b"PNG", "image/png")},
    )

    assert response.status_code == 422


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
        json={"text": "Сообщение", "chat_id": "123456"},
    )
    photo_response = client.post(
        "/v1/telegram/photo",
        headers=AUTH,
        data={"caption": "Подпись", "chat_id": "-123456"},
        files={"photo": ("screen.png", b"PNG", "image/png")},
    )
    album_response = client.post(
        "/v1/telegram/media-group",
        headers=AUTH,
        data={"caption": "Альбом", "chat_id": "-123456"},
        files=[
            ("photos", ("page-1.png", b"PAGE_1", "image/png")),
            ("photos", ("page-2.png", b"PAGE_2", "image/png")),
        ],
    )

    assert message_response.json() == {"sent": True}
    assert photo_response.json() == {"sent": True}
    assert album_response.json() == {"sent": True}
    assert calls["messenger_message"] == "Сообщение"
    assert calls["messenger_message_chat_id"] == "123456"
    assert calls["messenger_photo"] == b"PNG"
    assert calls["messenger_caption"] == "Подпись"
    assert calls["messenger_photo_chat_id"] == "-123456"
    assert calls["messenger_photos"] == [b"PAGE_1", b"PAGE_2"]
    assert calls["messenger_album_caption"] == "Альбом"
    assert calls["messenger_album_chat_id"] == "-123456"


def test_messenger_actions_are_proxied():
    calls = {}
    client = _build_client(calls)

    message_response = client.post(
        "/v1/messengers/message",
        headers=AUTH,
        json={"text": "Сообщение", "chat_id": "123456"},
    )
    photo_response = client.post(
        "/v1/messengers/photo",
        headers=AUTH,
        data={"caption": "Подпись", "chat_id": "-123456"},
        files={"photo": ("screen.png", b"PNG", "image/png")},
    )
    album_response = client.post(
        "/v1/messengers/media-group",
        headers=AUTH,
        data={"caption": "Альбом", "chat_id": "-123456"},
        files=[
            ("photos", ("page-1.png", b"PAGE_1", "image/png")),
            ("photos", ("page-2.png", b"PAGE_2", "image/png")),
        ],
    )

    assert message_response.json() == {"sent": True}
    assert photo_response.json() == {"sent": True}
    assert album_response.json() == {"sent": True}
    assert calls["messenger_message"] == "Сообщение"
    assert calls["messenger_message_chat_id"] == "123456"
    assert calls["messenger_photo"] == b"PNG"
    assert calls["messenger_caption"] == "Подпись"
    assert calls["messenger_photos"] == [b"PAGE_1", b"PAGE_2"]
    assert calls["messenger_album_caption"] == "Альбом"


def test_yandex_failure_is_returned_as_bad_gateway_without_internal_details():
    def failed_text(_text: str, _model: str | None) -> str:
        raise RuntimeError("SECRET INTERNAL DETAILS")

    application = create_app(access_token="SECRET", solve_text_fn=failed_text)
    client = TestClient(application)

    response = client.post(
        "/v1/text",
        headers=AUTH,
        json={"text": "Подробный вопрос"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Не удалось получить ответ от Яндекса"}
    assert "INTERNAL" not in response.text


def test_open_yandex_circuit_is_returned_as_service_unavailable():
    def blocked_text(_text: str, _model: str | None) -> str:
        raise YandexCircuitOpenError("blocked")

    client = TestClient(
        create_app(
            access_token="SECRET",
            solve_text_fn=blocked_text,
            readiness_checker=ReadyChecker(),
        )
    )

    response = client.post(
        "/v1/text",
        headers=AUTH,
        json={"text": "Подробный вопрос"},
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"


def test_http_guard_limits_rate_and_request_size():
    config = RequestGuardConfig(
        max_concurrent=2,
        requests_per_window=2,
        rate_window_seconds=60,
        max_body_bytes=20,
        auth_failure_limit=5,
        auth_failure_window_seconds=60,
        auth_block_seconds=300,
    )
    client = TestClient(
        create_app(
            access_token="SECRET",
            readiness_checker=ReadyChecker(),
            request_guard=RequestGuard(config),
        )
    )

    assert client.get("/v1/ping", headers=AUTH).status_code == 200
    assert client.get("/v1/ping", headers=AUTH).status_code == 200
    assert client.get("/v1/ping", headers=AUTH).status_code == 429

    another_client = TestClient(
        create_app(
            access_token="SECRET",
            readiness_checker=ReadyChecker(),
            request_guard=RequestGuard(config),
        )
    )
    response = another_client.post(
        "/v1/text",
        headers=AUTH,
        content=b"x" * 21,
    )
    assert response.status_code == 413


def test_http_guard_blocks_repeated_invalid_tokens():
    config = RequestGuardConfig(
        max_concurrent=2,
        requests_per_window=20,
        rate_window_seconds=60,
        max_body_bytes=1024,
        auth_failure_limit=2,
        auth_failure_window_seconds=60,
        auth_block_seconds=30,
    )
    client = TestClient(
        create_app(
            access_token="SECRET",
            readiness_checker=ReadyChecker(),
            request_guard=RequestGuard(config),
        )
    )

    assert client.get("/v1/ping").status_code == 401
    blocked = client.get("/v1/ping")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "30"
    assert client.get("/v1/ping", headers=AUTH).status_code == 429
