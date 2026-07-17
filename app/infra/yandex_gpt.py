from typing import Union

import requests

from app.infra.yandex_ocr import recognize_text
from app.settings import DEFAULT_YC_MODEL, SUPPORTED_YC_MODELS, get_settings

API_URL = "https://ai.api.cloud.yandex.net/v1/chat/completions"
DEFAULT_MODEL = DEFAULT_YC_MODEL
DEFAULT_SYSTEM = (
    "Ты помощник: отвечай кратко, ясно, структурируй мысли, если нужно пиши по шагам."
)


class YandexServiceError(RuntimeError):
    pass


class YandexGPTClient:
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        model: str = DEFAULT_MODEL,
        http_post=requests.post,
        ocr_text_fn=recognize_text,
        timeout: int = 120,
    ) -> None:
        self.http_post = http_post
        self.ocr_text = ocr_text_fn
        self.timeout = timeout
        self.model_uri = (
            model if model.startswith("gpt://") else f"gpt://{folder_id}/{model}"
        )
        self.headers = {
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
            "OpenAI-Project": folder_id,
        }

    def gpt_request(
        self, user_text: str, system_prompt: str, temperature: float = 0.2
    ) -> str:
        body = {
            "model": self.model_uri,
            "stream": False,
            "temperature": temperature,
            "max_tokens": 700,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        resp = self.http_post(
            API_URL, headers=self.headers, json=body, timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def solve_text(
        self,
        user_text: str,
        system_prompt: str = DEFAULT_SYSTEM,
        temperature: float = 0,
    ) -> str:
        if len(user_text.strip()) < 3:
            return "Слишком короткий запрос (нужно больше контекста)."
        try:
            return self.gpt_request(user_text, system_prompt, temperature)
        except Exception as exc:
            raise YandexServiceError("Не удалось получить ответ от Яндекса") from exc

    def solve_image(
        self,
        image: Union[str, bytes],
        prompt: str = "Проанализируй текст на изображении",
    ) -> str:
        try:
            text = self.ocr_text(image).strip()
            if not text:
                print("[gpt] OCR returned empty text")
                return "Не удалось распознать текст на изображении."
            combined = f"{prompt}\n\n{text}"
            print(f"[gpt] sending OCR text to GPT: {len(text)} chars")
            answer = self.gpt_request(combined, DEFAULT_SYSTEM)
            print(f"[gpt] got answer from GPT: {len(answer)} chars")
            print(f"[gpt] answer text: {answer}")
            return answer
        except Exception as exc:
            raise YandexServiceError("Не удалось обработать изображение") from exc


def build_gpt_client(model: str | None = None) -> YandexGPTClient:
    settings = get_settings()
    selected_model = model or settings.yc_model
    if selected_model not in SUPPORTED_YC_MODELS:
        raise ValueError("Выбрана неподдерживаемая модель")
    return YandexGPTClient(
        settings.yc_api_key,
        settings.yc_folder_id,
        model=selected_model,
    )


def _gpt_request(user_text: str, system_prompt: str, temperature: float = 0.2) -> str:
    return build_gpt_client().gpt_request(user_text, system_prompt, temperature)


def solve_text(
    user_text: str,
    model: str | None = None,
    system_prompt: str = DEFAULT_SYSTEM,
    temperature: float = 0,
) -> str:
    return build_gpt_client(model).solve_text(user_text, system_prompt, temperature)


def solve_image(
    image: Union[str, bytes],
    prompt: str = "Проанализируй текст на изображении",
    model: str | None = None,
) -> str:
    return build_gpt_client(model).solve_image(image, prompt)
