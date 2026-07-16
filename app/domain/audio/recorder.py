from datetime import datetime
from pathlib import Path
import subprocess

from app.infra.ffmpeg import ffmpeg_executable

RECORDS_DIR = "records"
GRACEFUL_STOP_TIMEOUT = 5
TERMINATE_TIMEOUT = 2


class VoiceRecorder:
    def __init__(self, mic_device: str, mix_device: str | None):
        self.mic = mic_device
        self.mix = mix_device
        self.proc: subprocess.Popen | None = None
        self.filepath: Path | None = None

    def start(self) -> None:
        if self.proc is not None:
            raise RuntimeError("Запись уже запущена")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = (Path.cwd() / RECORDS_DIR).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"record_{ts}.wav"
        self.filepath = out

        cmd = [
            ffmpeg_executable(),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "dshow",
            "-i",
            f"audio={self.mic}",
        ]
        if self.mix:
            cmd.extend(
                [
                    "-f",
                    "dshow",
                    "-i",
                    f"audio={self.mix}",
                    "-filter_complex",
                    "amix=inputs=2:normalize=0",
                ]
            )
        cmd.extend(["-ac", "1", "-ar", "16000", str(out)])
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
        forced_stop = False
        try:
            assert proc.stdin is not None, "stdin was None"
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except Exception as exc:
            print("[voice] Не удалось послать 'q' в FFmpeg:", exc)

        try:
            proc.wait(timeout=GRACEFUL_STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            forced_stop = True
            print("[voice] FFmpeg не остановился вовремя, завершаю процесс")
            proc.terminate()
            try:
                proc.wait(timeout=TERMINATE_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=TERMINATE_TIMEOUT)
        finally:
            self.proc = None

        stderr_text = self._read_stderr(proc)

        assert self.filepath is not None
        print("🛑 REC stop ", self.filepath.name)

        if proc.returncode not in (0, None):
            raise RuntimeError(
                f"FFmpeg завершился с кодом {proc.returncode}: {stderr_text or 'без сообщения'}"
            )
        if forced_stop:
            raise RuntimeError("FFmpeg пришлось остановить принудительно")
        if not self.filepath.exists():
            raise RuntimeError(
                "FFmpeg не создал WAV-файл. "
                f"Путь: {self.filepath}. "
                f"stderr: {stderr_text or 'пусто'}"
            )
        return self.filepath

    def abort(self) -> None:
        proc = self.proc
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=TERMINATE_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=TERMINATE_TIMEOUT)
        finally:
            self.proc = None

    @staticmethod
    def _read_stderr(proc: subprocess.Popen) -> str:
        if proc.stderr is None:
            return ""
        return proc.stderr.read().decode("utf-8", errors="replace").strip()
