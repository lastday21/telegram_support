import threading
import traceback

import keyboard

from src.interfaces.hotkeys.listener import main as start_hotkeys_listener
from src.interfaces.telegram.bot import main as start_telegram_bot


def _run_hotkeys_listener() -> None:
    try:
        start_hotkeys_listener()
    except Exception:
        traceback.print_exc()


def main() -> None:
    threading.Thread(target=_run_hotkeys_listener, daemon=True).start()

    try:
        start_telegram_bot()
    except Exception:
        traceback.print_exc()
        print("Бот не запустился. Хоткеи работают, закрой окно для выхода.")
        keyboard.wait()


if __name__ == "__main__":
    main()
