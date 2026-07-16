from __future__ import annotations

import ctypes
from typing import Any


def load_library(name: str) -> Any:
    loader = getattr(ctypes, "windll", None)
    if loader is None:
        raise RuntimeError("Windows API недоступен")
    return getattr(loader, name)


def make_function_type(*args: object) -> Any:
    factory = getattr(ctypes, "WINFUNCTYPE", None)
    if factory is None:
        raise RuntimeError("Windows API недоступен")
    return factory(*args)


def get_last_error() -> int:
    getter = getattr(ctypes, "get_last_error", None)
    if getter is None:
        return 0
    return int(getter())
