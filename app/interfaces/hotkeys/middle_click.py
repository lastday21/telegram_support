from __future__ import annotations

import os
import threading
from collections.abc import Callable

from app.infra.windows_api import get_last_error, load_library, make_function_type


class MiddleClickHook:
    def __init__(self, callback: Callable[[], object]) -> None:
        self._callback = callback
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._error: Exception | None = None
        self._hook_callback: object | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        if os.name != "nt":
            raise RuntimeError("Перехват колёсика поддерживается только в Windows")

        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=3):
            raise RuntimeError("Не удалось запустить перехват колёсика")
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        if not self._thread_id:
            return

        load_library("user32").PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)
        self._thread_id = 0
        self._thread = None

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = load_library("user32")
        kernel32 = load_library("kernel32")
        hook_handle = None

        try:
            result_type = ctypes.c_ssize_t
            hook_proc_type = make_function_type(
                result_type,
                ctypes.c_int,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )
            user32.SetWindowsHookExW.argtypes = (
                ctypes.c_int,
                hook_proc_type,
                wintypes.HINSTANCE,
                wintypes.DWORD,
            )
            user32.SetWindowsHookExW.restype = wintypes.HANDLE
            user32.CallNextHookEx.argtypes = (
                wintypes.HANDLE,
                ctypes.c_int,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )
            user32.CallNextHookEx.restype = result_type

            def handle_mouse(code: int, message: int, data: int) -> int:
                if code >= 0 and message in {0x0207, 0x0208}:
                    if message == 0x0208:
                        try:
                            self._callback()
                        except Exception:
                            pass
                    return 1
                return int(user32.CallNextHookEx(hook_handle, code, message, data))

            self._hook_callback = hook_proc_type(handle_mouse)
            self._thread_id = int(kernel32.GetCurrentThreadId())
            hook_handle = user32.SetWindowsHookExW(
                14,
                self._hook_callback,
                None,
                0,
            )
            if not hook_handle:
                raise OSError(get_last_error(), "Не удалось перехватить колёсико")
            self._ready.set()

            message = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        except Exception as exc:
            self._error = exc
            self._ready.set()
        finally:
            if hook_handle:
                user32.UnhookWindowsHookEx(hook_handle)
            self._thread_id = 0
            self._hook_callback = None
