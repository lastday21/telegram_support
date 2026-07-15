from app import desktop


def test_desktop_starts_tray_and_service(monkeypatch):
    calls = {}

    class _Service:
        def submit_check_server(self):
            calls["check"] = True

        def run(self, stop_event):
            calls["run_event"] = stop_event

        def close(self):
            calls["service_closed"] = True

    class _Tray:
        def __init__(self, on_exit):
            calls["on_exit"] = on_exit

        def set_check_handler(self, handler):
            calls["check_handler"] = handler

        def start(self):
            calls["tray_started"] = True

        def update(self, status, message, notify):
            pass

        def stop(self):
            calls["tray_stopped"] = True

    service = _Service()
    monkeypatch.setattr(desktop, "TrayController", _Tray)
    monkeypatch.setattr(
        desktop,
        "build_hotkey_service",
        lambda status_callback: service,
    )

    desktop.main()

    assert calls["tray_started"] is True
    assert calls["check_handler"] == service.submit_check_server
    assert calls["service_closed"] is True
    assert calls["tray_stopped"] is True
