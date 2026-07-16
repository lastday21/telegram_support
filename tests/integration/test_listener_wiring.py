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
        send_message=lambda _text: None,
        ping=lambda: True,
    )
    monkeypatch.setattr(
        listener,
        "get_client_settings",
        lambda: types.SimpleNamespace(mic_device=None, mix_device=None),
    )
    monkeypatch.setattr(listener, "build_remote_client", lambda: remote_client)
    monkeypatch.setattr(listener, "pick_default_devices", lambda: ("MIC", "MIX"))
    monkeypatch.setattr(listener, "VoiceRecorder", _FakeRecorder)

    service = listener.build_hotkey_service()

    assert service.recorder.mic_device == "MIC"
    assert service.recorder.mix_device == "MIX"
    assert service.prompts == listener.PROMPTS
    assert service.solve_text("question") == "answer"
    assert service.ping() is True


def test_register_hotkeys_binds_all_prompts():
    registered = []
    launched = []

    class _Keyboard:
        def add_hotkey(self, combo, handler):
            registered.append((combo, handler))

    service = listener.HotkeyService(
        recorder=_FakeRecorder("MIC", "MIX"), prompts=["A", "B"]
    )
    service.register_hotkeys(
        keyboard_module_override=_Keyboard(),
        thread_factory=lambda target, args: launched.append((target, args)),
    )

    assert [combo for combo, _ in registered] == ["alt+q", "alt+1", "alt+2"]
    registered[1][1]()
    assert launched[0][1] == ("A",)


def test_main_runs_built_hotkey_service(monkeypatch):
    calls = {}

    class _FakeService:
        def run(self):
            calls["run_called"] = True

    monkeypatch.setattr(listener, "build_hotkey_service", lambda: _FakeService())

    listener.main()

    assert calls["run_called"] is True
