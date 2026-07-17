from pathlib import Path
from typing import Any

from app.infra import process_control


class _Process:
    def poll(self):
        return None


def test_start_main_launches_program_and_waits_for_mutex(monkeypatch, tmp_path: Path):
    states = iter((False, True))
    calls: dict[str, Any] = {}
    monkeypatch.setattr(process_control, "_ensure_windows", lambda: None)
    monkeypatch.setattr(process_control, "is_main_running", lambda: next(states))
    monkeypatch.setattr(
        process_control, "_main_command", lambda: (["SmartHelper.exe"], tmp_path)
    )
    monkeypatch.setattr(
        process_control.subprocess,
        "Popen",
        lambda command, **kwargs: calls.update(command=command, kwargs=kwargs)
        or _Process(),
    )

    assert process_control.start_main() is True
    assert calls["command"] == ["SmartHelper.exe"]
    assert calls["kwargs"]["cwd"] == tmp_path


def test_start_main_does_not_launch_second_instance(monkeypatch):
    monkeypatch.setattr(process_control, "_ensure_windows", lambda: None)
    monkeypatch.setattr(process_control, "is_main_running", lambda: True)
    monkeypatch.setattr(
        process_control.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("not called")),
    )

    assert process_control.start_main() is False


def test_stop_main_signals_program_and_waits_for_exit(monkeypatch):
    states = iter((True, True, False))
    signals = []
    monkeypatch.setattr(process_control, "is_main_running", lambda: next(states))
    monkeypatch.setattr(
        process_control, "_signal_stop", lambda: signals.append(True) or True
    )
    monkeypatch.setattr(process_control.time, "sleep", lambda _seconds: None)

    assert process_control.stop_main() is True
    assert signals == [True]
