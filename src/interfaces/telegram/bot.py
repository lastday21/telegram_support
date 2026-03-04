import asyncio
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

from src.infra.yandex_gpt import solve_text
from src.prompts import PROMPTS
from src.settings import get_settings

HELP = (
    "/help - список команд\n"
    "/prompts - список подсказок (Alt+1-9)\n"
    "/p <n> - ответ по подсказке n\n"
    "Отправь любое сообщение - получишь ответ GPT."
)
THINKING = "Думаю..."
BULB = "Ответ: "


class TelegramBotService:
    def __init__(
        self,
        solve_text_fn=solve_text,
        prompts: Sequence[str] = PROMPTS,
    ) -> None:
        self.solve_text = solve_text_fn
        self.prompts = list(prompts)

    async def cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.message
        if msg is None:
            return
        await msg.reply_text(HELP)

    async def cmd_prompts(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.message
        if msg is None:
            return
        txt = "\n".join(
            f"{index}. {prompt.splitlines()[0][:60]}..."
            for index, prompt in enumerate(self.prompts, 1)
        )
        await msg.reply_text(txt)

    async def cmd_p(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
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
        answer = await loop.run_in_executor(
            None, self.solve_text, self.prompts[prompt_index - 1]
        )
        await msg.reply_text(f"{BULB}{answer}")

    async def on_msg(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.message
        if msg is None or msg.text is None:
            return

        await msg.reply_text(THINKING)
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, self.solve_text, msg.text)
        await msg.reply_text(f"{BULB}{answer}")


def create_app(
    bot_token: str | None = None,
    solve_text_fn=solve_text,
    prompts: Sequence[str] = PROMPTS,
    request: HTTPXRequest | None = None,
):
    if bot_token is None:
        bot_token = get_settings().tg_bot_token
    request = request or HTTPXRequest(connect_timeout=20, read_timeout=20)
    app = ApplicationBuilder().token(bot_token).request(request).build()
    service = TelegramBotService(solve_text_fn=solve_text_fn, prompts=prompts)
    app.add_handler(CommandHandler(["start", "help"], service.cmd_help))
    app.add_handler(CommandHandler("prompts", service.cmd_prompts))
    app.add_handler(CommandHandler("p", service.cmd_p))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, service.on_msg))
    return app


def main() -> None:
    create_app().run_polling()
