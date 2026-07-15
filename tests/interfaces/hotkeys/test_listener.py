from app.interfaces.hotkeys.listener import FIXED_PROMPT, HotkeyService


class _FakeRecorder:
    def __init__(self, wav_path):
        self.wav_path = wav_path
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
        return self.wav_path


def test_toggle_rec_start_and_stop(tmp_path):
    ctx = {
        "messages": [],
        "solve_text": [],
    }
    wav_path = tmp_path / "fake.wav"
    wav_path.write_bytes(b"RIFF....WAVEfmt")

    recorder = _FakeRecorder(wav_path)
    service = HotkeyService(
        recorder=recorder,
        transcribe_fn=lambda wav: "hello world",
        solve_text_fn=lambda text: ctx["solve_text"].append(text) or "AI ANSWER",
        send_message_fn=lambda text: ctx["messages"].append(text),
    )

    service.toggle_recording()
    assert recorder.started is True
    assert service.is_recording is True
    assert ctx["messages"] == []

    service.toggle_recording()
    assert recorder.stopped is True
    assert service.is_recording is False
    assert len(ctx["messages"]) == 2
    assert ctx["messages"][0].startswith("Ты продиктовал:")
    assert ctx["messages"][1].startswith("Ответ:")
    assert ctx["solve_text"] == [FIXED_PROMPT + "hello world"]
    assert not wav_path.exists()


def test_handler_screenshot_flow(capsys):
    ctx = {
        "messages": [],
        "photos": [],
        "solve_image": [],
    }
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        solve_image_fn=lambda img, prompt: (
            ctx["solve_image"].append((img, prompt)) or "IMG ANSWER"
        ),
        send_message_fn=lambda text: ctx["messages"].append(text),
        send_photo_fn=lambda photo, caption=None: ctx["photos"].append(
            (photo, caption)
        ),
        take_screenshot_fn=lambda: b"PNG_BYTES",
    )

    service.handle_prompt("PROMPT_X")
    out = capsys.readouterr().out

    assert ctx["photos"] == [(b"PNG_BYTES", "PROMPT_X")]
    assert ctx["solve_image"] == [(b"PNG_BYTES", "PROMPT_X")]
    assert ctx["messages"] == ["IMG ANSWER"]
    assert "Screenshot flow started" in out
    assert "Screenshot captured" in out
    assert "Screenshot sent to Telegram" in out
    assert "Screenshot answer ready" in out
    assert "Screenshot answer: IMG ANSWER" in out
