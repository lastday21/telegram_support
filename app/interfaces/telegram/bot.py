import asyncio
import logging
import os
from collections.abc import Sequence

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from app.infra.remote_client import RemoteServiceClient
from app.infra.dns_fallback import install_dns_fallback
from app.infra.yandex_gpt import solve_text
from app.prompts import PROMPTS
from app.settings import get_settings

HELP = (
    "/help - список команд\n"
    "/prompts - список подсказок (Alt+1-9)\n"
    "/p <n> - ответ по подсказке n\n"
    "Отправь любое сообщение - получишь ответ GPT."
)
THINKING = "Думаю..."
BULB = "Ответ: "
ANSWER_ERROR = "Не удалось получить ответ от Яндекса. Попробуйте ещё раз позже."
logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(
        self,
        solve_text_fn=solve_text,
        prompts: Sequence[str] = PROMPTS,
        allowed_chat_id: str = "",
    ) -> None:
        self.solve_text = solve_text_fn
        self.prompts = list(prompts)
        self.allowed_chat_id = str(allowed_chat_id)

    def is_allowed(self, update: Update) -> bool:
        chat = update.effective_chat
        return chat is not None and str(chat.id) == self.allowed_chat_id

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_allowed(update):
            return
        msg = update.message
        if msg is None:
            return
        await msg.reply_text(HELP)

    async def cmd_prompts(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_allowed(update):
            return
        msg = update.message
        if msg is None:
            return
        txt = "\n".join(
            f"{index}. {prompt.splitlines()[0][:60]}..."
            for index, prompt in enumerate(self.prompts, 1)
        )
        await msg.reply_text(txt)

    async def cmd_p(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_allowed(update):
            return
        msg = update.message
        if msg is None:
            return

        args = ctx.args or []
        if not args or not args[0].isdigit():
            await msg.reply_text("Использование: /p <1-9>")
            return

        prompt_index = int(args[0])
        if not 1 <= prompt_index <= len(self.prompts):
            await msg.reply_text("Использование: /p <1-9>")
            return

        await msg.reply_text(THINKING)
        loop = asyncio.get_running_loop()
        try:
            answer = await loop.run_in_executor(
                None, self.solve_text, self.prompts[prompt_index - 1]
            )
        except Exception:
            logger.exception("Не удалось получить ответ для команды Telegram")
            await msg.reply_text(ANSWER_ERROR)
            return
        await msg.reply_text(f"{BULB}{answer}")

    async def on_msg(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_allowed(update):
            return
        msg = update.message
        if msg is None or msg.text is None:
            return

        await msg.reply_text(THINKING)
        loop = asyncio.get_running_loop()
        try:
            answer = await loop.run_in_executor(None, self.solve_text, msg.text)
        except Exception:
            logger.exception("Не удалось ответить на сообщение Telegram")
            await msg.reply_text(ANSWER_ERROR)
            return
        await msg.reply_text(f"{BULB}{answer}")


def create_app(
    bot_token: str | None = None,
    solve_text_fn=solve_text,
    prompts: Sequence[str] = PROMPTS,
    request: HTTPXRequest | None = None,
    allowed_chat_id: str | None = None,
):
    settings = None
    if bot_token is None or allowed_chat_id is None:
        settings = get_settings()
    if bot_token is None and settings is not None:
        bot_token = settings.tg_bot_token
    if allowed_chat_id is None and settings is not None:
        allowed_chat_id = settings.tg_chat_id
    if bot_token is None:
        raise RuntimeError("Не задан токен Telegram-бота")
    request = request or HTTPXRequest(connect_timeout=20, read_timeout=20)
    app = ApplicationBuilder().token(bot_token).request(request).build()
    service = TelegramBotService(
        solve_text_fn=solve_text_fn,
        prompts=prompts,
        allowed_chat_id=allowed_chat_id or "",
    )
    app.add_handler(CommandHandler(["start", "help"], service.cmd_help))
    app.add_handler(CommandHandler("prompts", service.cmd_prompts))
    app.add_handler(CommandHandler("p", service.cmd_p))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, service.on_msg))
    return app


def main() -> None:
    install_dns_fallback()
    settings = get_settings()
    server_url = os.getenv("SMARTHELPER_SERVER_URL", "http://server:8000")
    server = RemoteServiceClient(
        server_url=server_url,
        access_token=settings.app_access_token,
        model=settings.yc_model,
    )
    create_app(
        bot_token=settings.tg_bot_token,
        solve_text_fn=server.solve_text,
        allowed_chat_id=settings.tg_chat_id,
    ).run_polling(bootstrap_retries=-1)


if __name__ == "__main__":
    main()
