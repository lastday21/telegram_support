import threading
import keyboard
import traceback

from src.interfaces.telegram.bot import main as tg_main
from src.interfaces.hotkeys.listener import main as hk_main


def run_hotkeys():
    try:
        hk_main()
    except Exception:
        traceback.print_exc()


threading.Thread(target=run_hotkeys, daemon=True).start()

try:

    tg_main()
except Exception:
    traceback.print_exc()
    print("Бот не запустился. Хоткеи работают, закрой окно для выхода.")
    keyboard.wait()
