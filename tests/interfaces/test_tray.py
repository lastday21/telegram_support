from app.domain.status import AppStatus
from app.interfaces.tray import TrayController, make_status_icon


class _FakeIcon:
    def __init__(self):
        self.icon = None
        self.title = ""
        self.notifications = []
        self.menu_updated = False
        self.stopped = False

    def update_menu(self):
        self.menu_updated = True

    def notify(self, message, title):
        self.notifications.append((message, title))

    def stop(self):
        self.stopped = True


def test_status_icon_has_expected_size():
    icon = make_status_icon(AppStatus.RECORDING)

    assert icon.size == (64, 64)
    assert icon.getpixel((10, 32))[:3] == (220, 38, 38)


def test_tray_updates_status_and_notification():
    tray = TrayController(on_exit=lambda: None)
    icon = _FakeIcon()
    tray._icon = icon

    tray.update(AppStatus.READY, "Ответ готов", notify=True)

    assert icon.title == "SmartHelper — Ответ готов"
    assert icon.menu_updated is True
    assert icon.notifications == [("Ответ готов", "SmartHelper")]


def test_tray_exit_stops_application():
    calls = []
    tray = TrayController(on_exit=lambda: calls.append("exit"))
    icon = _FakeIcon()
    tray._icon = icon

    tray._exit()

    assert calls == ["exit"]
    assert icon.stopped is True
