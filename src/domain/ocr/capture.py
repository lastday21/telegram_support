from __future__ import annotations

import os
import tempfile
from io import BytesIO
from typing import Literal, Optional, Tuple

from mss import mss, tools

__all__ = ["take_screenshot"]


def take_screenshot(
    region: Optional[Tuple[int, int, int, int]] = None,
    monitor: Optional[int] = 1,
    output_format: Literal["png", "jpg", "bmp"] = "png",
) -> bytes:
    if output_format not in {"png", "jpg", "bmp"}:
        raise ValueError("output_format должен быть 'png', 'jpg' или 'bmp'")

    file_suffix = f".{output_format}"

    with mss() as screen_capture:
        if region is None:
            monitor_index = monitor if monitor is not None else 1
            temp_file = tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False)
            temp_file_path = temp_file.name
            temp_file.close()

            try:
                screen_capture.shot(output=temp_file_path, mon=monitor_index)
                with open(temp_file_path, "rb") as file_handle:
                    return file_handle.read()
            finally:
                try:
                    os.remove(temp_file_path)
                except FileNotFoundError:
                    pass

        region_box = {
            "left": region[0],
            "top": region[1],
            "width": region[2],
            "height": region[3],
        }
        screenshot = screen_capture.grab(region_box)
        png_bytes = tools.to_png(screenshot.rgb, screenshot.size)

        if png_bytes is None:
            raise RuntimeError("Не удалось сформировать PNG")

        if output_format == "png":
            return png_bytes

        from PIL import Image

        with Image.open(BytesIO(png_bytes)) as image, BytesIO() as output_buffer:
            image.save(output_buffer, format=output_format.upper())
            return output_buffer.getvalue()
