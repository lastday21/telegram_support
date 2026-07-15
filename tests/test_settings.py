from pathlib import Path

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
