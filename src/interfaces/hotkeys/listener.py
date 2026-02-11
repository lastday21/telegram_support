import os
import threading

import keyboard
import pytesseract
from PIL import Image

from src.domain.audio.recorder import VoiceRecorder
from src.domain.ocr.capture import take_screenshot
from src.infra.audio_devices import pick_default_devices
from src.infra.yandex_gpt import solve_image, solve_text
from src.infra.yandex_stt import transcribe
from src.interfaces.telegram.sender import send_message, send_photo

FIXED_PROMPT = "Расскажи максимально подробно про следующую тему/напиши код: "

PROMPTS = [
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


def _resolve_devices() -> tuple[str, str]:
    mic = os.getenv("MIC_DEVICE")
    mix = os.getenv("MIX_DEVICE")
    if mic and mix:
        return mic, mix
    return pick_default_devices()


def _run_async(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


def _transcribe_recording(wav_path) -> str:
    try:
        return transcribe(wav_path).strip()
    finally:
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)


MIC_DEVICE, MIX_DEVICE = _resolve_devices()
_rec = VoiceRecorder(mic_device=MIC_DEVICE, mix_device=MIX_DEVICE)
_is_recording = False


def _toggle_rec() -> None:
    global _is_recording

    try:
        if not _is_recording:
            _rec.start()
            _is_recording = True
            print("Запись началась (Alt+Q — стоп)")
            return

        wav_path = _rec.stop()
        _is_recording = False

        text = _transcribe_recording(wav_path)
        if not text:
            return

        send_message(f"🗣 Вы сказали:\n{text}")
        answer = solve_text(FIXED_PROMPT + text)
        send_message(f"💡 {answer}")
    except Exception as error:
        print(f"Ошибка обработки аудио: {error}")


def _handler(prompt: str) -> None:
    try:
        image_bytes = take_screenshot()
        send_photo(image_bytes, caption=prompt)

        answer = solve_image(image_bytes, prompt)
        send_message(answer)
    except Exception as error:
        send_message(f"🚨 Ошибка обработки скриншота: {error}")


def main() -> None:
    print("Готово! Alt+Q — аудио, Alt+1…Alt+9 — скриншот + GPT")

    keyboard.add_hotkey("alt+q", lambda: _run_async(_toggle_rec))
    for index, prompt in enumerate(PROMPTS, start=1):
        keyboard.add_hotkey(f"alt+{index}", lambda p=prompt: _run_async(_handler, p))

    keyboard.wait()


if __name__ == "__main__":
    main()
