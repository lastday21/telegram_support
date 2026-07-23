from app.domain.status import AppStatus
from app.interfaces.hotkeys import listener
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
    def __init__(self, send, send_photos=None):
        self.send = send
        self.send_photos = send_photos

    def submit(self, text):
        self.send(text)
        return True

    def submit_photos(self, photos, caption=None):
        if self.send_photos is not None:
            self.send_photos(tuple(photos), caption)
        return True

    def close(self):
        pass


def test_default_screenshot_is_saved_for_later_review(monkeypatch):
    saved = []
    monkeypatch.setattr(
        "app.domain.ocr.capture.take_screenshot",
        lambda: b"SCREEN",
    )
    monkeypatch.setattr(listener, "save_screenshot", saved.append)

    image = listener._default_take_screenshot()

    assert image == b"SCREEN"
    assert saved == [b"SCREEN"]


def test_archive_failure_does_not_break_screenshot(monkeypatch):
    monkeypatch.setattr(
        "app.domain.ocr.capture.take_screenshot",
        lambda: b"SCREEN",
    )

    def fail_to_save(_image):
        raise RuntimeError("archive failed")

    monkeypatch.setattr(listener, "save_screenshot", fail_to_save)

    assert listener._default_take_screenshot() == b"SCREEN"


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
    sent_photos = []
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
            lambda text: events.append("send") or ctx["messages"].append(text),
            lambda photos, caption: (
                events.append("send_photos") or sent_photos.append((photos, caption))
            ),
        ),
        take_screenshot_fn=lambda: events.append("capture") or b"PNG_BYTES",
        answer_overlay=_FakeOverlay(events),
    )

    service.handle_prompt("PROMPT_X")

    assert ctx["solve_image"] == [(b"PNG_BYTES", "PROMPT_X")]
    assert ctx["messages"] == ["IMG ANSWER"]
    assert sent_photos == [((b"PNG_BYTES",), "Снимок задания")]
    assert events == [
        "overlay:hide",
        "capture",
        "send_photos",
        "solve",
        ("overlay:show", "IMG ANSWER"),
        "send",
    ]


def test_long_text_is_collected_and_used_for_follow_up_questions():
    calls = {
        "recognized": [],
        "answers": [],
        "messages": [],
        "photos": [],
    }
    screenshots = iter((b"PAGE_1", b"QUESTION"))
    statuses = []
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        recognize_image_fn=lambda image: (
            calls["recognized"].append(image) or "Героя большого текста звали Алексей."
        ),
        solve_image_fn=lambda image, prompt, context: (
            calls["answers"].append((image, prompt, context)) or "Алексей"
        ),
        send_message_fn=calls["messages"].append,
        telegram_delivery=_ImmediateDelivery(
            calls["messages"].append,
            lambda photos, caption: calls["photos"].append((photos, caption)),
        ),
        take_screenshot_fn=lambda: next(screenshots),
        status_callback=lambda status, message, notify: statuses.append(
            (status, message, notify)
        ),
    )

    service.capture_reading_context()
    service.handle_prompt("Как звали героя?")

    assert calls["recognized"] == [b"PAGE_1"]
    assert calls["answers"] == [
        (
            b"QUESTION",
            "Как звали героя?",
            "Героя большого текста звали Алексей.",
        )
    ]
    assert calls["messages"] == ["Алексей"]
    assert calls["photos"] == [
        (
            (b"PAGE_1", b"QUESTION"),
            "Большой текст и текущее задание",
        )
    ]
    saved_status = next(
        status for status in statuses if status[1].startswith("Часть текста сохранена")
    )
    assert saved_status[2] is False


def test_context_image_is_sent_when_text_is_not_recognized():
    photos = []
    screenshots = iter((b"DIAGRAM", b"QUESTION"))
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        recognize_image_fn=lambda _image: "",
        solve_image_fn=lambda _image, _prompt: "Ответ",
        telegram_delivery=_ImmediateDelivery(
            lambda _text: None,
            lambda images, caption: photos.append((images, caption)),
        ),
        take_screenshot_fn=lambda: next(screenshots),
    )

    service.capture_reading_context()
    service.handle_prompt("Вопрос по рисунку")

    assert photos == [
        (
            (b"DIAGRAM", b"QUESTION"),
            "Большой текст и текущее задание",
        )
    ]


def test_long_text_context_can_be_cleared():
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        recognize_image_fn=lambda _image: "Сохранённый большой текст",
        send_message_fn=lambda _text: None,
        take_screenshot_fn=lambda: b"PAGE",
    )

    service.capture_reading_context()
    assert service.reading_context.text == "Сохранённый большой текст"

    service.clear_reading_context()

    assert service.reading_context.text == ""
    assert service._pending_context_images == []


def test_context_screens_are_sent_only_with_first_follow_up_question():
    photos = []
    screenshots = iter((b"PAGE_1", b"PAGE_2", b"QUESTION_1", b"QUESTION_2"))
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        recognize_image_fn=lambda image: image.decode(),
        solve_image_fn=lambda _image, _prompt, _context: "Ответ",
        telegram_delivery=_ImmediateDelivery(
            lambda _text: None,
            lambda images, caption: photos.append((images, caption)),
        ),
        take_screenshot_fn=lambda: next(screenshots),
    )

    service.capture_reading_context()
    service.capture_reading_context()
    service.handle_prompt("Первый вопрос")
    service.handle_prompt("Второй вопрос")

    assert photos == [
        (
            (b"PAGE_1", b"PAGE_2", b"QUESTION_1"),
            "Большой текст и текущее задание",
        ),
        ((b"QUESTION_2",), "Снимок задания"),
    ]


def test_seven_context_screens_and_question_form_one_album():
    photos = []
    screenshots = iter(
        [
            *(f"PAGE_{index}".encode() for index in range(1, 8)),
            b"QUESTION",
        ]
    )
    service = HotkeyService(
        recorder=_FakeRecorder(None),
        recognize_image_fn=lambda image: image.decode(),
        solve_image_fn=lambda _image, _prompt, _context: "Ответ",
        telegram_delivery=_ImmediateDelivery(
            lambda _text: None,
            lambda images, caption: photos.append((images, caption)),
        ),
        take_screenshot_fn=lambda: next(screenshots),
    )

    for _ in range(7):
        service.capture_reading_context()
    service.handle_prompt("Вопрос")

    assert photos == [
        (
            (
                b"PAGE_1",
                b"PAGE_2",
                b"PAGE_3",
                b"PAGE_4",
                b"PAGE_5",
                b"PAGE_6",
                b"PAGE_7",
                b"QUESTION",
            ),
            "Большой текст и текущее задание",
        )
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
    screenshots = iter((b"QUESTION_SCREEN", b"CONTEXT_SCREEN"))

    class _Queue:
        def submit(self, target, args=()):
            submitted.append((target, args))
            return True

        def close(self):
            pass

    class _MouseHook:
        def __init__(self, handler, context_handler, clear_context_handler):
            self.handler = handler
            self.context_handler = context_handler
            self.clear_context_handler = clear_context_handler

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
        take_screenshot_fn=lambda: next(screenshots),
    )
    service.register_hotkeys(keyboard_module_override=_Keyboard())

    assert submitted[0][0] == service._handle_captured_prompt
    assert submitted[0][1] == (b"QUESTION_SCREEN", "Универсальный")
    service._middle_click_hook.context_handler()
    service._middle_click_hook.clear_context_handler()
    assert submitted[1][0] == service._store_reading_context
    assert submitted[1][1] == (b"CONTEXT_SCREEN",)
    assert submitted[2][0] == service.clear_reading_context
    service.close()
    assert stopped == [True]


def test_seven_context_screens_are_captured_before_queue_processing():
    submitted = []
    screenshots = iter(
        [
            *(f"PAGE_{index}".encode() for index in range(1, 8)),
            b"QUESTION",
        ]
    )
    clock_values = iter(float(index) for index in range(1, 9))

    class _Queue:
        def submit(self, target, args=()):
            submitted.append((target, args))
            return True

        def close(self):
            pass

    service = HotkeyService(
        recorder=_FakeRecorder(None),
        action_queue=_Queue(),
        clock=lambda: next(clock_values),
        take_screenshot_fn=lambda: next(screenshots),
    )

    assert all(service.submit_reading_context() for _ in range(7))
    assert service.submit_mouse_prompt() is True

    assert [args[0] for _target, args in submitted] == [
        *(f"PAGE_{index}".encode() for index in range(1, 8)),
        b"QUESTION",
    ]
    assert submitted[-1][0] == service._handle_captured_prompt
    assert submitted[-1][1] == (b"QUESTION", service.mouse_prompt)
