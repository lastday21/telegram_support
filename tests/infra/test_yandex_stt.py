"""
Юнит-тесты для infra.yandex_stt.transcribe()

• monkeypatch → подменяем wave.open   → не читаем реальный WAV;
• monkeypatch → подменяем requests.post → не совершаем HTTP;
• проверяем:
     1) корректная WAV-геометрия делает POST и отдаёт текст;
     2) неверная геометрия вызывает RuntimeError.
"""

import types
import pytest
import src.infra.yandex_stt as stt


# ---------- helpers --------------------------------------------------
_FAKE_RAW = b"\x00\x01" * 100  # 200 байт PCM 16-бит


class _FakeWave:
    """Контекст-менеджер, имитирующий wave.open()."""

    def __init__(self, ok: bool):
        self.ok = ok

    # ——— методы, которые вызывает transcribe() ———
    def getframerate(self):  # 16 000 Гц
        return 16000

    def getnchannels(self):  # 1 канал или 2 (bad)
        return 1 if self.ok else 2

    def getsampwidth(self):  # 2 байта = 16-бит
        return 2

    def getnframes(self):  # сколько «фреймов»
        return len(_FAKE_RAW) // 2

    def readframes(self, n):
        return _FAKE_RAW

    # ——— контекст ———
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeResp:
    status_code = 200
    _json = {"result": "привет"}

    def json(self):
        return self._json


# ---------- fixtures -------------------------------------------------
@pytest.fixture
def patch_wave_and_requests(monkeypatch):
    """
    Подменяет wave.open и requests.post.
    Возвращает словарь call_data с параметрами вызова POST.
    """
    call_data = {}

    def _fake_wave_open(path, mode="rb"):
        return _FakeWave(ok=True)

    monkeypatch.setattr(stt, "wave", types.SimpleNamespace(open=_fake_wave_open))

    def _fake_post(url, headers, data, timeout):
        call_data["url"] = url
        call_data["headers"] = headers
        call_data["data"] = data
        call_data["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(stt, "requests", types.SimpleNamespace(post=_fake_post))

    return call_data


# ---------- TESTS ----------------------------------------------------
def test_transcribe_success(tmp_path, patch_wave_and_requests):
    """Корректный WAV → идёт POST → возвращается текст «привет»."""
    wav_path = tmp_path / "ok.wav"
    wav_path.touch()

    result = stt.transcribe(wav_path)

    # функция вернула правильный текст
    assert result == "привет"

    # сформирована корректная строка запроса и тело == raw-данным
    call = patch_wave_and_requests
    assert "folderId=" in call["url"] and "sampleRateHertz=16000" in call["url"]
    assert call["data"] == _FAKE_RAW
    assert call["timeout"] == 90


def test_transcribe_bad_geometry(monkeypatch, tmp_path):
    """Если WAV не 16 kHz/mono/16-bit → должен быть RuntimeError."""
    wav_path = tmp_path / "bad.wav"
    wav_path.touch()

    # подменяем wave.open объектом со 2 каналами
    def _bad_wave_open(path, mode="rb"):
        return _FakeWave(ok=False)

    monkeypatch.setattr(stt, "wave", types.SimpleNamespace(open=_bad_wave_open))

    with pytest.raises(RuntimeError):
        stt.transcribe(wav_path)
