"""
Модуль для создания скриншотов:

* Снимает весь экран, выбранный монитор.
* Возвращает «сырые» байты PNG/JPEG/BMP, а не путь к файлу.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional, Tuple, Literal
from io import BytesIO
from mss import mss, tools


__all__ = ["take_screenshot"]


def take_screenshot(
    region: Optional[Tuple[int, int, int, int]] = None,
    monitor: Optional[int] = 1,
    output_format: Literal["png", "jpg", "bmp"] = "png",
) -> bytes:
    """
    Снимает скриншот и возвращает содержимое файла в виде `bytes`.

    Параметры
    ---------
    region : tuple(x, y, width, height) | None
        Область захвата. Если ``None``, снимается весь монитор.
    monitor : int | None
        Номер монитора (нумерация начинается с `1`), если их несколько.
        ``None`` → используется *первый* монитор (mss.monitors[1]).
    output_format : {'png', 'jpg', 'bmp'}
        Формат итогового изображения.

    Возврат
    -------
    bytes
        Байтовое содержимое PNG/JPEG/BMP–файла.

    Исключения
    ----------
    ValueError
        Если `output_format` не поддерживается.
    """
    if output_format not in {"png", "jpg", "bmp"}:
        raise ValueError("output_format должен быть 'png', 'jpg' или 'bmp'")

    suffix = f".{output_format}"

    with mss() as sct:
        # --------- СНИМОК ВЕСЬ МОНТОР ---------
        if region is None:
            mon_idx = monitor if monitor is not None else 1
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp_path = tmp.name
            tmp.close()
            try:
                sct.shot(output=tmp_path, mon=mon_idx)  # region не передаём!
                with open(tmp_path, "rb") as fh:
                    return fh.read()
            finally:
                try:
                    os.remove(tmp_path)
                except FileNotFoundError:
                    pass

        # --------- СНИМОК ОБЛАСТИ / MULTI-MON ---------
        # grab() → raw RGB; сохраняем в PNG, затем при нужде конвертируем через Pillow
        img = sct.grab(
            {
                "left": region[0],
                "top": region[1],
                "width": region[2],
                "height": region[3],
            }
        )
        png_bytes = tools.to_png(img.rgb, img.size)
        assert png_bytes is not None

        # если нужен PNG ― сразу возвращаем
        if output_format == "png":
            return png_bytes

        # иначе переконвертируем (JPG/BMP)
        from PIL import Image

        with Image.open(BytesIO(png_bytes)) as im, BytesIO() as buf:
            im.save(buf, format=output_format.upper())
            return buf.getvalue()
