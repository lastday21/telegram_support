from pathlib import Path
import wave

import requests

from app.infra.yandex_resilience import (
    YandexCallPolicy,
    default_yandex_call_policy,
)
from app.settings import get_settings

BASE_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
DEBUG = True
MAX_CHUNK_BYTES = 900_000


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
        call_policy: YandexCallPolicy = default_yandex_call_policy,
    ) -> None:
        self.folder_id = folder_id
        self.http_post = http_post
        self.timeout = timeout
        self.call_policy = call_policy
        self.headers = {"Authorization": f"Api-Key {api_key}"}

    def transcribe(self, wav_path: Path) -> str:
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            if (sr, ch, sw) != (16000, 1, 2):
                raise RuntimeError("Нужен WAV 16 kHz mono 16-bit")
            frame_size = ch * sw
            raw = wf.readframes(wf.getnframes())

        if not raw:
            return ""

        chunk_size = MAX_CHUNK_BYTES - (MAX_CHUNK_BYTES % frame_size)
        chunks = [
            raw[offset : offset + chunk_size]
            for offset in range(0, len(raw), chunk_size)
        ]
        parts: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            _log(f"часть {index}/{len(chunks)}", f"({len(chunk)} bytes)")
            text = self._transcribe_chunk(chunk)
            if text:
                parts.append(text)
        return " ".join(parts)

    def _transcribe_chunk(self, raw: bytes) -> str:
        params = {
            "folderId": self.folder_id,
            "lang": "ru-RU",
            "format": "lpcm",
            "sampleRateHertz": "16000",
        }
        url = (
            BASE_URL + "?" + "&".join(f"{key}={value}" for key, value in params.items())
        )

        _log("POST", url, f"({len(raw)} bytes)")

        def send_request():
            response = self.http_post(
                url, headers=self.headers, data=raw, timeout=self.timeout
            )
            _log("HTTP", response.status_code)
            if response.status_code != 200:
                _log("STT error:", response.text)
                error = requests.HTTPError(
                    f"STT {response.status_code}: {response.text}"
                )
                error.response = response
                raise error
            return response

        response = self.call_policy.execute(send_request)
        return response.json().get("result", "").strip()


def build_stt_client() -> YandexSTTClient:
    settings = get_settings()
    return YandexSTTClient(settings.yc_api_key, settings.yc_folder_id)


def transcribe(wav_path: Path) -> str:
    return build_stt_client().transcribe(wav_path)
