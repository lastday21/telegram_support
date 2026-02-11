"""
Unit-тесты для interfaces.hotkeys.listener.

Покрываем:
    • handle_audio_hotkey_press()      — сначала start → затем stop
    • handle_screenshot_hotkey_press() — скриншот, GPT и Telegram
"""

import importlib
import pytest


@pytest.fixture
def listener(monkeypatch, tmp_path):
    call_state = {
        "recording_started": False,
        "recording_stopped": False,
        "messages": [],
        "photos": [],
        "solve_text_calls": [],
        "solve_image_calls": [],
    }

    class FakeVoiceRecorder:
        def __init__(self):
            self.output_file_path = tmp_path / "fake.wav"
            self.output_file_path.write_bytes(b"RIFF....WAVEfmt")

        def start(self):
            call_state["recording_started"] = True

        def stop(self):
            call_state["recording_stopped"] = True
            return self.output_file_path

    def fake_send_message(text):
        call_state["messages"].append(text)

    def fake_send_photo(photo, caption=None):
        call_state["photos"].append((photo, caption))

    def fake_transcribe(_audio_file_path):
        return "hello world"

    def fake_solve_text(text):
        call_state["solve_text_calls"].append(text)
        return "ANSWER"

    def fake_solve_image(image, prompt):
        call_state["solve_image_calls"].append((image, prompt))
        return "IMAGE ANSWER"

    def fake_take_screenshot(*_args, **_kwargs):
        return b"PNG_BYTES"

    listener_module = importlib.import_module("src.interfaces.hotkeys.listener")

    monkeypatch.setattr(listener_module, "voice_recorder", FakeVoiceRecorder())
    monkeypatch.setattr(listener_module, "send_message", fake_send_message)
    monkeypatch.setattr(listener_module, "send_photo", fake_send_photo)
    monkeypatch.setattr(listener_module, "transcribe", fake_transcribe)
    monkeypatch.setattr(listener_module, "solve_text", fake_solve_text)
    monkeypatch.setattr(listener_module, "solve_image", fake_solve_image)
    monkeypatch.setattr(listener_module, "take_screenshot", fake_take_screenshot)

    listener_module.is_recording_audio = False

    return listener_module, call_state


def test_toggle_rec_start_and_stop(listener):
    listener_module, call_state = listener

    listener_module.handle_audio_hotkey_press()
    assert call_state["recording_started"] is True
    assert listener_module.is_recording_audio is True
    assert call_state["messages"] == []

    listener_module.handle_audio_hotkey_press()
    assert call_state["recording_stopped"] is True
    assert listener_module.is_recording_audio is False
    assert len(call_state["messages"]) == 2
    assert call_state["messages"][0].startswith("🗣 Вы сказали:")
    assert call_state["messages"][1].startswith("💡")
    assert call_state["solve_text_calls"]
    assert "hello world" in call_state["solve_text_calls"][0]


def test_handler_screenshot_flow(listener):
    listener_module, call_state = listener

    listener_module.handle_screenshot_hotkey_press("PROMPT_X")

    assert call_state["photos"]
    assert call_state["photos"][0][0] == b"PNG_BYTES"
    assert call_state["solve_image_calls"]
    assert call_state["solve_image_calls"][0][1] == "PROMPT_X"
    assert call_state["messages"][-1] == "IMAGE ANSWER"
