import types

import pytest

from app.infra.yandex_stt import YandexSTTClient

_FAKE_RAW = b"\x00\x01" * 100


class _FakeWave:
    def __init__(self, ok: bool):
        self.ok = ok

    def getframerate(self):
        return 16000

    def getnchannels(self):
        return 1 if self.ok else 2

    def getsampwidth(self):
        return 2

    def getnframes(self):
        return len(_FAKE_RAW) // 2

    def readframes(self, n):
        return _FAKE_RAW

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeResp:
    status_code = 200
    text = ""

    def json(self):
        return {"result": "привет"}


def test_transcribe_success(monkeypatch, tmp_path):
    calls = {}

    def _fake_wave_open(path, mode="rb"):
        return _FakeWave(ok=True)

    def _fake_post(url, headers, data, timeout):
        calls["url"] = url
        calls["headers"] = headers
        calls["data"] = data
        calls["timeout"] = timeout
        return _FakeResp()

    client = YandexSTTClient(api_key="KEY", folder_id="FOLDER", http_post=_fake_post)
    monkeypatch.setattr(
        "app.infra.yandex_stt.wave", types.SimpleNamespace(open=_fake_wave_open)
    )

    wav_path = tmp_path / "ok.wav"
    wav_path.touch()

    result = client.transcribe(wav_path)

    assert result == "привет"
    assert "folderId=FOLDER" in calls["url"]
    assert "sampleRateHertz=16000" in calls["url"]
    assert calls["data"] == _FAKE_RAW
    assert calls["timeout"] == 90


def test_transcribe_bad_geometry(monkeypatch, tmp_path):
    def _bad_wave_open(path, mode="rb"):
        return _FakeWave(ok=False)

    client = YandexSTTClient(api_key="KEY", folder_id="FOLDER")
    monkeypatch.setattr(
        "app.infra.yandex_stt.wave", types.SimpleNamespace(open=_bad_wave_open)
    )

    wav_path = tmp_path / "bad.wav"
    wav_path.touch()

    with pytest.raises(RuntimeError):
        client.transcribe(wav_path)


def test_transcribe_splits_long_audio(monkeypatch, tmp_path):
    chunks = []

    def _fake_wave_open(path, mode="rb"):
        return _FakeWave(ok=True)

    class _PartResponse:
        status_code = 200
        text = ""

        def __init__(self, number):
            self.number = number

        def json(self):
            return {"result": f"часть {self.number}"}

    def _fake_post(url, headers, data, timeout):
        chunks.append(data)
        return _PartResponse(len(chunks))

    client = YandexSTTClient(api_key="KEY", folder_id="FOLDER", http_post=_fake_post)
    monkeypatch.setattr(
        "app.infra.yandex_stt.wave", types.SimpleNamespace(open=_fake_wave_open)
    )
    monkeypatch.setattr("app.infra.yandex_stt.MAX_CHUNK_BYTES", 100)
    wav_path = tmp_path / "long.wav"
    wav_path.touch()

    result = client.transcribe(wav_path)

    assert result == "часть 1 часть 2"
    assert chunks == [_FAKE_RAW[:100], _FAKE_RAW[100:]]
