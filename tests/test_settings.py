import json
from pathlib import Path

import pytest

from app import settings


def test_packaged_client_uses_appdata(monkeypatch, tmp_path: Path):
    monkeypatch.delenv(settings.CLIENT_ENV_NAME, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(settings.sys, "frozen", True, raising=False)

    assert settings.client_env_path() == tmp_path / "SmartHelper" / ".env"


def test_explicit_client_settings_path_has_priority(monkeypatch, tmp_path: Path):
    env_path = tmp_path / "client.env"
    monkeypatch.setenv(settings.CLIENT_ENV_NAME, str(env_path))

    assert settings.client_env_path() == env_path.resolve()


def test_preferences_are_saved_for_next_launch(monkeypatch, tmp_path: Path):
    preferences_path = tmp_path / "settings.json"
    monkeypatch.setenv(settings.PREFERENCES_ENV_NAME, str(preferences_path))

    saved = settings.save_client_preferences(
        yc_model="aliceai-llm/latest",
        record_hotkey="CTRL+R",
        mouse_prompt="Ответь на вопрос",
        actions=[(f"CTRL+{index}", f"Подсказка {index}") for index in range(1, 6)],
        show_answer_overlay=False,
    )

    payload = json.loads(preferences_path.read_text(encoding="utf-8"))
    assert payload["model"] == "aliceai-llm/latest"
    assert payload["actions"][4]["hotkey"] == "ctrl+5"
    assert payload["show_answer_overlay"] is False
    assert saved.record_hotkey == "ctrl+r"
    assert saved.mouse_prompt == "Ответь на вопрос"
    assert saved.action_prompts[0] == "Подсказка 1"
    assert saved.show_answer_overlay is False


def test_saved_preferences_are_loaded(monkeypatch, tmp_path: Path):
    preferences_path = tmp_path / "settings.json"
    monkeypatch.setenv(settings.PREFERENCES_ENV_NAME, str(preferences_path))
    settings.save_client_preferences(
        yc_model="deepseek-v32/latest",
        record_hotkey="f8",
        mouse_prompt="Промпт мыши",
        actions=[(f"ctrl+{index}", f"Промпт {index}") for index in range(1, 6)],
        show_answer_overlay=False,
    )

    loaded = settings.load_user_preferences()

    assert loaded.yc_model == "deepseek-v32/latest"
    assert loaded.record_hotkey == "f8"
    assert loaded.action_hotkeys == settings.DEFAULT_ACTION_HOTKEYS
    assert loaded.show_answer_overlay is False


def test_old_preferences_keep_answer_window_enabled(monkeypatch, tmp_path: Path):
    preferences_path = tmp_path / "settings.json"
    preferences_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(settings.PREFERENCES_ENV_NAME, str(preferences_path))

    loaded = settings.load_user_preferences()

    assert loaded.show_answer_overlay is True


def test_duplicate_hotkey_is_rejected():
    with pytest.raises(ValueError, match="не должны повторяться"):
        settings.validate_hotkeys(
            "ctrl+1",
            ["ctrl+1", "ctrl+2", "ctrl+3", "ctrl+4", "ctrl+5"],
        )


def test_connection_settings_can_be_saved_on_first_run(monkeypatch, tmp_path: Path):
    env_path = tmp_path / "client.env"
    monkeypatch.setenv(settings.CLIENT_ENV_NAME, str(env_path))
    monkeypatch.setenv(
        settings.PREFERENCES_ENV_NAME, str(tmp_path / "preferences.json")
    )
    for name in ("SERVER_URL", "APP_ACCESS_TOKEN", "MIC_DEVICE", "MIX_DEVICE"):
        monkeypatch.delenv(name, raising=False)

    initial = settings.load_client_settings(require_connection=False)
    saved = settings.save_client_connection_settings(
        "https://helper.example.ru/",
        "SECRET",
        mic_device="Микрофон",
    )

    assert initial.server_url == settings.DEFAULT_SERVER_URL
    assert initial.app_access_token == ""
    assert saved.server_url == "https://helper.example.ru"
    assert saved.app_access_token == "SECRET"
    assert saved.mic_device == "Микрофон"
    assert "APP_ACCESS_TOKEN=SECRET" in env_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("server_url", ["", "helper.example.ru", "ftp://host"])
def test_invalid_server_url_is_rejected(server_url: str):
    with pytest.raises(ValueError, match="полный адрес"):
        settings.validate_client_connection(server_url, "SECRET")
