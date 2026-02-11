import subprocess
from datetime import datetime
from pathlib import Path


class VoiceRecorder:
    def __init__(self, mic_device: str, mix_device: str):
        self.microphone_device = mic_device
        self.system_mix_device = mix_device
        self.process: subprocess.Popen | None = None
        self.proc: subprocess.Popen | None = None
        self.output_file_path: Path | None = None
        self.filepath: Path | None = None

    def start(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file_path = Path(f"record_{timestamp}.wav")
        self.output_file_path = output_file_path
        self.filepath = output_file_path

        ffmpeg_command = (
            "ffmpeg -y -loglevel error "
            f'-f dshow -i "audio={self.system_mix_device}" '
            f'-f dshow -i "audio={self.microphone_device}" '
            "-filter_complex amix=inputs=2:normalize=0 "
            f'-ac 1 -ar 16000 "{output_file_path}"'
        )
        self.process = subprocess.Popen(
            ffmpeg_command,
            shell=True,
            stdin=subprocess.PIPE,
        )
        self.proc = self.process

    def stop(self) -> Path:
        if self.process is None and self.proc is not None:
            self.process = self.proc

        if self.process is None:
            raise RuntimeError("Запись не запущена")

        try:
            assert self.process.stdin is not None, "stdin недоступен"
            self.process.stdin.write(b"q")
            self.process.stdin.flush()
        except Exception as error:
            print("Не удалось остановить FFmpeg через stdin:", error)

        self.process.wait(timeout=5)

        if self.output_file_path is None and self.filepath is not None:
            self.output_file_path = self.filepath

        if self.output_file_path is None:
            raise RuntimeError("Путь к аудиофайлу не установлен")

        self.filepath = self.output_file_path
        return self.output_file_path
