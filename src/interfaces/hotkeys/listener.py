import threading
import keyboard
from PIL import Image
import pytesseract
import os

from src.domain.audio.recorder import VoiceRecorder
from src.infra.yandex_stt import transcribe
from src.infra.yandex_gpt import solve_text, solve_image
from src.interfaces.telegram.sender import send_message, send_photo
from src.domain.ocr.capture import take_screenshot
from io import BytesIO
from src.infra.audio_devices import pick_default_devices


FIXED_PROMPT = "Расскажи максимально подробно про следующую тему/напиши код: "


def _resolve_devices() -> tuple[str, str]:
    """Берём устройства из ENV, а если их нет — ищем автоматически."""
    mic_env = os.getenv("MIC_DEVICE")
    mix_env = os.getenv("MIX_DEVICE")
    if mic_env and mix_env:
        return mic_env, mix_env
    return pick_default_devices()


MIC_DEVICE, MIX_DEVICE = _resolve_devices()
_rec = VoiceRecorder(mic_device=MIC_DEVICE, mix_device=MIX_DEVICE)
# MIC_DEVICE = (
#     "@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\\"
#     "wave_{EBB798E2-2326-4DC4-A40F-5BD075C42CDC}"
# )
# MIX_DEVICE = (
#     "@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\\"
#     "wave_{108367BD-4575-4D6D-9B91-5AF7AF0FBEA9}"
# )
#
# _rec = VoiceRecorder(
#     mic_device="Набор микрофонов (Технология Intel® Smart Sound для цифровых микрофонов)",
#     mix_device="Стерео микшер (Realtek(R) Audio)",
# )
_is_recording = False


def _toggle_rec():
    global _is_recording
    wav = None
    try:
        if not _is_recording:
            _rec.start()
            _is_recording = True
            print("🎙 Запись началась (Alt+Q — стоп)")
        else:
            wav = _rec.stop()
            _is_recording = False

            text = transcribe(wav)
            print(f"📝 Распознано: {text or '<пусто>'}")
            if not text.strip():
                return

            send_message(f"🗣 Вы сказали:\n{text}")
            answer = solve_text(FIXED_PROMPT + text)
            send_message(f"💡 {answer}")

    except Exception:
        import traceback

        print("\n—— ERROR audio-module ———")
        traceback.print_exc()
        print("——————————————————————\n")

    finally:
        if wav is not None and wav.exists():
            wav.unlink(missing_ok=True)


def _handler(prompt: str):
    try:
        img_bytes = take_screenshot()
        send_photo(img_bytes, caption=prompt)

        ocr_text = pytesseract.image_to_string(
            Image.open(BytesIO(img_bytes)), lang="rus+eng", config="--oem 3 --psm 6"
        ).strip()

        print("\n===== AI INPUT =====")
        print(prompt, ocr_text, sep="\n")
        print("===== END INPUT =====\n")

        answer = solve_image(img_bytes, prompt)
        send_message(answer)
    except Exception as exc:
        import traceback

        traceback.print_exc()
        send_message(f"🚨 ERROR screenshot-module: {exc}")


# ──────────────────  Список промптов Alt+1…9  ─────────────────
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


# ──────────────────── Регистрация хоткеев ────────────────────
def main():
    print("Готово!  Alt+Q — аудио,  Alt+1…Alt+9 — скриншот + GPT")

    keyboard.add_hotkey(
        "alt+q", lambda: threading.Thread(target=_toggle_rec, daemon=True).start()
    )
    for i, prm in enumerate(PROMPTS, start=1):
        keyboard.add_hotkey(
            f"alt+{i}",
            lambda p=prm: threading.Thread(
                target=_handler, args=(p,), daemon=True
            ).start(),
        )
    keyboard.wait()


if __name__ == "__main__":
    main()
