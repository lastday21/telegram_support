from src.infra.yandex_gpt import DEFAULT_SYSTEM, YandexGPTClient


class _FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeImg:
    pass


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

    def _fake_open(fp):
        calls["image_opened"] = True
        return _FakeImg()

    def _fake_ocr(img, lang, config):
        calls["ocr_called"] = (img, lang, config)
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
        image_open=_fake_open,
        ocr_to_string=_fake_ocr,
    )

    result = client.solve_image(b"bytes", prompt="Объясни SQL")

    assert result == "SQL explanation"
    assert "Объясни SQL" in calls["prompt"]
    assert "SELECT *" in calls["prompt"]
    assert calls.get("ocr_called")
    assert calls.get("image_opened")


def test_solve_image_no_text():
    client = YandexGPTClient(
        api_key="KEY",
        folder_id="FOLDER",
        image_open=lambda fp: _FakeImg(),
        ocr_to_string=lambda *a, **kw: "",
    )

    assert client.solve_image(b"bytes") == "Не удалось распознать текст на изображении."
