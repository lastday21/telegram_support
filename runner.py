# runner.py
import threading
import asyncio

def run_hotkey():
    import hotkey_listener
    hotkey_listener.main()

def run_bot():
    import telegram_bot
    # создаём свой цикл в этом потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # предполагаем, что telegram_bot.main() — обычная функция,
    # а вот внутри она запускает app.run_polling(), которая является корутиной.
    # Поэтому мы обернём её в asyncio.run (или loop.run_until_complete).
    try:
        loop.run_until_complete(telegram_bot.main())
    finally:
        loop.close()

if __name__ == "__main__":
    t1 = threading.Thread(target=run_hotkey, daemon=True)
    t2 = threading.Thread(target=run_bot,    daemon=True)

    t1.start()
    t2.start()
    t1.join()
    t2.join()
