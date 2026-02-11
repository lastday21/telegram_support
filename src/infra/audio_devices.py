from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from typing import Optional

LIST_DEVICES_COMMAND = [
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
    completed_process = subprocess.run(
        LIST_DEVICES_COMMAND,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    stderr_text = completed_process.stderr.decode("utf-8", errors="replace")
    device_names: list[str] = []

    for line in stderr_text.splitlines():
        if "(audio)" not in line:
            continue
        match = re.search(r'"(.+?)"', line)
        if match:
            device_names.append(match.group(1))

    return device_names


def pick_default_devices() -> tuple[str, str]:
    device_names = list_audio_devices()

    microphone_device: Optional[str] = None
    stereo_mix_device: Optional[str] = None

    if len(device_names) == 2 and any("mix" in device.lower() for device in device_names):
        first_device, second_device = device_names
        if "mix" in first_device.lower():
            return second_device, first_device
        return first_device, second_device

    microphone_device = next(
        (
            device
            for device in device_names
            if "микрофон" in device.lower() or "microphone" in device.lower()
        ),
        None,
    )
    stereo_mix_device = next(
        (
            device
            for device in device_names
            if ("стерео" in device.lower() and "микшер" in device.lower())
            or "stereo mix" in device.lower()
        ),
        None,
    )

    if microphone_device is None or stereo_mix_device is None:
        raise RuntimeError(
            "Автопоиск устройств не удался.\n"
            f"Найдено: {device_names or 'ничего'}\n"
            "Включи Stereo Mix в «Панель управления → Звук → Запись» "
            "или задай MIC_DEVICE/MIX_DEVICE через переменные окружения."
        )

    return microphone_device, stereo_mix_device
