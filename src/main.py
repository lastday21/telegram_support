import threading
import traceback

import keyboard

from src.interfaces.hotkeys.listener import main as hotkeys_main
from src.interfaces.telegram.bot import main as telegram_main


def _run_hotkeys() -> None:
    try:
        hotkeys_main()
    except Exception:
        traceback.print_exc()


def main() -> None:
    threading.Thread(target=_run_hotkeys, daemon=True).start()

    try:
        telegram_main()
    except Exception:
        traceback.print_exc()
        print("Бот не запустился. Хоткеи работают, закрой окно для выхода.")
        keyboard.wait()


if __name__ == "__main__":
    main()
