import logging
from pathlib import Path

from app.logging_config import configure_desktop_logging, desktop_log_path


def test_desktop_log_is_written_to_local_app_data(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    existing_handlers = set(root_logger.handlers)

    log_path = configure_desktop_logging()
    logging.getLogger("smarthelper.test").info("Проверка журнала")
    added_handlers = [
        handler for handler in root_logger.handlers if handler not in existing_handlers
    ]
    for handler in added_handlers:
        handler.flush()

    try:
        assert log_path == tmp_path / "SmartHelper" / "logs" / "smarthelper.log"
        assert log_path.is_file()
        assert "Проверка журнала" in log_path.read_text(encoding="utf-8")
        assert desktop_log_path() == log_path
    finally:
        for handler in added_handlers:
            root_logger.removeHandler(handler)
            handler.close()
        root_logger.setLevel(previous_level)
