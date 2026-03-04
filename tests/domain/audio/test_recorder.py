from pathlib import Path
import types

import pytest

from src.domain.audio.recorder import RECORDS_DIR, VoiceRecorder


@pytest.fixture
def fake_popen(monkeypatch):
    calls: dict[str, object] = {}

    class _FakeStdin:
        def write(self, data):
            calls["stdin_write"] = data

        def flush(self):
            calls["stdin_flush"] = True

    class _FakeProc:
        def __init__(self, cmd, stdin, stdout, stderr):
            calls["cmd"] = cmd
            self.stdin = _FakeStdin()
            self.stderr = types.SimpleNamespace(read=lambda: b"")
            self.returncode = 0

        def wait(self, timeout=None):
            calls["wait_called"] = True
            return 0

    monkeypatch.setattr(
        "src.domain.audio.recorder.subprocess.Popen", _FakeProc, raising=True
    )
    return calls


@pytest.fixture
def recorder():
    return VoiceRecorder(mic_device="MicDevice", mix_device="MixDevice")


def test_start_creates_process(recorder, fake_popen):
    recorder.start()

    assert recorder.proc is not None
    assert recorder.filepath is not None
    assert recorder.filepath.suffix == ".wav"
    assert recorder.filepath.is_absolute()
    assert recorder.filepath.parent.name == RECORDS_DIR

    cmd = fake_popen["cmd"]
    assert "audio=MixDevice" in cmd
    assert "audio=MicDevice" in cmd
    assert "-ac" in cmd


def test_stop_returns_recorded_file(recorder, fake_popen):
    recorder.start()
    assert recorder.filepath is not None
    recorder.filepath.touch()

    wav_path: Path = recorder.stop()

    assert fake_popen.get("wait_called") is True
    assert fake_popen.get("stdin_write") == b"q"
    assert fake_popen.get("stdin_flush") is True
    assert wav_path == recorder.filepath


def test_stop_raises_when_ffmpeg_did_not_create_file(
    monkeypatch, recorder, fake_popen, tmp_path
):
    monkeypatch.setattr("src.domain.audio.recorder.Path.cwd", lambda: tmp_path)
    recorder.start()

    with pytest.raises(RuntimeError, match="не создал WAV-файл"):
        recorder.stop()


def test_start_creates_records_directory(monkeypatch, recorder, fake_popen, tmp_path):
    monkeypatch.setattr("src.domain.audio.recorder.Path.cwd", lambda: tmp_path)

    recorder.start()

    assert (tmp_path / RECORDS_DIR).is_dir()
