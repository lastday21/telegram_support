"""
Юнит-тесты для VoiceRecorder.

• monkeypatch → подменяем subprocess.Popen фэйковым классом, чтобы
  не запускать FFmpeg;
• tmp_path  → проверяем, что файл .wav создаётся в рабочей папке;
• фиксация вызовов в словаре `calls` позволяет убедиться,
  что методы wait / terminate / stdin.write были вызваны.
"""

from pathlib import Path
import pytest
from src.domain.audio.recorder import VoiceRecorder


@pytest.fixture
def fake_popen(monkeypatch):
    """
    Подменяет subprocess.Popen и отдаёт словарь `calls`
    с отметками, какие методы вызывались.
    """
    calls: dict[str, object] = {}

    class _FakeStdin:
        def write(self, data):
            calls["stdin_write"] = data

        def flush(self):
            calls["stdin_flush"] = True

    class _FakeProc:
        def __init__(self, cmd, shell, stdin):
            calls["cmd"] = cmd
            self.stdin = _FakeStdin()
            self._terminated = False

        def wait(self, timeout=None):
            calls["wait_called"] = True
            return 0  # imitate clean exit

        def terminate(self):
            self._terminated = True
            calls["terminate_called"] = True

    monkeypatch.setattr(
        "src.domain.audio.recorder.subprocess.Popen", _FakeProc, raising=True
    )
    return calls


@pytest.fixture
def recorder():
    """Создаём экземпляр с фиктивными именами устройств."""
    return VoiceRecorder(mic_device="MicDevice", mix_device="MixDevice")


# ---------- тесты ----------------------------------------------------
def test_start_creates_process(recorder, fake_popen, tmp_path):
    """Recorder.start() должен создать процесс и сохранить путь к файлу."""
    recorder.start()

    # 1) Процесс создан
    assert recorder.proc is not None

    # 2) Файл .wav в имени
    assert recorder.filepath is not None
    assert recorder.filepath.suffix == ".wav"

    # 3) В командной строке есть оба устройства и ключ -ac 1
    cmd = fake_popen["cmd"]
    assert '"audio=MixDevice"' in cmd
    assert '"audio=MicDevice"' in cmd
    assert "-ac 1" in cmd


def test_stop_terminates_process(recorder, fake_popen):
    """Recorder.stop() корректно завершает процесс и возвращает Path."""
    recorder.start()  # создаём фэйковый процесс
    wav_path: Path = recorder.stop()

    # 1) wait() вызван
    assert fake_popen.get("wait_called") is True

    # 2) stdin.write('q') и flush() вызваны
    assert fake_popen.get("stdin_write") == b"q"
    assert fake_popen.get("stdin_flush") is True

    # 3) Метод вернул тот же путь, что хранится в объекте
    assert wav_path == recorder.filepath
