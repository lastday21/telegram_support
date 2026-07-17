from pathlib import Path

from app import desktop


def test_desktop_runs_service_without_tray(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        desktop, "configure_desktop_logging", lambda: Path("smarthelper.log")
    )

    class _StopEvent:
        def close(self):
            calls["event_closed"] = True

    stop_event = _StopEvent()

    class _Service:
        def run(self, stop_event=None):
            calls["run"] = stop_event

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: True)
    monkeypatch.setattr(desktop, "create_stop_event", lambda: stop_event)
    monkeypatch.setattr(desktop, "build_hotkey_service", lambda: _Service())

    desktop.main()

    assert calls == {
        "run": stop_event,
        "closed": True,
        "event_closed": True,
    }


def test_second_desktop_instance_exits_silently(monkeypatch):
    calls = []
    monkeypatch.setattr(
        desktop, "configure_desktop_logging", lambda: Path("smarthelper.log")
    )
    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: None)
    monkeypatch.setattr(desktop, "build_hotkey_service", lambda: calls.append(True))

    desktop.main()

    assert calls == []
