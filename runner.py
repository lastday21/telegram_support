# runner.py
import threading, keyboard, traceback

# 1) хоткеи (Alt+Q / Alt+1…9) в фоне
def run_hotkeys():
    try:
        import hotkey_listener
        hotkey_listener.main()          # блокирует поток
    except Exception:
        traceback.print_exc()

threading.Thread(target=run_hotkeys, daemon=True).start()

# 2) Telegram-бот в ГЛАВНОМ потоке
try:
    import telegram_bot
    telegram_bot.main()                # блокирует процесс
except Exception:
    traceback.print_exc()
    print("Бот не запустился. Хоткеи работают, закрой окно для выхода.")
    keyboard.wait()
