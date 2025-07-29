"""
Проверяем:
1. solve_text()      – короткий текст → early-return; длинный → зовёт _gpt_request.
2. solve_image()     – OCR + GPT: вызывается pytesseract и _gpt_request c комбинированным prompt.

Все внешние зависимости (HTTP, Pillow, Tesseract) мокируем, чтобы
тесты работали оффлайн и быстро.
"""

import types
import src.infra.yandex_gpt as gpt


def test_solve_text_too_short():
    """Если строка < 3 симв. → сразу 🤷 без вызова GPT."""
    assert (
        gpt.solve_text("ok")  # 2 символа
        == "🤷 Не понял вопрос (текст слишком короткий)."  # ожидаемый early-return
    )


def test_solve_text_calls_gpt(monkeypatch):
    """solve_text() должен прокинуть текст в _gpt_request и вернуть его ответ."""
    call = {}

    def _fake_req(user_text, system_prompt, temperature):
        call["args"] = (user_text, system_prompt, temperature)
        return "ANSWER"

    monkeypatch.setattr(gpt, "_gpt_request", _fake_req)

    out = gpt.solve_text("How to sort list?")
    assert out == "ANSWER" and "args" in call


class _FakeImg:
    """Минимальный объект, передаваемый в pytesseract.image_to_string."""

    pass


def test_solve_image_success(monkeypatch):
    """Корректный OCR → формируется комбинированный prompt и идёт запрос к GPT."""
    calls = {}

    # --- мокаем Image.open ----------------------------------------------------
    def _fake_open(fp):
        calls["image_opened"] = True
        return _FakeImg()

    monkeypatch.setattr(gpt, "Image", types.SimpleNamespace(open=_fake_open))

    def _fake_ocr(img, lang, config):
        calls["ocr_called"] = True
        return "SELECT * FROM table;"

    monkeypatch.setattr(
        gpt,
        "pytesseract",
        types.SimpleNamespace(image_to_string=_fake_ocr),
    )

    def _fake_req(user_text, system_prompt, temperature=0.3):
        calls["prompt"] = user_text
        return "SQL explanation"

    monkeypatch.setattr(gpt, "_gpt_request", _fake_req)

    result = gpt.solve_image(b"bytes", prompt="Объясни SQL")

    assert result == "SQL explanation"

    assert "Объясни SQL" in calls["prompt"] and "SELECT *" in calls["prompt"]
    assert calls.get("ocr_called") and calls.get("image_opened")


def test_solve_image_no_text(monkeypatch):
    """Когда OCR не распознал текст → функция возвращает сообщение об ошибке."""
    monkeypatch.setattr(
        gpt,
        "Image",
        types.SimpleNamespace(open=lambda fp: _FakeImg()),
    )
    monkeypatch.setattr(
        gpt,
        "pytesseract",
        types.SimpleNamespace(image_to_string=lambda *a, **kw: ""),
    )

    assert gpt.solve_image(b"bytes") == "Не удалось распознать текст на изображении."
