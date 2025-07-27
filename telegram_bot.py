from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.request import HTTPXRequest
from config import TG_BOT_TOKEN
from ai_solver import solve_text
from hotkey_listener import PROMPTS    # список Alt+1…9


request = HTTPXRequest(connect_timeout=20, read_timeout=20)

app = (
    ApplicationBuilder()
    .token(TG_BOT_TOKEN)
    .request(request)
    .concurrent_updates(True)   # обрабатывать апдейты параллельно
    .build()
)

HELP = (
    "/help – эта справка\n"
    "/prompts – список подсказок (Alt+1…9)\n"
    "/p <n> – ответ по подсказке №n\n"
    "Любой другой текст → ответ GPT."
)

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

async def cmd_prompts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = "\n".join(f"{i}. {p.splitlines()[0][:60]}…" for i, p in enumerate(PROMPTS, 1))
    await update.message.reply_text(txt)

async def cmd_p(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(ctx.args[0]); assert 1 <= n <= len(PROMPTS)
    except (IndexError, ValueError, AssertionError):
        await update.message.reply_text("Использование: /p <1-9>")
        return
    await update.message.reply_text("⌛ Думаю…")
    await update.message.reply_text(f"💡 {solve_text(PROMPTS[n-1])}")

async def on_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⌛ Думаю…")
    await update.message.reply_text(f"💡 {solve_text(update.message.text)}")

app.add_handler(CommandHandler(["start", "help"],   cmd_help))
app.add_handler(CommandHandler("prompts",           cmd_prompts))
app.add_handler(CommandHandler("p",                 cmd_p))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))

def main() -> None:
    app.run_polling(stop_signals=[])   # блокирует поток
