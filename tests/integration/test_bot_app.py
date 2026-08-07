import asyncio
import types

from app.interfaces.telegram import bot
from app.settings import Settings


def test_create_app_registers_expected_handlers():
    app = bot.create_app(
        bot_token="TOKEN",
        solve_text_fn=lambda text: text,
        prompts=["A", "B"],
        allowed_chat_id="CHAT",
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

    app = bot.create_app(
        solve_text_fn=lambda text: text,
        prompts=["A"],
        allowed_chat_id="CHAT",
    )

    assert app.bot.token == "TOKEN_FROM_SETTINGS"


def test_main_runs_polling_on_created_app(monkeypatch):
    calls = {}
    fake_app = types.SimpleNamespace(
        run_polling=lambda **kwargs: calls.__setitem__("run_polling", kwargs)
    )
    settings = Settings(
        yc_api_key="KEY",
        yc_folder_id="FOLDER",
        tg_bot_token="TOKEN",
        tg_chat_id="CHAT",
        mic_device=None,
        mix_device=None,
        app_access_token="ACCESS",
    )
    fake_client = types.SimpleNamespace(solve_text=lambda text: text)
    monkeypatch.setattr(bot, "get_settings", lambda: settings)
    monkeypatch.setattr(bot, "RemoteServiceClient", lambda **_kwargs: fake_client)

    def create_app(**kwargs):
        calls["create_app"] = kwargs
        return fake_app

    monkeypatch.setattr(bot, "create_app", create_app)

    bot.main()

    assert calls["run_polling"] == {"bootstrap_retries": -1}
    assert calls["create_app"]["solve_text_fn"] == fake_client.solve_text


def test_service_allows_only_configured_chat():
    service = bot.TelegramBotService(
        solve_text_fn=lambda text: text,
        prompts=["A"],
        allowed_chat_id="42",
    )

    allowed = types.SimpleNamespace(effective_chat=types.SimpleNamespace(id=42))
    denied = types.SimpleNamespace(effective_chat=types.SimpleNamespace(id=43))

    assert service.is_allowed(allowed) is True
    assert service.is_allowed(denied) is False


def test_service_reports_yandex_failure_without_internal_details():
    def failed_solve(_text: str) -> str:
        raise RuntimeError("SECRET INTERNAL DETAILS")

    replies: list[str] = []
    message = types.SimpleNamespace(
        text="Подробный вопрос",
        reply_text=lambda text: _append_reply(replies, text),
    )
    update = types.SimpleNamespace(
        effective_chat=types.SimpleNamespace(id=42),
        message=message,
    )
    service = bot.TelegramBotService(
        solve_text_fn=failed_solve,
        allowed_chat_id="42",
    )

    asyncio.run(service.on_msg(update, types.SimpleNamespace()))

    assert replies == [bot.THINKING, bot.ANSWER_ERROR]
    assert "SECRET" not in " ".join(replies)


async def _append_reply(replies: list[str], text: str) -> None:
    replies.append(text)
