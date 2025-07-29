from io import BytesIO
from typing import Union
import requests
from config import YC_API_KEY, YC_FOLDER_ID


API_URL   = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MODEL_URI = f"gpt://{YC_FOLDER_ID}/yandexgpt-lite/latest"
HEADERS   = {
    "Authorization": f"Api-Key {YC_API_KEY}",
    "Content-Type":  "application/json"
}
DEFAULT_SYSTEM = (
    "Ты помогаешь на mock-собеседовании: отвечай кратко, просто, "
    "доступным языком, без лишней «воды»."
)

# --- функции -----------------------------------------------------------------
def _gpt_request(user_text: str, system_prompt: str, temperature: float = 0.3) -> str:
    body = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": 700
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user",   "text": user_text}
        ]
    }
    resp = requests.post(API_URL, headers=HEADERS, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()["result"]["alternatives"][0]["message"]["text"].strip()


def solve_text(user_text: str,
               system_prompt: str = DEFAULT_SYSTEM,
               temperature: float = 0) -> str:
    """
    Отправляет чистый текст в Yandex GPT и возвращает ответ.
    """
    if len(user_text.strip()) < 3:
        return "🤷 Не понял вопрос (текст слишком короткий)."
    try:
        return _gpt_request(user_text, system_prompt, temperature)
    except Exception as e:
        return f"🛑 Ошибка Yandex GPT: {e}"



import pytesseract
from PIL import Image
from pathlib import Path

def solve_image(image: Union[str, bytes],
                prompt: str = "Объясни задачу простыми словами") -> str:
    """
    Делает OCR картинки, конкатенирует prompt + извлечённый текст,
    отправляет в Yandex GPT и возвращает ответ.
    """
    try:
        if isinstance(image, bytes):
            img = Image.open(BytesIO(image))
        else:
            img = Image.open(Path(image))
        text = pytesseract.image_to_string(
            img, lang="rus+eng", config="--oem 3 --psm 6"
        ).strip()
        if not text:
            return "Не удалось распознать текст на изображении."
        combined = f"{prompt}\n\n{text}"
        return _gpt_request(combined, DEFAULT_SYSTEM)
    except Exception as e:
        return f"🛑 OCR/Yandex GPT error: {e}"