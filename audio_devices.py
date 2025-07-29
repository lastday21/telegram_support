"""
Автоопределение аудиоустройств (Windows) для FFmpeg.
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache

_DSHOW_CMD = [
    "ffmpeg",
    "-hide_banner",
    "-list_devices",
    "true",
    "-f",
    "dshow",
    "-i",
    "dummy",
]


@lru_cache(maxsize=1)
def list_audio_devices() -> list[str]:
    """Возвращает список имён всех аудио-устройств DirectShow."""
    proc = subprocess.run(
        _DSHOW_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,       # нужен stderr
        check=False,
    )

    stderr = proc.stderr.decode("utf-8", errors="replace")
    devices: list[str] = []
    for line in stderr.splitlines():
        if "(audio)" not in line:
            continue
        m = re.search(r'"(.+?)"', line)
        if m:
            devices.append(m.group(1))
    return devices


def pick_default_devices() -> tuple[str, str]:
    """
    Возвращает (mic_device, mix_device).

    mic  — строка, содержащая «микрофон»/«microphone»
    mix  — строка, содержащая «stereo mix» или оба слова «стерео» и «микшер»
    """
    devs = list_audio_devices()

    # fallback: если устройств ровно два и одно из них содержит 'mix' ― берём их
    if len(devs) == 2 and any("mix" in d.lower() for d in devs):
        mic, mix = devs
        if "mix" in mic.lower():
            mic, mix = mix, mic
        return mic, mix

    mic = next(
        (d for d in devs if "микрофон" in d.lower() or "microphone" in d.lower()),
        None,
    )
    mix = next(
        (
            d
            for d in devs
            if ("стерео" in d.lower() and "микшер" in d.lower())
            or "stereo mix" in d.lower()
        ),
        None,
    )

    if not mic or not mix:
        raise RuntimeError(
            "Автопоиск устройств не удался.\n"
            f"Найдено: {devs or 'ничего'}\n"
            "Включи Stereo Mix в «Панель управления → Звук → Запись» "
            "или задай MIC_DEVICE/MIX_DEVICE через переменные окружения."
        )

    return mic, mix
