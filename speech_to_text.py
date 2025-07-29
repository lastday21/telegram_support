"""
• 16 kHz mono WAV  →  raw-PCM bytes
•  POST /speech/v1/stt:recognize?...  (query-params)
•  ответ JSON → text
"""
from pathlib import Path
import wave
import requests
from config import YC_API_KEY, YC_FOLDER_ID

BASE_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
HEADERS  = {"Authorization": f"Api-Key {YC_API_KEY}"}
DEBUG    = True
def _log(*m):
    if DEBUG:
        print("[speech]", *m)

def transcribe(wav_path: Path) -> str:
    # 1) читаем raw-сэмплы
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        if (sr, ch, sw) != (16000, 1, 2):
            raise RuntimeError("Нужно WAV 16 kHz mono 16-bit")
        raw = wf.readframes(wf.getnframes())

    # 2) собираем URL с query-параметрами
    params = {
        "folderId":         YC_FOLDER_ID,
        "lang":             "ru-RU",
        "format":           "lpcm",
        "sampleRateHertz":  "16000",
    }
    url = BASE_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    _log("POST", url, f"({len(raw)} bytes)")

    # 3) POST-им сырой PCM как body
    r = requests.post(url, headers=HEADERS, data=raw, timeout=90)
    _log("HTTP", r.status_code)
    if r.status_code != 200:
        _log("STT error:", r.text)
        raise RuntimeError(f"STT {r.status_code}: {r.text}")

    text = r.json().get("result", "").strip()
    _log("STT text:", text)
    return text
