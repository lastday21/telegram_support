from __future__ import annotations

import os
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from requests import RequestException

from app.domain.actions import SerialActionQueue
from app.domain.audio.recorder import VoiceRecorder
from app.domain.status import AppStatus
from app.infra.audio_devices import pick_default_devices
from app.infra.remote_client import build_remote_client
from app.interfaces.hotkeys.middle_click import MiddleClickHook
from app.settings import (
    DEFAULT_ACTION_HOTKEYS,
    DEFAULT_ACTION_PROMPTS,
    DEFAULT_MOUSE_PROMPT,
    DEFAULT_RECORD_HOTKEY,
    ClientSettings,
    get_client_settings,
)

FIXED_PROMPT = (
    "Ниже распознан вопрос или условие задания. Определи, что требуется, "
    "и дай правильный ответ. Сначала напиши итог, затем краткое объяснение. "
    "Если это тест, укажи вариант и его текст. Текст: "
)
HOTKEY_DEBOUNCE_SECONDS = 0.45

StatusCallback = Callable[[AppStatus, str, bool], None]


class ActionQueue(Protocol):
    def submit(self, target: Callable, args: tuple = ()) -> bool: ...

    def close(self) -> None: ...


try:
    import keyboard as _keyboard_module

    keyboard_module: Any | None = _keyboard_module
except ImportError:  # pragma: no cover - зависит от окружения Windows
    keyboard_module = None


def _default_take_screenshot() -> bytes:
    from app.domain.ocr.capture import take_screenshot

    return take_screenshot()


def _missing_server_client(*_args, **_kwargs):
    raise RuntimeError("Серверный клиент не настроен")


class HotkeyService:
    def __init__(
        self,
        recorder: VoiceRecorder,
        transcribe_fn: Callable | None = None,
        solve_text_fn: Callable[[str], str] | None = None,
        solve_image_fn: Callable[[bytes, str], str] | None = None,
        send_message_fn: Callable[[str], None] | None = None,
        take_screenshot_fn: Callable[[], bytes] | None = None,
        ping_fn: Callable[[], bool] | None = None,
        status_callback: StatusCallback | None = None,
        action_queue: ActionQueue | None = None,
        clock: Callable[[], float] = time.monotonic,
        prompts: Sequence[str] = DEFAULT_ACTION_PROMPTS,
        fixed_prompt: str = FIXED_PROMPT,
        record_hotkey: str = DEFAULT_RECORD_HOTKEY,
        mouse_prompt: str = DEFAULT_MOUSE_PROMPT,
        action_hotkeys: Sequence[str] = DEFAULT_ACTION_HOTKEYS,
        middle_click_factory: Callable[[Callable[[], object]], Any] = MiddleClickHook,
    ) -> None:
        self.recorder = recorder
        self.transcribe = transcribe_fn or _missing_server_client
        self.solve_text = solve_text_fn or _missing_server_client
        self.solve_image = solve_image_fn or _missing_server_client
        self.send_message = send_message_fn or _missing_server_client
        self.take_screenshot = take_screenshot_fn or _default_take_screenshot
        self.ping = ping_fn
        self.status_callback = status_callback
        self.prompts = list(prompts)
        self.fixed_prompt = fixed_prompt
        self.record_hotkey = record_hotkey
        self.mouse_prompt = mouse_prompt
        self.action_hotkeys = list(action_hotkeys)
        self.is_recording = False
        self._processing = False
        self._state_lock = threading.Lock()
        self._clock = clock
        self._last_hotkey_at: dict[str, float] = {}
        self._keyboard_impl = None
        self._middle_click_factory = middle_click_factory
        self._middle_click_hook: Any | None = None
        self._closed = False
        self.action_queue = action_queue or SerialActionQueue(
            on_error=self._handle_queue_error
        )

    def toggle_recording(self) -> None:
        wav = None
        with self._state_lock:
            if self._processing:
                busy = True
                starting = False
            else:
                busy = False
                starting = not self.is_recording
                self._processing = True

        if busy:
            self._report(AppStatus.BUSY, "Предыдущее действие ещё выполняется", True)
            return

        if starting:
            try:
                self.recorder.start()
                with self._state_lock:
                    self.is_recording = True
                self._report(AppStatus.RECORDING, "Идёт запись")
            except Exception as exc:
                with self._state_lock:
                    self.is_recording = False
                self._report_error("Не удалось начать запись", exc)
            finally:
                with self._state_lock:
                    self._processing = False
            return

        self._report(AppStatus.WORKING, "Останавливаю и обрабатываю запись")
        try:
            wav = self.recorder.stop()
            with self._state_lock:
                self.is_recording = False

            text = self.transcribe(wav)
            if not text.strip():
                self._report(AppStatus.READY, "Речь не распознана", True)
                return

            self.send_message(f"Ты продиктовал:\n{text}")
            answer = self.solve_text(self.fixed_prompt + text)
            self.send_message(f"Ответ:\n{answer}")
            self._report(AppStatus.READY, "Ответ готов", True)
        except Exception as exc:
            with self._state_lock:
                self.is_recording = False
            self._report_error("Не удалось обработать запись", exc)
        finally:
            with self._state_lock:
                self._processing = False
            if wav is not None and wav.exists():
                wav.unlink(missing_ok=True)

    def handle_prompt(self, prompt: str) -> None:
        with self._state_lock:
            if self._processing or self.is_recording:
                busy = True
                recording = self.is_recording
            else:
                busy = False
                recording = False
                self._processing = True

        if busy:
            status = AppStatus.RECORDING if recording else AppStatus.BUSY
            message = (
                "Сначала остановите запись"
                if recording
                else "Сначала завершите текущее действие"
            )
            self._report(status, message, True)
            return

        self._report(AppStatus.WORKING, "Обрабатываю снимок экрана")
        try:
            image = self.take_screenshot()
            answer = self.solve_image(image, prompt)
            self.send_message(answer)
            self._report(AppStatus.READY, "Ответ по снимку готов", True)
        except Exception as exc:
            self._report_error("Не удалось обработать снимок", exc)
            try:
                self.send_message("Не удалось обработать снимок экрана")
            except Exception:
                pass
        finally:
            with self._state_lock:
                self._processing = False

    def check_server(self) -> bool:
        if self.ping is None:
            self._report(AppStatus.READY, "Готово")
            return True
        self._report(AppStatus.WORKING, "Проверяю сервер")
        try:
            if not self.ping():
                raise RuntimeError("Сервер вернул неожиданный ответ")
        except Exception as exc:
            self._report_error("Сервер недоступен", exc, disconnected=True)
            return False
        self._report(AppStatus.READY, "Сервер доступен")
        return True

    def submit_toggle_recording(self) -> bool:
        return self._submit_hotkey(
            "recording",
            self.toggle_recording,
            (),
        )

    def submit_prompt(self, prompt: str, index: int) -> bool:
        return self._submit_hotkey(
            f"prompt-{index}",
            self.handle_prompt,
            (prompt,),
        )

    def submit_mouse_prompt(self) -> bool:
        return self._submit_hotkey(
            "mouse-prompt",
            self.handle_prompt,
            (self.mouse_prompt,),
        )

    def submit_check_server(self) -> bool:
        accepted = self.action_queue.submit(self.check_server)
        if not accepted:
            self._report(AppStatus.BUSY, "Очередь действий заполнена", True)
        return accepted

    def register_hotkeys(
        self,
        keyboard_module_override=None,
        thread_factory: Callable[[Callable, tuple], None] | None = None,
    ) -> None:
        keyboard_impl = keyboard_module_override or keyboard_module
        if keyboard_impl is None:
            raise RuntimeError("Пакет keyboard не установлен")
        self._keyboard_impl = keyboard_impl

        if thread_factory is None:
            keyboard_impl.add_hotkey(self.record_hotkey, self.submit_toggle_recording)
            for index, (hotkey, prompt) in enumerate(
                zip(self.action_hotkeys, self.prompts, strict=True), start=1
            ):
                keyboard_impl.add_hotkey(
                    hotkey,
                    lambda prompt_text=prompt, prompt_index=index: self.submit_prompt(
                        prompt_text, prompt_index
                    ),
                )
            self._register_middle_click()
            return

        keyboard_impl.add_hotkey(
            self.record_hotkey, lambda: thread_factory(self.toggle_recording, ())
        )
        for hotkey, prompt in zip(self.action_hotkeys, self.prompts, strict=True):
            keyboard_impl.add_hotkey(
                hotkey,
                lambda prompt_text=prompt: thread_factory(
                    self.handle_prompt, (prompt_text,)
                ),
            )
        self._register_middle_click()

    def run(
        self,
        keyboard_module_override=None,
        thread_factory: Callable[[Callable, tuple], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        keyboard_impl = keyboard_module_override or keyboard_module
        if keyboard_impl is None:
            raise RuntimeError("Пакет keyboard не установлен")

        print(f"Готово: {self.record_hotkey} — запись, колёсико — ответ по экрану")
        self.register_hotkeys(
            keyboard_module_override=keyboard_impl,
            thread_factory=thread_factory,
        )
        self.submit_check_server()
        try:
            if stop_event is None:
                keyboard_impl.wait()
            else:
                stop_event.wait()
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.action_queue.close()
        self._unregister_middle_click()
        keyboard_impl = self._keyboard_impl
        if keyboard_impl is not None and hasattr(keyboard_impl, "unhook_all_hotkeys"):
            keyboard_impl.unhook_all_hotkeys()
        if self.is_recording and hasattr(self.recorder, "abort"):
            self.recorder.abort()
        self.is_recording = False

    def _register_middle_click(self) -> None:
        if self._middle_click_hook is not None:
            return
        hook = self._middle_click_factory(self.submit_mouse_prompt)
        hook.start()
        self._middle_click_hook = hook

    def _unregister_middle_click(self) -> None:
        if self._middle_click_hook is not None:
            self._middle_click_hook.stop()
        self._middle_click_hook = None

    def _submit_hotkey(
        self,
        key: str,
        target: Callable,
        args: tuple,
    ) -> bool:
        now = self._clock()
        with self._state_lock:
            previous = self._last_hotkey_at.get(key)
            if previous is not None and now - previous < HOTKEY_DEBOUNCE_SECONDS:
                return False
            self._last_hotkey_at[key] = now

        accepted = self.action_queue.submit(target, args)
        if not accepted:
            self._report(AppStatus.BUSY, "Очередь действий заполнена", True)
        return accepted

    def _report(
        self,
        status: AppStatus,
        message: str,
        notify: bool = False,
    ) -> None:
        print(f"[SmartHelper] {message}")
        if self.status_callback is None:
            return
        try:
            self.status_callback(status, message, notify)
        except Exception:
            traceback.print_exc()

    def _report_error(
        self,
        message: str,
        exc: Exception,
        disconnected: bool = False,
    ) -> None:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        status = (
            AppStatus.DISCONNECTED
            if disconnected or isinstance(exc, RequestException)
            else AppStatus.ERROR
        )
        self._report(status, message, True)

    def _handle_queue_error(self, exc: Exception) -> None:
        self._report_error("Не удалось выполнить действие", exc)


def _resolve_devices(
    settings: ClientSettings | None = None,
) -> tuple[str, str | None]:
    settings = settings or get_client_settings()
    mic_env = settings.mic_device or os.getenv("MIC_DEVICE")
    mix_env = settings.mix_device or os.getenv("MIX_DEVICE")
    if mic_env:
        return mic_env, mix_env
    return pick_default_devices()


def build_hotkey_service(
    status_callback: StatusCallback | None = None,
) -> HotkeyService:
    settings = get_client_settings()
    mic_device, mix_device = _resolve_devices(settings)
    recorder = VoiceRecorder(mic_device=mic_device, mix_device=mix_device)
    remote_client = build_remote_client(settings)
    return HotkeyService(
        recorder=recorder,
        transcribe_fn=remote_client.transcribe,
        solve_text_fn=remote_client.solve_text,
        solve_image_fn=remote_client.solve_image,
        send_message_fn=remote_client.send_message,
        ping_fn=remote_client.ping,
        status_callback=status_callback,
        record_hotkey=settings.record_hotkey,
        mouse_prompt=settings.mouse_prompt,
        action_hotkeys=settings.action_hotkeys,
        prompts=settings.action_prompts,
    )


def main() -> None:
    build_hotkey_service().run()
