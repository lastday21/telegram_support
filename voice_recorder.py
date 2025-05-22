# voice_recorder.py
# ──────────────────────────────────────────────────────────────
# FFmpeg через shell=True, чтобы было проще с кавычками
# Два dshow-инпута (stereo mix + mic) → amix → mono 16 kHz WAV
# ──────────────────────────────────────────────────────────────
import subprocess, signal
from pathlib import Path
from datetime import datetime

class VoiceRecorder:
    def __init__(self, mic_device: str, mix_device: str):
        """
        mic_device — точное имя микрофона, как его видит `ffmpeg -list_devices`
        mix_device — точное имя «Стерео микшер», как его видит ffmpeg
        """
        self.mic = mic_device
        self.mix = mix_device
        self.proc = None
        self.filepath = None

    def start(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path(f"record_{ts}.wav")
        self.filepath = out

        # Формируем одну строку команды с кавычками внутри
        cmd = (
            f'ffmpeg -y -loglevel error '
            f'-f dshow -i "audio={self.mix}" '
            f'-f dshow -i "audio={self.mic}" '
            f'-filter_complex amix=inputs=2:normalize=0 '
            f'-ac 1 -ar 16000 "{out}"'
        )
        print("🔴 REC start →", out)
        print("CMD:", cmd)

        # shell=True чтобы Windows правильно распарсил кавычки
        self.proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            shell=True
        )

    def stop(self) -> Path:
        if not self.proc:
            raise RuntimeError("Запись не запущена")
        try:
            # CTRL+BREAK надёжнее для FFmpeg
            self.proc.send_signal(signal.CTRL_BREAK_EVENT)
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("[voice] FFmpeg не завершился, убиваем принудительно")
            self.proc.kill()
            self.proc.wait()
        print("🛑 REC stop →", self.filepath)
        return self.filepath
