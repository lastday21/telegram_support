"""
Тесты парсера infra.audio_devices.
"""

import pytest
import src.infra.audio_devices as ad


@pytest.fixture
def fake_ffmpeg(monkeypatch):
    """
    Подменяет subprocess.run. В dict body["text"] лежит *строка* —
    её можно менять в тестах, а мок-процесс вернёт bytes.
    """
    body = {
        "text": (
            '[dshow @ 000] DirectShow audio devices\n'
            '  "Микрофон (audio)"\n'
            '  "Стерео микшер (audio)"\n'
        )
    }

    class _FakeProc:
        def __init__(self, *_, **__):
            self.stderr = body["text"].encode("utf-8")

    monkeypatch.setattr(ad.subprocess, "run", lambda *a, **k: _FakeProc())
    return body


# ──────────────── TESTS ─────────────────────────────────────────────
def test_list_audio_devices(fake_ffmpeg):
    devs = ad.list_audio_devices()
    assert len(devs) == 2
    assert any("микрофон" in d.lower() for d in devs)
    assert any("микшер" in d.lower() or "mix" in d.lower() for d in devs)


def test_pick_default_devices(fake_ffmpeg):
    mic, mix = ad.pick_default_devices()
    assert "микрофон" in mic.lower() or "microphone" in mic.lower()
    assert "микшер" in mix.lower() or "mix" in mix.lower()


def test_no_mixer_error(fake_ffmpeg):
    body_text = fake_ffmpeg["text"]
    fake_ffmpeg["text"] = body_text.replace(
        '  "Микрофон (audio)"\n',  # ← две пробелы перед кавычкой
        "",
    )


