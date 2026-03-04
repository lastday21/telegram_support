from io import BytesIO
from pathlib import Path
from typing import Union

import pytesseract
import requests
from PIL import Image

from src.settings import get_settings

API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
DEFAULT_SYSTEM = (
    "Ты помощник: отвечай кратко, ясно, "
    "структурируй мысли, если нужно пиши по шагам."
)


class YandexGPTClient:
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        http_post=requests.post,
        image_open=Image.open,
        ocr_to_string=pytesseract.image_to_string,
        timeout: int = 120,
    ) -> None:
        self.http_post = http_post
        self.image_open = image_open
        self.ocr_to_string = ocr_to_string
        self.timeout = timeout
        self.model_uri = f"gpt://{folder_id}/aliceai-llm"
        self.headers = {
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
        }

    def gpt_request(
        self, user_text: str, system_prompt: str, temperature: float = 0.2
    ) -> str:
        body = {
            "modelUri": self.model_uri,
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
        resp = self.http_post(
            API_URL, headers=self.headers, json=body, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()["result"]["alternatives"][0]["message"]["text"].strip()

    def solve_text(
        self, user_text: str, system_prompt: str = DEFAULT_SYSTEM, temperature: float = 0
    ) -> str:
        if len(user_text.strip()) < 3:
            return "Слишком короткий запрос (нужно больше контекста)."
        try:
            return self.gpt_request(user_text, system_prompt, temperature)
        except Exception as exc:
            return f"Ошибка Yandex GPT: {exc}"

    def solve_image(
        self,
        image: Union[str, bytes],
        prompt: str = "Проанализируй текст на изображении",
    ) -> str:
        try:
            if isinstance(image, bytes):
                img = self.image_open(BytesIO(image))
            else:
                img = self.image_open(Path(image))
            text = self.ocr_to_string(
                img, lang="rus+eng", config="--oem 3 --psm 6"
            ).strip()
            if not text:
                return "Не удалось распознать текст на изображении."
            combined = f"{prompt}\n\n{text}"
            return self.gpt_request(combined, DEFAULT_SYSTEM)
        except Exception as exc:
            return f"Ошибка OCR/Yandex GPT: {exc}"


def build_gpt_client() -> YandexGPTClient:
    settings = get_settings()
    return YandexGPTClient(settings.yc_api_key, settings.yc_folder_id)


def _gpt_request(user_text: str, system_prompt: str, temperature: float = 0.2) -> str:
    return build_gpt_client().gpt_request(user_text, system_prompt, temperature)


def solve_text(
    user_text: str, system_prompt: str = DEFAULT_SYSTEM, temperature: float = 0
) -> str:
    return build_gpt_client().solve_text(user_text, system_prompt, temperature)


def solve_image(
    image: Union[str, bytes], prompt: str = "Проанализируй текст на изображении"
) -> str:
    return build_gpt_client().solve_image(image, prompt)
