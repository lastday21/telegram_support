import os
import threading
from pathlib import Path
from typing import Callable

import keyboard

from src.domain.audio.recorder import VoiceRecorder
from src.domain.ocr.capture import take_screenshot
from src.infra.audio_devices import pick_default_devices
from src.infra.yandex_gpt import solve_image, solve_text
from src.infra.yandex_stt import transcribe
from src.interfaces.telegram.sender import send_message, send_photo

VOICE_PROMPT_PREFIX = "Расскажи максимально подробно про следующую тему/напиши код: "

SCREENSHOT_PROMPTS = [
    """У меня есть учебная задача по backend на Python. Определи, к какому типу она относится: что приходит на вход, что нужно вернуть на выходе и какие ограничения есть? Объясни максимально просто, без сложных терминов.""",
    """У меня есть учебная задача по backend на Python. Опиши, какой алгоритм подходит для её решения: как он работает и почему его стоит выбрать? Приведи простое описание и название алгоритма.""",
    """У меня есть учебная задача по backend на Python. Какая структура данных лучше всего подходит для решения этой задачи и почему? Покажи небольшой пример в коде.""",
    """У меня есть учебная задача по backend на Python. Разбей процесс написания решения на понятные шаги: опиши каждый шаг и покажи пример кода по частям, а в конце собери полный вариант.""",
    """У меня есть учебная задача по backend на Python. Объясни сложность предлагаемого алгоритма простыми словами и предложи, как его можно улучшить при большем времени.""",
    """У меня есть учебная задача по backend на Python. Составь краткое описание решения по пунктам, чтобы я мог пересказать его своими словами.""",
    """У меня есть учебная задача по backend на Python. Напиши полный код решения с комментариями к каждому важному фрагменту.""",
    """У меня есть учебная задача по backend на Python. Напиши полный код решения без комментариев, чтобы можно было сразу проверить работу.""",
    """У меня есть учебная задача по backend на Python. Подскажи, какие вопросы могут задать по этому решению, и дай простые понятные ответы на них.""",
]


def _resolve_audio_devices() -> tuple[str, str]:
    microphone_device = os.getenv("MIC_DEVICE")
    stereo_mix_device = os.getenv("MIX_DEVICE")
    if microphone_device and stereo_mix_device:
        return microphone_device, stereo_mix_device
    return pick_default_devices()


def _start_background_task(task: Callable, *args) -> None:
    threading.Thread(target=task, args=args, daemon=True).start()


def _transcribe_and_cleanup(audio_file_path: Path) -> str:
    try:
        return transcribe(audio_file_path).strip()
    finally:
        if audio_file_path.exists():
            audio_file_path.unlink(missing_ok=True)


MIC_DEVICE, MIX_DEVICE = _resolve_audio_devices()
voice_recorder = VoiceRecorder(mic_device=MIC_DEVICE, mix_device=MIX_DEVICE)
is_recording_audio = False


def handle_audio_hotkey_press() -> None:
    global is_recording_audio

    try:
        if not is_recording_audio:
            voice_recorder.start()
            is_recording_audio = True
            print("Запись началась (Alt+Q — стоп)")
            return

        recorded_file_path = voice_recorder.stop()
        is_recording_audio = False

        recognized_text = _transcribe_and_cleanup(recorded_file_path)
        if not recognized_text:
            return

        send_message(f"🗣 Вы сказали:\n{recognized_text}")
        answer_text = solve_text(VOICE_PROMPT_PREFIX + recognized_text)
        send_message(f"💡 {answer_text}")
    except Exception as error:
        print(f"Ошибка обработки аудио: {error}")


def handle_screenshot_hotkey_press(prompt_text: str) -> None:
    try:
        screenshot_bytes = take_screenshot()
        send_photo(screenshot_bytes, caption=prompt_text)

        answer_text = solve_image(screenshot_bytes, prompt_text)
        send_message(answer_text)
    except Exception as error:
        send_message(f"🚨 Ошибка обработки скриншота: {error}")


def main() -> None:
    print("Готово! Alt+Q — аудио, Alt+1…Alt+9 — скриншот + GPT")

    keyboard.add_hotkey("alt+q", lambda: _start_background_task(handle_audio_hotkey_press))
    for prompt_index, prompt_text in enumerate(SCREENSHOT_PROMPTS, start=1):
        keyboard.add_hotkey(
            f"alt+{prompt_index}",
            lambda prompt=prompt_text: _start_background_task(handle_screenshot_hotkey_press, prompt),
        )

    keyboard.wait()


if __name__ == "__main__":
    main()
