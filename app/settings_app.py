import logging

from app.interfaces.settings_window import SettingsWindow
from app.logging_config import configure_desktop_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_desktop_logging()
    logger.info("Открыто окно настроек")
    try:
        SettingsWindow().run()
    except Exception:
        logger.exception("Окно настроек аварийно завершено")
        raise


if __name__ == "__main__":
    main()
