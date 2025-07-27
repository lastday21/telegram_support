import subprocess
from pathlib import Path
from datetime import datetime

class VoiceRecorder:
    def __init__(self, mic_device: str, mix_device: str):
        self.mic = mic_device
        self.mix = mix_device
        self.proc: subprocess.Popen | None = None
        self.filepath: Path | None = None

    def start(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path(f"record_{ts}.wav")
        self.filepath = out

        cmd = (
            f'ffmpeg -y -loglevel error '
            f'-f dshow -i "audio={self.mix}" '
            f'-f dshow -i "audio={self.mic}" '
            f'-filter_complex amix=inputs=2:normalize=0 '
            f'-ac 1 -ar 16000 "{out}"'
        )
        print("🔴 REC start →", out)
        print("CMD:", cmd)

        # открываем stdin, чтобы посылать 'q'
        self.proc = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE
        )

    def stop(self) -> Path:
        if not self.proc:
            raise RuntimeError("Запись не запущена")
        try:
            # отправляем FFmpeg команду 'q' для graceful exit
            self.proc.stdin.write(b"q")
            self.proc.stdin.flush()
        except Exception as e:
            print("[voice] Не удалось послать 'q' в FFmpeg:", e)
        # ждём завершения (долго не надо)
        self.proc.wait(timeout=5)
        print("🛑 REC stop →", self.filepath)
        return self.filepath
