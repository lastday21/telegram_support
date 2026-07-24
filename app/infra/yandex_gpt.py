import base64
from typing import Union

import requests

from app.infra.yandex_ocr import recognize_text
from app.infra.yandex_resilience import (
    YandexCallPolicy,
    YandexCircuitOpenError,
    default_yandex_call_policy,
)
from app.settings import (
    DEFAULT_YC_MODEL,
    DEFAULT_YC_VISION_MODEL,
    SUPPORTED_YC_MODELS,
    SUPPORTED_YC_VISION_MODELS,
    get_settings,
)

API_URL = "https://ai.api.cloud.yandex.net/v1/chat/completions"
DEFAULT_MODEL = DEFAULT_YC_MODEL
DEFAULT_VISION_MODEL = DEFAULT_YC_VISION_MODEL
DEFAULT_SYSTEM = (
    "Ты помощник: отвечай кратко, ясно, структурируй мысли, если нужно пиши по шагам."
)
DEFAULT_VISION_SYSTEM = (
    "Ты внимательно анализируешь изображение задания и решаешь его. "
    "Не выдумывай невидимые данные. Отвечай по-русски, кратко и точно."
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
        call_policy: YandexCallPolicy = default_yandex_call_policy,
    ) -> None:
        self.http_post = http_post
        self.ocr_text = ocr_text_fn
        self.timeout = timeout
        self.call_policy = call_policy
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

        def send_request():
            response = self.http_post(
                API_URL, headers=self.headers, json=body, timeout=self.timeout
            )
            response.raise_for_status()
            return response

        resp = self.call_policy.execute(send_request)
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
        except YandexCircuitOpenError:
            raise
        except Exception as exc:
            raise YandexServiceError("Не удалось получить ответ от Яндекса") from exc

    def solve_image(
        self,
        image: Union[str, bytes],
        prompt: str = "Проанализируй текст на изображении",
        context_text: str = "",
    ) -> str:
        try:
            text = self.ocr_text(image).strip()
            if not text:
                print("[gpt] OCR returned empty text")
                return "Не удалось распознать текст на изображении."
            normalized_context = context_text.strip()
            if normalized_context:
                combined = (
                    f"{prompt}\n\n"
                    "Ниже дан ранее собранный большой текст. Используй его как "
                    "источник для ответа, но отвечай только на задание с текущего "
                    "снимка. Не пытайся решать старые задания, случайно попавшие "
                    "в собранный текст.\n\n"
                    "<СОБРАННЫЙ_ТЕКСТ>\n"
                    f"{normalized_context}\n"
                    "</СОБРАННЫЙ_ТЕКСТ>\n\n"
                    "<ТЕКУЩИЙ_СНИМОК>\n"
                    f"{text}\n"
                    "</ТЕКУЩИЙ_СНИМОК>"
                )
            else:
                combined = f"{prompt}\n\n{text}"
            print(f"[gpt] sending OCR text to GPT: {len(text)} chars")
            answer = self.gpt_request(combined, DEFAULT_SYSTEM, temperature=0)
            print(f"[gpt] got answer from GPT: {len(answer)} chars")
            print(f"[gpt] answer text: {answer}")
            return answer
        except YandexCircuitOpenError:
            raise
        except Exception as exc:
            raise YandexServiceError("Не удалось обработать изображение") from exc

    def solve_vision_image(
        self,
        image: bytes,
        prompt: str,
    ) -> str:
        if not image:
            raise ValueError("Получен пустой снимок")
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Подсказка не может быть пустой")

        encoded_image = base64.b64encode(image).decode("ascii")
        body = {
            "model": self.model_uri,
            "stream": False,
            "temperature": 0,
            "max_tokens": 1000,
            "messages": [
                {"role": "system", "content": DEFAULT_VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": normalized_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded_image}"
                            },
                        },
                    ],
                },
            ],
        }

        def send_request():
            response = self.http_post(
                API_URL,
                headers=self.headers,
                json=body,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response

        try:
            response = self.call_policy.execute(send_request)
            return response.json()["choices"][0]["message"]["content"].strip()
        except YandexCircuitOpenError:
            raise
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


def build_vision_client() -> YandexGPTClient:
    settings = get_settings()
    if settings.yc_vision_model not in SUPPORTED_YC_VISION_MODELS:
        raise ValueError("Выбрана неподдерживаемая зрительная модель")
    return YandexGPTClient(
        settings.yc_api_key,
        settings.yc_folder_id,
        model=settings.yc_vision_model,
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
    context_text: str = "",
    model: str | None = None,
) -> str:
    return build_gpt_client(model).solve_image(image, prompt, context_text)


def solve_vision_image(image: bytes, prompt: str) -> str:
    return build_vision_client().solve_vision_image(image, prompt)
