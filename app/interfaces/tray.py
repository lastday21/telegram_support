from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageDraw

from app.domain.status import AppStatus

STATUS_LABELS = {
    AppStatus.STARTING: "Запуск",
    AppStatus.READY: "Готово",
    AppStatus.RECORDING: "Идёт запись",
    AppStatus.WORKING: "Обработка",
    AppStatus.BUSY: "Занято",
    AppStatus.ERROR: "Ошибка",
    AppStatus.DISCONNECTED: "Сервер недоступен",
}

STATUS_COLORS = {
    AppStatus.STARTING: "#64748b",
    AppStatus.READY: "#16a34a",
    AppStatus.RECORDING: "#dc2626",
    AppStatus.WORKING: "#eab308",
    AppStatus.BUSY: "#f97316",
    AppStatus.ERROR: "#dc2626",
    AppStatus.DISCONNECTED: "#64748b",
}


def make_status_icon(status: AppStatus) -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((5, 5, 59, 59), fill=STATUS_COLORS[status])
    draw.ellipse((21, 21, 43, 43), fill="white")
    return image


class TrayController:
    def __init__(self, on_exit: Callable[[], None]) -> None:
        self._on_exit = on_exit
        self._on_check: Callable[[], object] = lambda: None
        self._status = AppStatus.STARTING
        self._message = STATUS_LABELS[self._status]
        self._icon: Any | None = None
        self._lock = threading.Lock()

    def set_check_handler(self, handler: Callable[[], object]) -> None:
        self._on_check = handler

    def start(self) -> bool:
        try:
            import pystray
        except ImportError:
            print("Значок состояния недоступен: пакет pystray не установлен")
            return False

        menu = pystray.Menu(
            pystray.MenuItem(
                lambda _item: self._menu_label(),
                lambda _icon, _item: None,
                enabled=False,
            ),
            pystray.MenuItem(
                "Проверить сервер",
                lambda _icon, _item: self._on_check(),
            ),
            pystray.MenuItem("Выход", lambda _icon, _item: self._exit()),
        )
        self._icon = pystray.Icon(
            "SmartHelper",
            make_status_icon(self._status),
            self._title(),
            menu,
        )
        self._icon.run_detached()
        return True

    def update(
        self,
        status: AppStatus,
        message: str = "",
        notify: bool = False,
    ) -> None:
        with self._lock:
            self._status = status
            self._message = message or STATUS_LABELS[status]
            icon = self._icon

        if icon is None:
            return
        icon.icon = make_status_icon(status)
        icon.title = self._title()
        icon.update_menu()
        if notify:
            try:
                icon.notify(self._message, "SmartHelper")
            except Exception:
                pass

    def stop(self) -> None:
        icon = self._icon
        if icon is not None:
            icon.stop()

    def _menu_label(self) -> str:
        with self._lock:
            return f"Состояние: {self._message}"

    def _title(self) -> str:
        with self._lock:
            return f"SmartHelper — {self._message}"

    def _exit(self) -> None:
        self._on_exit()
        self.stop()
