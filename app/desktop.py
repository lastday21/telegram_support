import threading

from app.interfaces.hotkeys.listener import build_hotkey_service
from app.interfaces.tray import TrayController


def main() -> None:
    stop_event = threading.Event()
    tray = TrayController(on_exit=stop_event.set)
    service = build_hotkey_service(status_callback=tray.update)
    tray.set_check_handler(service.submit_check_server)
    tray.start()
    try:
        service.run(stop_event=stop_event)
    finally:
        service.close()
        tray.stop()


if __name__ == "__main__":
    main()
