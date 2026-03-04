import threading
import traceback

import keyboard

from src.interfaces.hotkeys.listener import main as hk_main
from src.interfaces.telegram.bot import main as tg_main


def run_hotkeys(hotkeys_main=hk_main) -> None:
    try:
        hotkeys_main()
    except Exception:
        traceback.print_exc()


def main(bot_main=tg_main, hotkeys_main=hk_main, keyboard_module=keyboard) -> None:
    threading.Thread(target=run_hotkeys, args=(hotkeys_main,), daemon=True).start()

    try:
        bot_main()
    except Exception:
        traceback.print_exc()
        print("Бот не запустился. Проверьте настройки, затем нажмите любую клавишу.")
        keyboard_module.wait()


if __name__ == "__main__":
    main()
