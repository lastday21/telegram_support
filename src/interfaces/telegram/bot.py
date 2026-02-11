"""
Основная задача модуля — принимать от пользователя команды и сообщения,
а затем незаметно запускать операции (GPT-ответ, OCR и т. д.) в фоновом
потоке, не блокируя event-loop python-telegram-bot.
"""

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest
import asyncio

from src.settings import TG_BOT_TOKEN, require_settings
from src.infra.yandex_gpt import solve_text
from src.interfaces.hotkeys.listener import PROMPTS

HELP = (
    "/help – эта справка\n"
    "/prompts – список подсказок (Alt+1…9)\n"
    "/p <n> – ответ по подсказке №n\n"
    "Любой другой текст → ответ GPT."
)
THINKING = "⌛ Думаю…"
BULB = "💡 "


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None:
        return
    await msg.reply_text(HELP)


async def cmd_prompts(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None:
        return
    txt = "\n".join(f"{i}. {p.splitlines()[0][:60]}…" for i, p in enumerate(PROMPTS, 1))
    await msg.reply_text(txt)


async def cmd_p(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None:
        return

    args = ctx.args or []
    if not args or not args[0].isdigit():
        await msg.reply_text("Использование: /p <1-9>")
        return

    n = int(args[0])
    if not 1 <= n <= len(PROMPTS):
        await msg.reply_text("Использование: /p <1-9>")
        return

    await msg.reply_text(THINKING)
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, solve_text, PROMPTS[n - 1])
    await msg.reply_text(f"{BULB}{answer}")


async def on_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg is None or msg.text is None:
        return

    await msg.reply_text(THINKING)
    text = msg.text
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, solve_text, text)
    await msg.reply_text(f"{BULB}{answer}")



def main() -> None:
    require_settings("TG_BOT_TOKEN")
    request = HTTPXRequest(connect_timeout=20, read_timeout=20)
    app = ApplicationBuilder().token(TG_BOT_TOKEN).request(request).build()

    app.add_handler(CommandHandler(["start", "help"], cmd_help))
    app.add_handler(CommandHandler("prompts", cmd_prompts))
    app.add_handler(CommandHandler("p", cmd_p))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))

    app.run_polling()


if __name__ == "__main__":
    main()
