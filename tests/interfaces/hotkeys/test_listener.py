from app.domain.status import AppStatus
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


class _FakeOverlay:
    def __init__(self, events=None):
        self.events = events if events is not None else []

    def start(self):
        self.events.append("overlay:start")

    def show(self, text):
        self.events.append(("overlay:show", text))

    def hide(self):
        self.events.append("overlay:hide")

    def close(self):
        self.events.append("overlay:close")


class _ImmediateDelivery:
    def __init__(self, send):
        self.send = send

    def submit(self, text):
        self.send(text)
        return True

    def close(self):
        pass


def test_toggle_rec_start_and_stop(tmp_path):
    ctx = {
        "messages": [],
        "solve_text": [],
    }
    wav_path = tmp_path / "fake.wav"
    wav_path.write_bytes(b"RIFF....WAVEfmt")

    recorder = _FakeRecorder(wav_path)
    statuses = []
    overlay_events = []
    service = HotkeyService(
        recorder=recorder,
        transcribe_fn=lambda wav: "hello world",
        solve_text_fn=lambda text: ctx["solve_text"].append(text) or "AI ANSWER",
        send_message_fn=lambda text: ctx["messages"].append(text),
        telegram_delivery=_ImmediateDelivery(ctx["messages"].append),
        status_callback=lambda status, message, notify: statuses.append(
            (status, message, notify)
        ),
        answer_overlay=_FakeOverlay(overlay_events),
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
    assert overlay_events == [("overlay:show", "AI ANSWER")]
    assert ctx["solve_text"] == [FIXED_PROMPT + "hello world"]
    assert not wav_path.exists()
    assert statuses[-1] == (AppStatus.READY, "Ответ готов", True)


def test_handler_screenshot_flow():
    ctx = {
        "messages": [],
        "solve_image": [],
    }
    events = []
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        solve_image_fn=lambda img, prompt: (
            events.append("solve")
            or ctx["solve_image"].append((img, prompt))
            or "IMG ANSWER"
        ),
        send_message_fn=lambda text: events.append("send")
        or ctx["messages"].append(text),
        telegram_delivery=_ImmediateDelivery(
            lambda text: events.append("send") or ctx["messages"].append(text)
        ),
        take_screenshot_fn=lambda: events.append("capture") or b"PNG_BYTES",
        answer_overlay=_FakeOverlay(events),
    )

    service.handle_prompt("PROMPT_X")

    assert ctx["solve_image"] == [(b"PNG_BYTES", "PROMPT_X")]
    assert ctx["messages"] == ["IMG ANSWER"]
    assert events == [
        "overlay:hide",
        "capture",
        "solve",
        ("overlay:show", "IMG ANSWER"),
        "send",
    ]


def test_screenshot_is_not_taken_when_overlay_cannot_hide():
    class _BrokenOverlay(_FakeOverlay):
        def hide(self):
            raise RuntimeError("not hidden")

    captured = []
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        send_message_fn=lambda _text: None,
        take_screenshot_fn=lambda: captured.append(True) or b"PNG_BYTES",
        answer_overlay=_BrokenOverlay(),
    )

    service.handle_prompt("PROMPT_X")

    assert captured == []


def test_prompt_is_rejected_while_recording():
    messages = []
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        send_message_fn=messages.append,
        status_callback=lambda status, message, notify: messages.append(message),
    )
    service.is_recording = True

    service.handle_prompt("PROMPT_X")

    assert messages == ["Сначала остановите запись"]


def test_hotkey_repeat_is_ignored():
    submitted = []

    class _Queue:
        def submit(self, target, args=()):
            submitted.append((target, args))
            return True

        def close(self):
            pass

    service = HotkeyService(
        recorder=_FakeRecorder(None),
        action_queue=_Queue(),
        clock=lambda: 10.0,
    )

    assert service.submit_toggle_recording() is True
    assert service.submit_toggle_recording() is False
    assert len(submitted) == 1


def test_middle_click_submits_universal_prompt():
    submitted = []
    stopped = []

    class _Queue:
        def submit(self, target, args=()):
            submitted.append((target, args))
            return True

        def close(self):
            pass

    class _MouseHook:
        def __init__(self, handler):
            self.handler = handler

        def start(self):
            self.handler()

        def stop(self):
            stopped.append(True)

    class _Keyboard:
        def add_hotkey(self, combo, handler):
            pass

        def unhook_all_hotkeys(self):
            pass

    service = HotkeyService(
        recorder=_FakeRecorder(None),
        prompts=["Команда"],
        action_hotkeys=["ctrl+1"],
        mouse_prompt="Универсальный",
        action_queue=_Queue(),
        middle_click_factory=_MouseHook,
    )
    service.register_hotkeys(keyboard_module_override=_Keyboard())

    assert submitted[0][1] == ("Универсальный",)
    service.close()
    assert stopped == [True]
