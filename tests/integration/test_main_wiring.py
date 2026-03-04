import importlib
import sys
import types


class _FakeThread:
    def __init__(self, calls, target, args, daemon):
        calls["thread_target"] = target
        calls["thread_args"] = args
        calls["thread_daemon"] = daemon
        self.calls = calls

    def start(self):
        self.calls["thread_started"] = True


def _load_main_module():
    sys.modules["keyboard"] = types.SimpleNamespace(wait=lambda: None)
    sys.modules.pop("src.main", None)
    return importlib.import_module("src.main")


def test_main_starts_hotkeys_thread_and_runs_bot(monkeypatch):
    app_main = _load_main_module()
    calls = {}

    monkeypatch.setattr(
        app_main.threading,
        "Thread",
        lambda target, args, daemon: _FakeThread(calls, target, args, daemon),
    )

    def _bot_main():
        calls["bot_main_called"] = True

    def _hotkeys_main():
        calls["hotkeys_main_passed"] = True

    app_main.main(
        bot_main=_bot_main,
        hotkeys_main=_hotkeys_main,
        keyboard_module=types.SimpleNamespace(wait=lambda: calls.__setitem__("wait_called", True)),
    )

    assert calls["thread_target"] is app_main.run_hotkeys
    assert calls["thread_args"] == (_hotkeys_main,)
    assert calls["thread_daemon"] is True
    assert calls["thread_started"] is True
    assert calls["bot_main_called"] is True
    assert "wait_called" not in calls


def test_main_waits_for_keyboard_when_bot_crashes(monkeypatch):
    app_main = _load_main_module()
    calls = {}

    monkeypatch.setattr(
        app_main.threading,
        "Thread",
        lambda target, args, daemon: _FakeThread(calls, target, args, daemon),
    )

    def _boom():
        raise RuntimeError("bot failed")

    app_main.main(
        bot_main=_boom,
        hotkeys_main=lambda: None,
        keyboard_module=types.SimpleNamespace(wait=lambda: calls.__setitem__("wait_called", True)),
    )

    assert calls["thread_started"] is True
    assert calls["wait_called"] is True
