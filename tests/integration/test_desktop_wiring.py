from app import desktop


def test_desktop_runs_service_without_tray(monkeypatch):
    calls = {}

    class _Service:
        def run(self):
            calls["run"] = True

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: True)
    monkeypatch.setattr(desktop, "build_hotkey_service", lambda: _Service())

    desktop.main()

    assert calls == {"run": True, "closed": True}


def test_second_desktop_instance_exits_silently(monkeypatch):
    calls = []
    monkeypatch.setattr(desktop, "acquire_single_instance", lambda: None)
    monkeypatch.setattr(desktop, "build_hotkey_service", lambda: calls.append(True))

    desktop.main()

    assert calls == []
