
import sounddevice as sd
import wave
import threading
from pathlib import Path
from datetime import datetime

SR = 16_000          # sample rate
CH = 1               # mono
SAMPLE_WIDTH = 2     # 16-bit

class VoiceRecorder:
    def __init__(self):
        self._wf = None
        self._stream = None
        self._lock = threading.Lock()
        self.filepath: Path | None = None

    # callback для sounddevice
    def _cb(self, in_data, frames, time_info, status):
        if status:
            print("sounddevice status:", status)
        with self._lock:
            if self._wf:
                self._wf.writeframes(in_data)

    # ─── публичные методы ────────────────────────────────
    def start(self):
        """Начинает запись микрофона."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = Path(f"record_{ts}.wav")

        # ⚠  str(self.filepath) — ключевой фикс
        self._wf = wave.open(str(self.filepath), "wb")
        self._wf.setnchannels(CH)
        self._wf.setsampwidth(SAMPLE_WIDTH)
        self._wf.setframerate(SR)

        self._stream = sd.InputStream(
            samplerate=SR,
            channels=CH,
            dtype="int16",
            callback=self._cb,
        )
        self._stream.start()
        print(f"🔴 REC start → {self.filepath}")

    def stop(self) -> Path:
        """Заканчивает запись и возвращает путь к WAV-файлу."""
        with self._lock:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            if self._wf:
                self._wf.close()
                self._wf = None
        print("🛑 REC stop")
        return self.filepath
