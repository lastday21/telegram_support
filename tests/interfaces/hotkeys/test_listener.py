"""
Unit-тесты для interfaces.hotkeys.listener.

Покрываем:
    • _toggle_rec()  — сначала start → затем stop
    • _handler()     — скриншот, OCR, GPT, Telegram
"""

import importlib
import types
import pytest


# ---------------------------------------------------------------------
@pytest.fixture
def listener(monkeypatch, tmp_path):
    """
    Импортируем модуль и подменяем все внешние зависимости на заглушки.
    Возвращаем (mod, ctx), где ctx — словарь со счётчиками вызовов/аргументов.
    """
    ctx = {
        "rec_started": False,
        "rec_stopped": False,
        "messages": [],
        "photos": [],
        "solve_text": [],
        "solve_image": [],
    }

    # --------- Fake VoiceRecorder ------------------------------------
    class _FakeRec:
        def __init__(self):
            self.wav = tmp_path / "fake.wav"
            self.wav.write_bytes(b"RIFF....WAVEfmt")  # псевдо-файл

        def start(self):
            ctx["rec_started"] = True

        def stop(self):
            ctx["rec_stopped"] = True
            return self.wav

    # --------- Fake Telegram ----------------------------------------
    def _fake_send_msg(txt):
        ctx["messages"].append(txt)

    def _fake_send_photo(photo, caption=None):
        ctx["photos"].append((photo, caption))

    # --------- Fake STT / GPT ---------------------------------------
    def _fake_transcribe(wav):
        return "hello world"

    def _fake_solve_text(text):
        ctx["solve_text"].append(text)
        return "AI ANSWER"

    def _fake_solve_image(img, prompt):
        ctx["solve_image"].append((img, prompt))
        return "IMG ANSWER"

    # --------- Fake screenshot & OCR --------------------------------
    def _fake_take_screenshot(*a, **kw):
        return b"PNG_BYTES"

    fake_pil_img = types.SimpleNamespace(open=lambda buf: object())
    fake_tess = types.SimpleNamespace(image_to_string=lambda *a, **k: "OCR TEXT")

    # --------- Импортируем модуль и ставим моки ----------------------
    mod = importlib.import_module("src.interfaces.hotkeys.listener")

    monkeypatch.setattr(mod, "_rec", _FakeRec())
    monkeypatch.setattr(mod, "send_message", _fake_send_msg)
    monkeypatch.setattr(mod, "send_photo", _fake_send_photo)
    monkeypatch.setattr(mod, "transcribe", _fake_transcribe)
    monkeypatch.setattr(mod, "solve_text", _fake_solve_text)
    monkeypatch.setattr(mod, "solve_image", _fake_solve_image)
    monkeypatch.setattr(mod, "take_screenshot", _fake_take_screenshot)
    monkeypatch.setattr(mod, "Image", fake_pil_img)
    monkeypatch.setattr(mod, "pytesseract", fake_tess)

    mod._is_recording = False

    return mod, ctx


# ---------------------------------------------------------------------
def test_toggle_rec_start_and_stop(listener):
    """Первый вызов _toggle_rec() запускает запись, второй — останавливает."""
    mod, ctx = listener

    # ---- старт записи ----
    mod._toggle_rec()
    assert ctx["rec_started"] is True
    assert mod._is_recording is True
    # Никаких сообщений пока не должно быть
    assert ctx["messages"] == []

    # ---- стоп записи ----
    mod._toggle_rec()
    assert ctx["rec_stopped"] is True
    assert mod._is_recording is False
    # Должны прилететь 2 сообщения: «вы сказали …» и ответ GPT
    assert len(ctx["messages"]) == 2
    assert ctx["messages"][0].startswith("🗣 Вы сказали:")
    assert ctx["messages"][1].startswith("💡")
    # solve_text получил объединённый prompt
    assert ctx["solve_text"] and "hello world" in ctx["solve_text"][0]


def test_handler_screenshot_flow(listener):
    """_handler() делает скриншот → отправляет фото → GPT-ответ текстом."""
    mod, ctx = listener

    mod._handler("PROMPT_X")

    # Фото отправлено
    assert ctx["photos"] and ctx["photos"][0][0] == b"PNG_BYTES"
    # solve_image вызван с тем же prompt
    assert ctx["solve_image"] and ctx["solve_image"][0][1] == "PROMPT_X"
    # В Telegram ушло сообщение-ответ
    assert ctx["messages"][-1] == "IMG ANSWER"
