import os
import threading
from collections.abc import Callable, Sequence

from src.domain.audio.recorder import VoiceRecorder
from src.infra.audio_devices import pick_default_devices
from src.infra.yandex_gpt import solve_image, solve_text
from src.infra.yandex_stt import transcribe
from src.interfaces.telegram.sender import send_message, send_photo
from src.prompts import PROMPTS
from src.settings import load_env

FIXED_PROMPT = "Дай развёрнутый полезный ответ для следующего текста или вопроса: "

try:
    import keyboard as keyboard_module
except ImportError:  # pragma: no cover - depends on local environment
    keyboard_module = None


def _default_take_screenshot() -> bytes:
    from src.domain.ocr.capture import take_screenshot

    return take_screenshot()


class HotkeyService:
    def __init__(
        self,
        recorder: VoiceRecorder,
        transcribe_fn: Callable = transcribe,
        solve_text_fn: Callable[[str], str] = solve_text,
        solve_image_fn: Callable[[bytes, str], str] = solve_image,
        send_message_fn: Callable[[str], None] = send_message,
        send_photo_fn: Callable[[bytes, str | None], None] = send_photo,
        take_screenshot_fn: Callable[[], bytes] | None = None,
        prompts: Sequence[str] = PROMPTS,
        fixed_prompt: str = FIXED_PROMPT,
    ) -> None:
        self.recorder = recorder
        self.transcribe = transcribe_fn
        self.solve_text = solve_text_fn
        self.solve_image = solve_image_fn
        self.send_message = send_message_fn
        self.send_photo = send_photo_fn
        self.take_screenshot = take_screenshot_fn or _default_take_screenshot
        self.prompts = list(prompts)
        self.fixed_prompt = fixed_prompt
        self.is_recording = False

    def toggle_recording(self) -> None:
        wav = None
        try:
            if not self.is_recording:
                self.recorder.start()
                self.is_recording = True
                print("Идёт запись аудио (Alt+Q -> стоп)")
                return

            wav = self.recorder.stop()
            self.is_recording = False

            text = self.transcribe(wav)
            print(f"Распознано: {text or '<пусто>'}")
            if not text.strip():
                return

            self.send_message(f"Ты продиктовал:\n{text}")
            answer = self.solve_text(self.fixed_prompt + text)
            self.send_message(f"Ответ:\n{answer}")
        except Exception:
            import traceback

            print("\n---- ERROR audio-module ----")
            traceback.print_exc()
            print("----------------------------\n")
        finally:
            if wav is not None and wav.exists():
                wav.unlink(missing_ok=True)

    def handle_prompt(self, prompt: str) -> None:
        try:
            img_bytes = self.take_screenshot()
            self.send_photo(img_bytes, caption=prompt)
            answer = self.solve_image(img_bytes, prompt)
            self.send_message(answer)
        except Exception as exc:
            import traceback

            traceback.print_exc()
            self.send_message(f"Ошибка модуля скриншота: {exc}")

    def register_hotkeys(
        self,
        keyboard_module_override=None,
        thread_factory: Callable[[Callable, tuple], None] | None = None,
    ) -> None:
        keyboard_impl = keyboard_module_override or keyboard_module
        if keyboard_impl is None:
            raise RuntimeError("keyboard package is not installed")

        thread_factory = thread_factory or _start_daemon_thread
        keyboard_impl.add_hotkey(
            "alt+q", lambda: thread_factory(self.toggle_recording, ())
        )
        for index, prompt in enumerate(self.prompts, start=1):
            keyboard_impl.add_hotkey(
                f"alt+{index}",
                lambda prompt_text=prompt: thread_factory(
                    self.handle_prompt, (prompt_text,)
                ),
            )

    def run(
        self,
        keyboard_module_override=None,
        thread_factory: Callable[[Callable, tuple], None] | None = None,
    ) -> None:
        keyboard_impl = keyboard_module_override or keyboard_module
        if keyboard_impl is None:
            raise RuntimeError("keyboard package is not installed")

        print("Готово! Alt+Q -> запись, Alt+1-Alt+9 -> скриншот + GPT")
        self.register_hotkeys(
            keyboard_module_override=keyboard_impl,
            thread_factory=thread_factory,
        )
        keyboard_impl.wait()


def _start_daemon_thread(target: Callable, args: tuple) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def _resolve_devices() -> tuple[str, str]:
    load_env()
    mic_env = os.getenv("MIC_DEVICE")
    mix_env = os.getenv("MIX_DEVICE")
    if mic_env and mix_env:
        return mic_env, mix_env
    return pick_default_devices()


def build_hotkey_service() -> HotkeyService:
    mic_device, mix_device = _resolve_devices()
    recorder = VoiceRecorder(mic_device=mic_device, mix_device=mix_device)
    return HotkeyService(recorder=recorder)


def _toggle_rec() -> None:
    build_hotkey_service().toggle_recording()


def _handler(prompt: str) -> None:
    build_hotkey_service().handle_prompt(prompt)


def main() -> None:
    build_hotkey_service().run()
