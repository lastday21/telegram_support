import asyncio

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
from src.interfaces.hotkeys.listener import SCREENSHOT_PROMPTS
from src.settings import TG_BOT_TOKEN

HELP_TEXT = (
    "/help – эта справка\n"
    "/prompts – список подсказок (Alt+1…9)\n"
    "/p <n> – ответ по подсказке №n\n"
    "Любой другой текст → ответ GPT."
)
THINKING_TEXT = "⌛ Думаю…"
ANSWER_PREFIX = "💡 "


def _build_application():
    request = HTTPXRequest(connect_timeout=20, read_timeout=20)
    application = ApplicationBuilder().token(TG_BOT_TOKEN).request(request).build()

    application.add_handler(CommandHandler(["start", "help"], handle_help_command))
    application.add_handler(CommandHandler("prompts", handle_prompts_command))
    application.add_handler(CommandHandler("p", handle_prompt_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    return application


async def _reply_if_message_exists(update: Update, text: str) -> bool:
    message = update.message
    if message is None:
        return False
    await message.reply_text(text)
    return True


async def _solve_text_without_blocking(prompt_text: str) -> str:
    event_loop = asyncio.get_running_loop()
    return await event_loop.run_in_executor(None, solve_text, prompt_text)


async def handle_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = context
    await _reply_if_message_exists(update, HELP_TEXT)


async def handle_prompts_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    _ = context
    prompt_lines = [
        f"{index}. {prompt_text.splitlines()[0][:60]}…"
        for index, prompt_text in enumerate(SCREENSHOT_PROMPTS, start=1)
    ]
    await _reply_if_message_exists(update, "\n".join(prompt_lines))


async def handle_prompt_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    if message is None:
        return

    if not context.args or not context.args[0].isdigit():
        await message.reply_text("Использование: /p <1-9>")
        return

    prompt_number = int(context.args[0])
    prompt_index = prompt_number - 1
    if not (0 <= prompt_index < len(SCREENSHOT_PROMPTS)):
        await message.reply_text("Использование: /p <1-9>")
        return

    await message.reply_text(THINKING_TEXT)
    answer_text = await _solve_text_without_blocking(SCREENSHOT_PROMPTS[prompt_index])
    await message.reply_text(f"{ANSWER_PREFIX}{answer_text}")


async def handle_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    _ = context
    message = update.message
    if message is None or message.text is None:
        return

    await message.reply_text(THINKING_TEXT)
    answer_text = await _solve_text_without_blocking(message.text)
    await message.reply_text(f"{ANSWER_PREFIX}{answer_text}")


def main() -> None:
    application = _build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
