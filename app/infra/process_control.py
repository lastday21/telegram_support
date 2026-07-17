from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

from app.infra.windows_api import load_library

MUTEX_NAME = "SmartHelper.Main.Instance"
STOP_EVENT_NAME = "SmartHelper.Main.Stop"
SYNCHRONIZE = 0x00100000
EVENT_MODIFY_STATE = 0x0002
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0


def _ensure_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Управление SmartHelper доступно только в Windows")


def _close_handle(handle: int) -> None:
    kernel32 = load_library("kernel32")
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle(handle)


class NamedStopEvent:
    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("Управление SmartHelper доступно только в Windows")
        kernel32 = load_library("kernel32")
        kernel32.CreateEventW.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_wchar_p,
        )
        kernel32.CreateEventW.restype = ctypes.c_void_p
        self.handle = int(
            kernel32.CreateEventW(None, True, False, STOP_EVENT_NAME) or 0
        )
        if not self.handle:
            raise OSError("Не удалось создать событие остановки SmartHelper")

    def wait(self) -> bool:
        kernel32 = load_library("kernel32")
        kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        result = kernel32.WaitForSingleObject(self.handle, INFINITE)
        return result == WAIT_OBJECT_0

    def close(self) -> None:
        if self.handle:
            _close_handle(self.handle)
            self.handle = 0


def create_stop_event() -> NamedStopEvent | None:
    if os.name != "nt":
        return None
    return NamedStopEvent()


def is_main_running() -> bool:
    if os.name != "nt":
        return False
    kernel32 = load_library("kernel32")
    kernel32.OpenMutexW.argtypes = (ctypes.c_uint, ctypes.c_int, ctypes.c_wchar_p)
    kernel32.OpenMutexW.restype = ctypes.c_void_p
    handle = int(kernel32.OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME) or 0)
    if not handle:
        return False
    _close_handle(handle)
    return True


def _signal_stop() -> bool:
    if os.name != "nt":
        return False
    kernel32 = load_library("kernel32")
    kernel32.OpenEventW.argtypes = (ctypes.c_uint, ctypes.c_int, ctypes.c_wchar_p)
    kernel32.OpenEventW.restype = ctypes.c_void_p
    handle = int(kernel32.OpenEventW(EVENT_MODIFY_STATE, False, STOP_EVENT_NAME) or 0)
    if not handle:
        return False
    try:
        kernel32.SetEvent.argtypes = (ctypes.c_void_p,)
        return bool(kernel32.SetEvent(handle))
    finally:
        _close_handle(handle)


def _main_command() -> tuple[list[str], Path]:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve().with_name("SmartHelper.exe")
        if not executable.is_file():
            raise RuntimeError(f"Не найден файл основной программы: {executable}")
        return [str(executable)], executable.parent
    project_root = Path(__file__).resolve().parents[2]
    return [sys.executable, "-m", "app.desktop"], project_root


def start_main(timeout: float = 10) -> bool:
    _ensure_windows()
    if is_main_running():
        return False

    command, working_directory = _main_command()
    process = subprocess.Popen(
        command,
        cwd=working_directory,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_main_running():
            return True
        if process.poll() is not None:
            raise RuntimeError("SmartHelper завершился во время запуска")
        time.sleep(0.1)
    raise RuntimeError("SmartHelper не запустился вовремя")


def stop_main(timeout: float = 10) -> bool:
    if not is_main_running():
        return False
    if not _signal_stop():
        raise RuntimeError("Запущенная версия SmartHelper не поддерживает остановку")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_main_running():
            return True
        time.sleep(0.1)
    raise RuntimeError("SmartHelper не остановился вовремя")


def restart_main(timeout: float = 10) -> None:
    stop_main(timeout=timeout)
    start_main(timeout=timeout)
