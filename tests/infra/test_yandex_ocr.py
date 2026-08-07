import base64

import pytest

from app.infra.yandex_ocr import DEFAULT_LANGUAGES, DEFAULT_MODEL, YandexOCRClient


class _FakeResp:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.text = str(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_recognize_text_with_bytes():
    calls = {}

    def _fake_http(url, headers, json, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        calls["timeout"] = timeout
        return _FakeResp({"textAnnotation": {"fullText": "recognized text\n"}})

    client = YandexOCRClient(api_key="KEY", http_post=_fake_http)

    result = client.recognize_text(b"PNG_BYTES")

    assert result == "recognized text"
    assert calls["headers"]["Authorization"] == "Api-Key KEY"
    assert calls["json"]["mimeType"] == "image/png"
    assert calls["json"]["languageCodes"] == list(DEFAULT_LANGUAGES)
    assert calls["json"]["model"] == DEFAULT_MODEL
    assert calls["json"]["content"] == base64.b64encode(b"PNG_BYTES").decode("ascii")
    assert calls["timeout"] == 20


def test_recognize_text_with_path(tmp_path):
    calls = {}

    def _fake_http(url, headers, json, timeout):
        calls["json"] = json
        return _FakeResp({"textAnnotation": {"fullText": "from file"}})

    img_path = tmp_path / "screen.png"
    img_path.write_bytes(b"FILE_BYTES")

    client = YandexOCRClient(api_key="KEY", http_post=_fake_http)

    result = client.recognize_text(str(img_path))

    assert result == "from file"
    assert calls["json"]["mimeType"] == "image/png"
    assert calls["json"]["content"] == base64.b64encode(b"FILE_BYTES").decode("ascii")


def test_recognize_text_rejects_unsupported_extension(tmp_path):
    bad_path = tmp_path / "screen.bmp"
    bad_path.write_bytes(b"BMP")
    client = YandexOCRClient(api_key="KEY")

    with pytest.raises(RuntimeError, match="Unsupported image format"):
        client.recognize_text(bad_path)


def test_recognize_text_logs_empty_response(capsys):
    client = YandexOCRClient(
        api_key="KEY",
        http_post=lambda url, headers, json, timeout: _FakeResp(
            {"textAnnotation": {"fullText": ""}, "result": {"pages": []}}
        ),
    )

    result = client.recognize_text(b"PNG_BYTES")
    out = capsys.readouterr().out

    assert result == ""
    assert "[ocr] http status: 200" in out
    assert "[ocr] empty OCR response:" in out


def test_recognize_text_reads_nested_blocks_when_full_text_is_empty():
    client = YandexOCRClient(
        api_key="KEY",
        http_post=lambda url, headers, json, timeout: _FakeResp(
            {
                "result": {
                    "textAnnotation": {
                        "fullText": "",
                        "blocks": [
                            {
                                "lines": [
                                    {"text": "Development"},
                                    {"text": "Question 1"},
                                ]
                            },
                            {
                                "lines": [
                                    {"words": [{"text": "Explain"}, {"text": "SQL"}]}
                                ]
                            },
                        ],
                    }
                }
            }
        ),
    )

    result = client.recognize_text(b"PNG_BYTES")

    assert result == "Development\nQuestion 1\n\nExplain SQL"
