import types

from app.interfaces.hotkeys import listener


class _FakeRecorder:
    def __init__(self, mic_device, mix_device):
        self.mic_device = mic_device
        self.mix_device = mix_device


def test_build_hotkey_service_uses_detected_devices(monkeypatch):
    remote_client = types.SimpleNamespace(
        transcribe=lambda _path: "text",
        solve_text=lambda _text: "answer",
        solve_image=lambda _image, _prompt: "answer",
        solve_vision_image=lambda _image, _prompt: "vision answer",
        recognize_image=lambda _image: "recognized",
        send_message=lambda _text: None,
        send_photo=lambda _photo, _caption=None: None,
        send_media_group=lambda _photos, _caption=None: None,
        ping=lambda: True,
    )
    settings = types.SimpleNamespace(
        mic_device=None,
        mix_device=None,
        server_url="http://server",
        app_access_token="TOKEN",
        tg_chat_id="123456",
        yc_model="qwen3-235b-a22b-fp8/latest",
        record_hotkey="alt+q",
        vision_hotkey="f1",
        vision_prompt="Реши изображение",
        mouse_prompt="Мышь",
        action_hotkeys=("ctrl+1", "ctrl+2", "ctrl+3", "ctrl+4", "ctrl+5"),
        action_prompts=("A", "B", "C", "D", "E"),
        show_answer_overlay=False,
    )
    monkeypatch.setattr(
        listener,
        "get_client_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        listener, "build_remote_client", lambda _settings: remote_client
    )
    monkeypatch.setattr(listener, "pick_default_devices", lambda: ("MIC", "MIX"))
    monkeypatch.setattr(listener, "VoiceRecorder", _FakeRecorder)

    service = listener.build_hotkey_service()

    assert service.recorder.mic_device == "MIC"
    assert service.recorder.mix_device == "MIX"
    assert service.prompts == ["A", "B", "C", "D", "E"]
    assert service.solve_text("question") == "answer"
    assert service.solve_vision_image(b"image", "prompt") == "vision answer"
    assert service.vision_hotkey == "f1"
    assert service.vision_prompt == "Реши изображение"
    assert service.ping() is True
    assert service.answer_overlay.__class__.__name__ == "_NullAnswerOverlay"


def test_register_hotkeys_binds_all_prompts():
    registered = []
    launched = []

    class _Keyboard:
        def add_hotkey(self, combo, handler):
            registered.append((combo, handler))

    class _MouseHook:
        def __init__(self, handler, context_handler, clear_context_handler):
            self.handler = handler
            self.context_handler = context_handler
            self.clear_context_handler = clear_context_handler

        def start(self):
            pass

        def stop(self):
            pass

    service = listener.HotkeyService(
        recorder=_FakeRecorder("MIC", "MIX"),
        prompts=["A", "B"],
        action_hotkeys=["ctrl+1", "ctrl+2"],
        middle_click_factory=_MouseHook,
    )
    service.register_hotkeys(
        keyboard_module_override=_Keyboard(),
        thread_factory=lambda target, args: launched.append((target, args)),
    )

    assert [combo for combo, _ in registered] == [
        "alt+q",
        "f1",
        "ctrl+1",
        "ctrl+2",
    ]
    registered[2][1]()
    assert launched[0][1] == ("A",)


def test_main_runs_built_hotkey_service(monkeypatch):
    calls = {}

    class _FakeService:
        def run(self):
            calls["run_called"] = True

    monkeypatch.setattr(listener, "build_hotkey_service", lambda: _FakeService())

    listener.main()

    assert calls["run_called"] is True
