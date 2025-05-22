# telegram_bot.py
import json
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)

from ai_solver import solve_text  # ваша функция для работы с чистым текстом

# --- Загружаем настройки ---
_cfg = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
BOT_TOKEN = _cfg["botToken"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Пришли мне условие задачи, а я верну ответ AI."
    )

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_id = update.effective_chat.id

    # показываем пользователю, что бот обрабатывает
    await context.bot.send_chat_action(chat_id, action="typing")

    try:
        answer = solve_text(user_text)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при обращении к AI: {e}")
        return

    await update.message.reply_text(answer)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), on_message)
    )

    print("Telegram bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
