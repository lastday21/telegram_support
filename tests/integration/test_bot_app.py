import types

from app.interfaces.telegram import bot
from app.settings import Settings


def test_create_app_registers_expected_handlers():
    app = bot.create_app(
        bot_token="TOKEN", solve_text_fn=lambda text: text, prompts=["A", "B"]
    )

    handlers = app.handlers[0]

    assert len(handlers) == 4
    assert handlers[0].commands == frozenset({"start", "help"})
    assert handlers[1].commands == frozenset({"prompts"})
    assert handlers[2].commands == frozenset({"p"})


def test_create_app_uses_token_from_settings(monkeypatch):
    monkeypatch.setattr(
        bot,
        "get_settings",
        lambda: Settings(
            yc_api_key="KEY",
            yc_folder_id="FOLDER",
            tg_bot_token="TOKEN_FROM_SETTINGS",
            tg_chat_id="CHAT",
            mic_device=None,
            mix_device=None,
        ),
    )

    app = bot.create_app(solve_text_fn=lambda text: text, prompts=["A"])

    assert app.bot.token == "TOKEN_FROM_SETTINGS"


def test_main_runs_polling_on_created_app(monkeypatch):
    calls = {}
    fake_app = types.SimpleNamespace(
        run_polling=lambda: calls.__setitem__("run_polling_called", True)
    )
    monkeypatch.setattr(bot, "create_app", lambda: fake_app)

    bot.main()

    assert calls["run_polling_called"] is True
