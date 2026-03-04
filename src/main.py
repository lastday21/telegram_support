from __future__ import annotations

import threading
import traceback

from src.interfaces.hotkeys.listener import main as hk_main
from src.interfaces.telegram.bot import main as tg_main
from src.settings import env_flag

try:
    import keyboard as keyboard_module
except ImportError:  # pragma: no cover - depends on local environment
    keyboard_module = None


def run_hotkeys(hotkeys_main=hk_main) -> None:
    try:
        hotkeys_main()
    except Exception:
        traceback.print_exc()


def hotkeys_enabled() -> bool:
    return env_flag("ENABLE_HOTKEYS", default=True)


def main(
    bot_main=tg_main,
    hotkeys_main=hk_main,
    keyboard_module_override=keyboard_module,
    enable_hotkeys: bool | None = None,
) -> None:
    if enable_hotkeys is None:
        enable_hotkeys = hotkeys_enabled()

    if enable_hotkeys:
        threading.Thread(target=run_hotkeys, args=(hotkeys_main,), daemon=True).start()

    try:
        bot_main()
    except Exception:
        traceback.print_exc()
        if enable_hotkeys and keyboard_module_override is not None:
            print(
                "Бот не запустился. Проверьте настройки, затем нажмите любую клавишу."
            )
            keyboard_module_override.wait()
            return
        raise


if __name__ == "__main__":
    main()
