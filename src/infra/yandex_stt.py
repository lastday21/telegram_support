from pathlib import Path
import wave

import requests

from src.settings import get_settings

BASE_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
DEBUG = True


def _log(*message_parts):
    if DEBUG:
        print("[speech]", *message_parts)


class YandexSTTClient:
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        http_post=requests.post,
        timeout: int = 90,
    ) -> None:
        self.folder_id = folder_id
        self.http_post = http_post
        self.timeout = timeout
        self.headers = {"Authorization": f"Api-Key {api_key}"}

    def transcribe(self, wav_path: Path) -> str:
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            if (sr, ch, sw) != (16000, 1, 2):
                raise RuntimeError("Нужен WAV 16 kHz mono 16-bit")
            raw = wf.readframes(wf.getnframes())

        params = {
            "folderId": self.folder_id,
            "lang": "ru-RU",
            "format": "lpcm",
            "sampleRateHertz": "16000",
        }
        url = BASE_URL + "?" + "&".join(f"{key}={value}" for key, value in params.items())

        _log("POST", url, f"({len(raw)} bytes)")

        response = self.http_post(
            url, headers=self.headers, data=raw, timeout=self.timeout
        )
        _log("HTTP", response.status_code)
        if response.status_code != 200:
            _log("STT error:", response.text)
            raise RuntimeError(f"STT {response.status_code}: {response.text}")

        text = response.json().get("result", "").strip()
        _log("STT text:", text)
        return text


def build_stt_client() -> YandexSTTClient:
    settings = get_settings()
    return YandexSTTClient(settings.yc_api_key, settings.yc_folder_id)


def transcribe(wav_path: Path) -> str:
    return build_stt_client().transcribe(wav_path)
