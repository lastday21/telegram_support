from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_SAVED_SCREENSHOTS = 100
SCREENSHOT_DIRECTORY_NAME = "screenshots"
_archive_lock = threading.Lock()


def screenshot_directory(base_dir: Path | None = None) -> Path:
    root = base_dir or Path(
        os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or Path.home()
    )
    return root / "SmartHelper" / SCREENSHOT_DIRECTORY_NAME


def save_screenshot(
    image: bytes,
    *,
    base_dir: Path | None = None,
    max_files: int = MAX_SAVED_SCREENSHOTS,
) -> Path | None:
    if not image:
        return None
    if max_files < 1:
        raise ValueError("Количество сохраняемых снимков должно быть положительным")

    directory = screenshot_directory(base_dir)
    try:
        with _archive_lock:
            directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            destination = directory / f"screenshot_{timestamp}.png"
            temporary = destination.with_suffix(".png.tmp")
            temporary.write_bytes(image)
            temporary.replace(destination)
            _remove_old_screenshots(directory, max_files)
    except OSError:
        logger.exception("Не удалось сохранить снимок для последующего разбора")
        return None

    logger.info("Снимок сохранён для разбора: %s", destination)
    return destination


def _remove_old_screenshots(directory: Path, max_files: int) -> None:
    screenshots = sorted(directory.glob("screenshot_*.png"), key=lambda path: path.name)
    for screenshot in screenshots[:-max_files]:
        try:
            screenshot.unlink()
        except OSError:
            logger.warning("Не удалось удалить старый снимок: %s", screenshot)
