import threading
import keyboard
import traceback
from interfaces.telegram import  bot
from interfaces.hotkeys import listener


def run_hotkeys():
    try:

        listener.main()  # блокирует поток
    except Exception:
        traceback.print_exc()


threading.Thread(target=run_hotkeys, daemon=True).start()

try:

    bot.main()  # блокирует процесс
except Exception:
    traceback.print_exc()
    print("Бот не запустился. Хоткеи работают, закрой окно для выхода.")
    keyboard.wait()
