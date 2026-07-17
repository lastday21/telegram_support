from __future__ import annotations

import ctypes
import logging
import os
import sys

from app.infra.windows_api import load_library
from app.interfaces.hotkeys.listener import build_hotkey_service
from app.logging_config import configure_desktop_logging

ALREADY_EXISTS = 183
logger = logging.getLogger(__name__)


def acquire_single_instance():
    if os.name != "nt":
        return True
    kernel32 = load_library("kernel32")
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "SmartHelper.Main.Instance")
    if not handle or kernel32.GetLastError() == ALREADY_EXISTS:
        if handle:
            kernel32.CloseHandle(handle)
        return None
    return handle


def show_startup_error(message: str) -> None:
    if os.name == "nt":
        load_library("user32").MessageBoxW(
            None,
            message,
            "SmartHelper — ошибка запуска",
            0x10,
        )
    else:
        print(message)


def main() -> None:
    log_path = configure_desktop_logging()
    logger.info("Запуск SmartHelper: %s", sys.executable)
    logger.info("Файл журнала: %s", log_path)
    instance = acquire_single_instance()
    if instance is None:
        logger.info("Второй экземпляр завершён")
        return
    try:
        service = build_hotkey_service()
    except Exception as exc:
        logger.exception("Не удалось подготовить SmartHelper")
        show_startup_error(str(exc))
        if os.name == "nt" and instance is not True:
            load_library("kernel32").CloseHandle(instance)
        return
    try:
        service.run()
    except Exception:
        logger.exception("Работа SmartHelper аварийно завершена")
    finally:
        service.close()
        if os.name == "nt" and instance is not True:
            load_library("kernel32").CloseHandle(instance)
        logger.info("SmartHelper завершён")


if __name__ == "__main__":
    main()
