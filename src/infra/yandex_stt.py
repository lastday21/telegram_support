from pathlib import Path
import wave

import requests

from src.settings import YC_API_KEY, YC_FOLDER_ID

STT_API_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
STT_HEADERS = {"Authorization": f"Api-Key {YC_API_KEY}"}
ENABLE_DEBUG_LOGS = True


def _debug_log(*message_parts: object) -> None:
    if ENABLE_DEBUG_LOGS:
        print("[speech]", *message_parts)


def transcribe(wav_path: Path) -> str:
    with wave.open(str(wav_path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        if (sample_rate, channels, sample_width) != (16000, 1, 2):
            raise RuntimeError("Нужно WAV 16 kHz mono 16-bit")
        raw_pcm_bytes = wav_file.readframes(wav_file.getnframes())

    query_params = {
        "folderId": YC_FOLDER_ID,
        "lang": "ru-RU",
        "format": "lpcm",
        "sampleRateHertz": "16000",
    }
    query_string = "&".join(f"{key}={value}" for key, value in query_params.items())
    request_url = f"{STT_API_URL}?{query_string}"

    _debug_log("POST", request_url, f"({len(raw_pcm_bytes)} bytes)")

    response = requests.post(
        request_url,
        headers=STT_HEADERS,
        data=raw_pcm_bytes,
        timeout=90,
    )
    _debug_log("HTTP", response.status_code)

    if response.status_code != 200:
        _debug_log("STT error:", response.text)
        raise RuntimeError(f"STT {response.status_code}: {response.text}")

    recognized_text = response.json().get("result", "").strip()
    _debug_log("STT text:", recognized_text)
    return recognized_text
