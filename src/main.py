import threading
import keyboard
import traceback

from src.settings import require_settings
from src.interfaces.telegram.bot import main as tg_main
from src.interfaces.hotkeys.listener import main as hk_main


def run_hotkeys() -> None:
    try:
        hk_main()
    except Exception:
        traceback.print_exc()


def main() -> None:
    require_settings("YC_API_KEY", "YC_FOLDER_ID", "TG_BOT_TOKEN", "TG_CHAT_ID")

    threading.Thread(target=run_hotkeys, daemon=True).start()

    try:
        tg_main()
    except Exception:
        traceback.print_exc()
        print("Бот не запустился. Хоткеи работают, закрой окно для выхода.")
        keyboard.wait()


if __name__ == "__main__":
    main()
