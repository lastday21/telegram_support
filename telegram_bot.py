"""
Основная задача модуля — принимать от пользователя команды и сообщения,
а затем незаметно запускать «тяжёлые» операции (GPT-ответ, STT-расшифровку,
OCR-анализ скриншота и т. д.) в фоновом потоке, не блокируя
асинхронный event-loop библиотеки **python-telegram-bot**.
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

from config import TG_BOT_TOKEN
from ai_solver import solve_text
from hotkey_listener import PROMPTS  # список Alt+1…9


request = HTTPXRequest(connect_timeout=20, read_timeout=20)

app = (
    ApplicationBuilder()
    .token(TG_BOT_TOKEN)
    .request(request)
    .concurrent_updates(True)  # обрабатывать апдейты параллельно
    .build()
)


HELP = (
    "/help – эта справка\n"
    "/prompts – список подсказок (Alt+1…9)\n"
    "/p <n> – ответ по подсказке №n\n"
    "Любой другой текст → ответ GPT."
)
THINKING = "⌛ Думаю…"
BULB = "💡 "


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/help — краткая справка."""
    await update.message.reply_text(HELP)


async def cmd_prompts(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/prompts — заголовки всех пресетов Alt+1…9."""
    txt = "\n".join(
        f"{i}. {p.splitlines()[0][:60]}…" for i, p in enumerate(PROMPTS, 1)
    )
    await update.message.reply_text(txt)


async def cmd_p(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/p <n> — ответ GPT по готовой подсказке №n (1–9)."""
    try:
        n = int(ctx.args[0])
        assert 1 <= n <= len(PROMPTS)
    except (IndexError, ValueError, AssertionError):
        await update.message.reply_text("Использование: /p <1-9>")
        return

    await update.message.reply_text(THINKING)

    # solve_text выполняем в пуле потоков → не блокируем event‑loop
    answer = await ctx.application.run_async(solve_text, PROMPTS[n - 1])
    await update.message.reply_text(f"{BULB}{answer}")



async def on_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет произвольный текст пользователя в GPT."""
    await update.message.reply_text(THINKING)

    answer = await ctx.application.run_async(solve_text, update.message.text)
    await update.message.reply_text(f"{BULB}{answer}")



app.add_handler(CommandHandler(["start", "help"], cmd_help))
app.add_handler(CommandHandler("prompts", cmd_prompts))
app.add_handler(CommandHandler("p", cmd_p))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))



def main() -> None:
    """Starts polling; responds to Ctrl+C (SIGINT) as usual."""
    app.run_polling()


if __name__ == "__main__":
    main()
