from io import BytesIO
from pathlib import Path
from typing import Union

import pytesseract
import requests
from PIL import Image

from src.settings import YC_API_KEY, YC_FOLDER_ID

GPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
GPT_MODEL_URI = f"gpt://{YC_FOLDER_ID}/yandexgpt-lite/latest"
GPT_HEADERS = {
    "Authorization": f"Api-Key {YC_API_KEY}",
    "Content-Type": "application/json",
}
DEFAULT_SYSTEM_PROMPT = (
    "Ты помогаешь: отвечай кратко, просто, "
    "доступным языком, без лишней «воды»."
)


def _gpt_request(user_text: str, system_prompt: str, temperature: float = 0.3) -> str:
    request_body = {
        "modelUri": GPT_MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": 700,
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_text},
        ],
    }

    response = requests.post(
        GPT_API_URL,
        headers=GPT_HEADERS,
        json=request_body,
        timeout=120,
    )
    response.raise_for_status()

    return response.json()["result"]["alternatives"][0]["message"]["text"].strip()


def solve_text(
    user_text: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    temperature: float = 0,
) -> str:
    if len(user_text.strip()) < 3:
        return "🤷 Не понял вопрос (текст слишком короткий)."

    try:
        return _gpt_request(user_text, system_prompt, temperature)
    except Exception as error:
        return f"🛑 Ошибка Yandex GPT: {error}"


def solve_image(
    image: Union[str, bytes],
    prompt: str = "Объясни задачу простыми словами",
) -> str:
    try:
        if isinstance(image, bytes):
            image_object = Image.open(BytesIO(image))
        else:
            image_object = Image.open(Path(image))

        extracted_text = pytesseract.image_to_string(
            image_object,
            lang="rus+eng",
            config="--oem 3 --psm 6",
        ).strip()

        if not extracted_text:
            return "Не удалось распознать текст на изображении."

        prompt_with_ocr_text = f"{prompt}\n\n{extracted_text}"
        return _gpt_request(prompt_with_ocr_text, DEFAULT_SYSTEM_PROMPT)
    except Exception as error:
        return f"🛑 OCR/Yandex GPT error: {error}"
