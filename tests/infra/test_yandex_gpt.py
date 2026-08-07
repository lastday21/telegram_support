import base64

import pytest

from app.infra.yandex_gpt import (
    API_URL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM,
    DEFAULT_VISION_MODEL,
    YandexGPTClient,
    YandexServiceError,
)


class _FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_solve_text_too_short():
    client = YandexGPTClient(api_key="KEY", folder_id="FOLDER")
    assert (
        client.solve_text("ok") == "Слишком короткий запрос (нужно больше контекста)."
    )


def test_solve_text_calls_gpt():
    calls = {}

    def _fake_http(url, headers, json, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        calls["timeout"] = timeout
        return _FakeResp({"choices": [{"message": {"content": "ANSWER"}}]})

    client = YandexGPTClient(api_key="KEY", folder_id="FOLDER", http_post=_fake_http)

    out = client.solve_text("How to sort list?")

    assert out == "ANSWER"
    assert calls["url"] == API_URL
    assert calls["headers"]["OpenAI-Project"] == "FOLDER"
    assert calls["timeout"] == 20
    assert calls["json"]["model"] == f"gpt://FOLDER/{DEFAULT_MODEL}"
    assert calls["json"]["messages"][1]["content"] == "How to sort list?"
    assert calls["json"]["messages"][0]["content"] == DEFAULT_SYSTEM


def test_solve_image_success():
    calls = {}

    def _fake_ocr(image):
        calls["ocr_called"] = image
        return "SELECT * FROM table;"

    def _fake_http(url, headers, json, timeout):
        calls["prompt"] = json["messages"][1]["content"]
        calls["temperature"] = json["temperature"]
        return _FakeResp({"choices": [{"message": {"content": "SQL explanation"}}]})

    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        http_post=_fake_http,
        ocr_text_fn=_fake_ocr,
    )

    result = client.solve_image(b"bytes", prompt="Объясни SQL")

    assert result == "SQL explanation"
    assert "Объясни SQL" in calls["prompt"]
    assert "SELECT *" in calls["prompt"]
    assert calls["temperature"] == 0
    assert calls["ocr_called"] == b"bytes"


def test_solve_image_uses_collected_text_as_context():
    calls = {}

    def _fake_http(url, headers, json, timeout):
        calls["prompt"] = json["messages"][1]["content"]
        return _FakeResp({"choices": [{"message": {"content": "Ответ"}}]})

    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        http_post=_fake_http,
        ocr_text_fn=lambda _image: "Как звали героя?",
    )

    result = client.solve_image(
        b"bytes",
        prompt="Ответь на вопрос",
        context_text="Героя звали Алексей.",
    )

    assert result == "Ответ"
    assert "<СОБРАННЫЙ_ТЕКСТ>" in calls["prompt"]
    assert "Героя звали Алексей." in calls["prompt"]
    assert "<ТЕКУЩИЙ_СНИМОК>" in calls["prompt"]
    assert "Как звали героя?" in calls["prompt"]


def test_solve_image_no_text():
    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        ocr_text_fn=lambda image: "",
    )

    assert client.solve_image(b"bytes") == "Не удалось распознать текст на изображении."


def test_vision_model_receives_one_image_and_prompt_without_ocr():
    calls = {}

    def fail_ocr(_image):
        raise AssertionError("Распознавание текста не должно вызываться")

    def fake_http(url, headers, json, timeout):
        calls.update(url=url, headers=headers, json=json, timeout=timeout)
        return _FakeResp({"choices": [{"message": {"content": "x = 2"}}]})

    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        model=DEFAULT_VISION_MODEL,
        http_post=fake_http,
        ocr_text_fn=fail_ocr,
    )

    answer = client.solve_vision_image(b"PNG_BYTES", "Реши уравнение")

    assert answer == "x = 2"
    assert calls["json"]["model"] == f"gpt://FOLDER/{DEFAULT_VISION_MODEL}"
    assert calls["json"]["temperature"] == 0
    user_content = calls["json"]["messages"][1]["content"]
    assert user_content[0] == {"type": "text", "text": "Реши уравнение"}
    assert len(user_content) == 2
    image_url = user_content[1]["image_url"]["url"]
    prefix, encoded_image = image_url.split(",", maxsplit=1)
    assert prefix == "data:image/png;base64"
    assert base64.b64decode(encoded_image) == b"PNG_BYTES"


def test_full_model_uri_is_used_as_is():
    model_uri = "gpt://ANOTHER_FOLDER/aliceai-llm/latest"
    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        model=model_uri,
    )

    assert client.model_uri == model_uri


def test_service_error_does_not_become_answer_or_expose_details():
    def _failed_http(*_args, **_kwargs):
        raise RuntimeError("SECRET INTERNAL DETAILS")

    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        http_post=_failed_http,
    )

    with pytest.raises(YandexServiceError) as error:
        client.solve_text("Подробный вопрос")

    assert str(error.value) == "Не удалось получить ответ от Яндекса"
    assert "SECRET" not in str(error.value)
