from datetime import datetime
from pathlib import Path
import subprocess


class VoiceRecorder:
    def __init__(self, mic_device: str, mix_device: str):
        self.mic = mic_device
        self.mix = mix_device
        self.proc: subprocess.Popen | None = None
        self.filepath: Path | None = None

    def start(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = (Path.cwd() / f"record_{ts}.wav").resolve()
        self.filepath = out

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "dshow",
            "-i",
            f"audio={self.mix}",
            "-f",
            "dshow",
            "-i",
            f"audio={self.mic}",
            "-filter_complex",
            "amix=inputs=2:normalize=0",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(out),
        ]
        print("🔴 REC start ", out.name)
        print("CMD:", subprocess.list2cmdline(cmd))

        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def stop(self) -> Path:
        if not self.proc:
            raise RuntimeError("Запись не запущена")

        proc = self.proc
        try:
            assert proc.stdin is not None, "stdin was None"
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except Exception as exc:
            print("[voice] Не удалось послать 'q' в FFmpeg:", exc)

        proc.wait(timeout=5)
        stderr_text = ""
        if proc.stderr is not None:
            stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()

        assert self.filepath is not None
        print("🛑 REC stop ", self.filepath.name)
        self.proc = None

        if proc.returncode not in (0, None):
            raise RuntimeError(
                f"FFmpeg завершился с кодом {proc.returncode}: {stderr_text or 'без сообщения'}"
            )
        if not self.filepath.exists():
            raise RuntimeError(
                "FFmpeg не создал WAV-файл. "
                f"Путь: {self.filepath}. "
                f"stderr: {stderr_text or 'пусто'}"
            )
        return self.filepath
