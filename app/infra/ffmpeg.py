from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ffmpeg_executable() -> str:
    candidates: list[Path] = []
    explicit_path = os.getenv("FFMPEG_BINARY")
    if explicit_path:
        candidates.append(Path(explicit_path))

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "ffmpeg.exe")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "ffmpeg.exe")

    path_value = shutil.which("ffmpeg")
    if path_value:
        candidates.append(Path(path_value))

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())

    raise RuntimeError(
        "FFmpeg не найден. Переустановите SmartHelper или укажите путь "
        "в переменной FFMPEG_BINARY."
    )
