from __future__ import annotations

import ctypes
import os

from app.infra.windows_api import load_library
from app.interfaces.hotkeys.listener import build_hotkey_service

ALREADY_EXISTS = 183


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
    instance = acquire_single_instance()
    if instance is None:
        return
    try:
        service = build_hotkey_service()
    except Exception as exc:
        show_startup_error(str(exc))
        if os.name == "nt" and instance is not True:
            load_library("kernel32").CloseHandle(instance)
        return
    try:
        service.run()
    finally:
        service.close()
        if os.name == "nt" and instance is not True:
            load_library("kernel32").CloseHandle(instance)


if __name__ == "__main__":
    main()
