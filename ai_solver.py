import os, sys

# если мы запущены из PyInstaller, пути лежат в _MEIPASS
base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
tesseract_dir = os.path.join(base_path, "Tesseract-OCR")


import requests
import pytesseract
from PIL import Image
from pathlib import Path




YC_API_KEY = os.getenv("YC_API_KEY")
YC_FOLDER_ID = "b1gkuo48m02f6lf8ri8p"
API_URL      = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MODEL_URI    = f"gpt://{YC_FOLDER_ID}/yandexgpt/latest"
HEADERS      = {
    "Authorization": f"Api-Key {YC_API_KEY}",
    "Content-Type":  "application/json"
}

def solve_image(image_path: str, prompt: str) -> str:
    # OCR
    img = Image.open(Path(image_path))
    text = pytesseract.image_to_string(img, lang="rus+eng", config="--oem 3 --psm 6").strip()
    if not text:
        return "Не удалось распознать текст."

    # Собираем сообщения с фиксированным system и динамическим user=prompt
    body = {
        "modelUri": MODEL_URI,
        "completionOptions": {"stream": False, "temperature": 0, "maxTokens": 400},
        "messages": [
            {"role": "system", "text": "ты на mock-собеседовании, должен просто и доступно объяснить решение"},
            {"role": "user",   "text": f"{prompt}\n\n{text}"}
        ]
    }

    resp = requests.post(API_URL, headers=HEADERS, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()["result"]["alternatives"][0]["message"]["text"].strip()

def solve_text(user_text: str,
               system_prompt: str = "ты на mock-собеседовании, должен просто и доступно объяснить решение") -> str:
    """
    Шлёт в Yandex GPT чистый текст (без OCR).
    user_text — то, что пришло от пользователя.
    system_prompt — роль/контекст для модели.
    """
    body = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0,
            "maxTokens": 400
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user",   "text": user_text}
        ]
    }
    resp = requests.post(API_URL, headers=HEADERS, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()["result"]["alternatives"][0]["message"]["text"].strip()