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
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

from src.infra.yandex_gpt import solve_text
from src.interfaces.hotkeys.listener import PROMPTS
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
def _build_app():
    request = HTTPXRequest(connect_timeout=20, read_timeout=20)
    app = ApplicationBuilder().token(TG_BOT_TOKEN).request(request).build()

    app.add_handler(CommandHandler(["start", "help"], cmd_help))
    app.add_handler(CommandHandler("prompts", cmd_prompts))
    app.add_handler(CommandHandler("p", cmd_p))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))
    return app


async def _safe_reply(update: Update, text: str) -> bool:
    msg = update.message
    if msg is None:
        return False
    await msg.reply_text(text)
    return True


async def _solve_in_thread(text: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, solve_text, text)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_reply(update, HELP_TEXT)

    application.add_handler(CommandHandler(["start", "help"], handle_help_command))
    application.add_handler(CommandHandler("prompts", handle_prompts_command))
    application.add_handler(CommandHandler("p", handle_prompt_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    return application

async def cmd_prompts(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"{index}. {prompt.splitlines()[0][:60]}…" for index, prompt in enumerate(PROMPTS, start=1)]
    await _safe_reply(update, "\n".join(lines))

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
async def cmd_p(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Использование: /p <1-9>")
        return

    prompt_index = int(ctx.args[0]) - 1
    if not (0 <= prompt_index < len(PROMPTS)):
        await update.message.reply_text("Использование: /p <1-9>")
        return

    await update.message.reply_text(THINKING_TEXT)
    answer = await _solve_in_thread(PROMPTS[prompt_index])
    await update.message.reply_text(f"{ANSWER_PREFIX}{answer}")


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
    await msg.reply_text(THINKING_TEXT)
    answer = await _solve_in_thread(msg.text)
    await msg.reply_text(f"{ANSWER_PREFIX}{answer}")


def main() -> None:
    app = _build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
