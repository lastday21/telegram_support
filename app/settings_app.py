import logging
import sys

from app.interfaces.settings_window import SettingsWindow
from app.logging_config import configure_desktop_logging
from app.settings import load_client_settings

logger = logging.getLogger(__name__)


def main() -> None:
    configure_desktop_logging()
    logger.info("Открыто окно настроек")
    try:
        SettingsWindow().run()
    except Exception:
        logger.exception("Окно настроек аварийно завершено")
        raise


def self_check() -> None:
    load_client_settings(require_connection=False)


if __name__ == "__main__":
    if "--check" in sys.argv:
        self_check()
    else:
        main()
