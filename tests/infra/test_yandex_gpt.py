from src.infra.yandex_gpt import DEFAULT_SYSTEM, YandexGPTClient


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
        return _FakeResp(
            {"result": {"alternatives": [{"message": {"text": "ANSWER"}}]}}
        )

    client = YandexGPTClient(api_key="KEY", folder_id="FOLDER", http_post=_fake_http)

    out = client.solve_text("How to sort list?")

    assert out == "ANSWER"
    assert calls["json"]["messages"][1]["text"] == "How to sort list?"
    assert calls["json"]["messages"][0]["text"] == DEFAULT_SYSTEM


def test_solve_image_success():
    calls = {}

    def _fake_ocr(image):
        calls["ocr_called"] = image
        return "SELECT * FROM table;"

    def _fake_http(url, headers, json, timeout):
        calls["prompt"] = json["messages"][1]["text"]
        return _FakeResp(
            {"result": {"alternatives": [{"message": {"text": "SQL explanation"}}]}}
        )

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
    assert calls["ocr_called"] == b"bytes"


def test_solve_image_no_text():
    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        ocr_text_fn=lambda image: "",
    )

    assert client.solve_image(b"bytes") == "Не удалось распознать текст на изображении."
