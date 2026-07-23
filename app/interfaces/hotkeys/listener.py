from __future__ import annotations

import logging
import os
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from requests import RequestException

from app.domain.actions import SerialActionQueue
from app.domain.audio.recorder import VoiceRecorder
from app.domain.reading_context import ReadingContext
from app.domain.screenshot_archive import save_screenshot
from app.domain.status import AppStatus
from app.domain.telegram_delivery import TelegramDeliveryQueue
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

logger = logging.getLogger(__name__)

StatusCallback = Callable[[AppStatus, str, bool], None]


class ActionQueue(Protocol):
    def submit(self, target: Callable, args: tuple = ()) -> bool: ...

    def close(self) -> None: ...


class AnswerOverlay(Protocol):
    def start(self) -> None: ...

    def show(self, text: str) -> None: ...

    def hide(self) -> None: ...

    def close(self) -> None: ...


class TelegramDelivery(Protocol):
    def submit(self, text: str) -> bool: ...

    def submit_photos(
        self,
        photos: Sequence[bytes],
        caption: str | None = None,
    ) -> bool: ...

    def close(self) -> None: ...


class StopEvent(Protocol):
    def wait(self) -> object: ...


class _NullAnswerOverlay:
    def start(self) -> None:
        pass

    def show(self, text: str) -> None:
        pass

    def hide(self) -> None:
        pass

    def close(self) -> None:
        pass


try:
    import keyboard as _keyboard_module

    keyboard_module: Any | None = _keyboard_module
except ImportError:  # pragma: no cover - зависит от окружения Windows
    keyboard_module = None


def _default_take_screenshot() -> bytes:
    from app.domain.ocr.capture import take_screenshot

    image = take_screenshot()
    try:
        save_screenshot(image)
    except Exception:
        logger.exception("Не удалось сохранить снимок для последующего разбора")
    return image


def _missing_server_client(*_args, **_kwargs):
    raise RuntimeError("Серверный клиент не настроен")


class HotkeyService:
    def __init__(
        self,
        recorder: VoiceRecorder,
        transcribe_fn: Callable | None = None,
        solve_text_fn: Callable[[str], str] | None = None,
        solve_image_fn: Callable[..., str] | None = None,
        recognize_image_fn: Callable[[bytes], str] | None = None,
        send_message_fn: Callable[[str], None] | None = None,
        send_photo_fn: Callable[[bytes, str | None], None] | None = None,
        send_media_group_fn: Callable[[Sequence[bytes], str | None], None]
        | None = None,
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
        middle_click_factory: Callable[..., Any] = MiddleClickHook,
        answer_overlay: AnswerOverlay | None = None,
        telegram_delivery: TelegramDelivery | None = None,
        reading_context: ReadingContext | None = None,
    ) -> None:
        self.recorder = recorder
        self.transcribe = transcribe_fn or _missing_server_client
        self.solve_text = solve_text_fn or _missing_server_client
        self.solve_image = solve_image_fn or _missing_server_client
        self.recognize_image = recognize_image_fn or _missing_server_client
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
        self.answer_overlay: AnswerOverlay = answer_overlay or _NullAnswerOverlay()
        self.telegram_delivery: TelegramDelivery = (
            telegram_delivery
            or TelegramDeliveryQueue(
                send_message_fn or _missing_server_client,
                send_photo_fn,
                send_media_group_fn,
            )
        )
        self.reading_context = reading_context or ReadingContext()
        self._pending_context_images: list[bytes] = []
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

            answer = self.solve_text(self.fixed_prompt + text)
            self._show_answer(answer)
            self._queue_telegram(f"Ты продиктовал:\n{text}")
            self._queue_telegram(f"Ответ:\n{answer}")
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
            self.answer_overlay.hide()
            image = self.take_screenshot()
            self._process_prompt_image(image, prompt)
        except Exception as exc:
            self._report_error("Не удалось обработать снимок", exc)
        finally:
            with self._state_lock:
                self._processing = False

    def _handle_captured_prompt(self, image: bytes, prompt: str) -> None:
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

        self._report(AppStatus.WORKING, "Обрабатываю сохранённый снимок экрана")
        try:
            self._process_prompt_image(image, prompt)
        except Exception as exc:
            self._report_error("Не удалось обработать снимок", exc)
        finally:
            with self._state_lock:
                self._processing = False

    def _process_prompt_image(self, image: bytes, prompt: str) -> None:
        self._queue_screenshots(image)
        context_text = self.reading_context.text
        if context_text:
            answer = self.solve_image(image, prompt, context_text)
        else:
            answer = self.solve_image(image, prompt)
        self._show_answer(answer)
        self._queue_telegram(answer)
        self._report(AppStatus.READY, "Ответ по снимку готов", True)

    def capture_reading_context(self) -> None:
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

        self._report(AppStatus.WORKING, "Сохраняю часть большого текста")
        try:
            self.answer_overlay.hide()
            image = self.take_screenshot()
            self._store_reading_context(image)
        except Exception as exc:
            self._report_error("Не удалось сохранить часть текста", exc)
        finally:
            with self._state_lock:
                self._processing = False

    def clear_reading_context(self) -> None:
        update = self.reading_context.clear()
        with self._state_lock:
            self._pending_context_images.clear()
        logger.info("Контекст большого текста очищен")
        self._report(
            AppStatus.READY,
            f"Большой текст очищен: {update.total_chars} знаков",
        )

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
        return self._submit_captured_prompt(
            f"prompt-{index}",
            prompt,
        )

    def submit_mouse_prompt(self) -> bool:
        return self._submit_captured_prompt(
            "mouse-prompt",
            self.mouse_prompt,
        )

    def _submit_captured_prompt(self, key: str, prompt: str) -> bool:
        if not self._reserve_hotkey(key):
            return False
        with self._state_lock:
            recording = self.is_recording
        if recording:
            self._report(AppStatus.RECORDING, "Сначала остановите запись", True)
            return False
        try:
            self.answer_overlay.hide()
            image = self.take_screenshot()
        except Exception as exc:
            self._report_error("Не удалось снять задание", exc)
            return False
        accepted = self.action_queue.submit(
            self._handle_captured_prompt,
            (image, prompt),
        )
        if not accepted:
            self._report(AppStatus.BUSY, "Очередь действий заполнена", True)
        return accepted

    def submit_reading_context(self) -> bool:
        if not self._reserve_hotkey("reading-context"):
            return False
        with self._state_lock:
            recording = self.is_recording
        if recording:
            self._report(AppStatus.RECORDING, "Сначала остановите запись", True)
            return False
        try:
            self.answer_overlay.hide()
            image = self.take_screenshot()
        except Exception as exc:
            self._report_error("Не удалось снять часть большого текста", exc)
            return False
        accepted = self.action_queue.submit(self._store_reading_context, (image,))
        if not accepted:
            self._report(AppStatus.BUSY, "Очередь действий заполнена", True)
        return accepted

    def submit_clear_reading_context(self) -> bool:
        return self._submit_hotkey(
            "clear-reading-context",
            self.clear_reading_context,
            (),
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
        stop_event: StopEvent | None = None,
    ) -> None:
        keyboard_impl = keyboard_module_override or keyboard_module
        if keyboard_impl is None:
            raise RuntimeError("Пакет keyboard не установлен")

        try:
            self.answer_overlay.start()
        except Exception:
            logger.exception("Закрытое окно ответа недоступно")
            self.answer_overlay = _NullAnswerOverlay()

        print(
            f"Готово: {self.record_hotkey} — запись, колёсико — ответ по экрану, "
            "alt+колёсико — добавить большой текст, "
            "ctrl+колёсико — очистить большой текст"
        )
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
        self.telegram_delivery.close()
        self._unregister_middle_click()
        self.answer_overlay.close()
        keyboard_impl = self._keyboard_impl
        if keyboard_impl is not None and hasattr(keyboard_impl, "unhook_all_hotkeys"):
            keyboard_impl.unhook_all_hotkeys()
        if self.is_recording and hasattr(self.recorder, "abort"):
            self.recorder.abort()
        self.is_recording = False

    def _register_middle_click(self) -> None:
        if self._middle_click_hook is not None:
            return
        hook = self._middle_click_factory(
            self.submit_mouse_prompt,
            self.submit_reading_context,
            self.submit_clear_reading_context,
        )
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
        if not self._reserve_hotkey(key):
            return False

        accepted = self.action_queue.submit(target, args)
        if not accepted:
            self._report(AppStatus.BUSY, "Очередь действий заполнена", True)
        return accepted

    def _reserve_hotkey(self, key: str) -> bool:
        now = self._clock()
        with self._state_lock:
            previous = self._last_hotkey_at.get(key)
            if previous is not None and now - previous < HOTKEY_DEBOUNCE_SECONDS:
                return False
            self._last_hotkey_at[key] = now
        return True

    def _store_reading_context(self, image: bytes) -> None:
        self._report(AppStatus.WORKING, "Распознаю часть большого текста")
        with self._state_lock:
            self._pending_context_images.append(image)
        text = self.recognize_image(image)
        update = self.reading_context.add(text)
        if not text.strip():
            message = "На снимке не найден текст"
        elif update.duplicate:
            message = "Эта часть текста уже сохранена"
        else:
            total = f"{update.total_chars:,}".replace(",", " ")
            message = (
                f"Часть текста сохранена: {update.fragments}, всего {total} знаков"
            )
            if update.truncated:
                message += "; начало сокращено"
        logger.info(message)
        self._report(AppStatus.READY, message)

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

    def _show_answer(self, answer: str) -> None:
        try:
            self.answer_overlay.show(answer)
        except Exception:
            logger.exception("Не удалось показать ответ в закрытом окне")

    def _queue_telegram(self, text: str) -> None:
        try:
            accepted = self.telegram_delivery.submit(text)
        except Exception:
            logger.exception("Не удалось поставить сообщение Telegram в очередь")
            return
        if not accepted:
            logger.warning("Очередь отправки в Telegram заполнена")

    def _queue_screenshots(self, current_image: bytes) -> None:
        with self._state_lock:
            context_images = tuple(self._pending_context_images)
        photos = (*context_images, current_image)
        caption = (
            "Большой текст и текущее задание" if context_images else "Снимок задания"
        )
        try:
            accepted = self.telegram_delivery.submit_photos(photos, caption)
        except Exception:
            logger.exception("Не удалось поставить снимки Telegram в очередь")
            return
        if not accepted:
            logger.warning("Очередь отправки снимков в Telegram заполнена")
            return
        if context_images:
            with self._state_lock:
                del self._pending_context_images[: len(context_images)]


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
    answer_overlay = None
    if settings.show_answer_overlay:
        from app.interfaces.private_overlay import PrivateAnswerOverlay

        answer_overlay = PrivateAnswerOverlay()
    return HotkeyService(
        recorder=recorder,
        transcribe_fn=remote_client.transcribe,
        solve_text_fn=remote_client.solve_text,
        solve_image_fn=remote_client.solve_image,
        recognize_image_fn=remote_client.recognize_image,
        send_message_fn=remote_client.send_message,
        send_photo_fn=remote_client.send_photo,
        send_media_group_fn=remote_client.send_media_group,
        ping_fn=remote_client.ping,
        status_callback=status_callback,
        record_hotkey=settings.record_hotkey,
        mouse_prompt=settings.mouse_prompt,
        action_hotkeys=settings.action_hotkeys,
        prompts=settings.action_prompts,
        answer_overlay=answer_overlay,
    )


def main() -> None:
    build_hotkey_service().run()
