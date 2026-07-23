from __future__ import annotations

from dataclasses import replace

import requests

from app.infra.readiness import ExternalReadinessChecker
from app.settings import Settings


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self) -> dict:
        return self.payload


def _settings() -> Settings:
    return Settings(
        yc_api_key="KEY",
        yc_folder_id="FOLDER",
        tg_bot_token="TOKEN",
        tg_chat_id="42",
        mic_device=None,
        mix_device=None,
        app_access_token="ACCESS",
    )


def test_readiness_checks_settings_yandex_and_telegram():
    calls = []

    def http_get(url: str, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/v1/models"):
            return FakeResponse({"data": []})
        return FakeResponse({"ok": True})

    checker = ExternalReadinessChecker(
        settings_provider=_settings,
        http_get=http_get,
        cache_seconds=30,
    )

    first = checker.check()
    second = checker.check()

    assert first.ready is True
    assert first.checks == {"settings": "ok", "yandex": "ok", "telegram": "ok"}
    assert second is first
    assert len(calls) == 2
    assert calls[0][1]["headers"] == {
        "Authorization": "Api-Key KEY",
        "OpenAI-Project": "FOLDER",
    }


def test_readiness_reports_invalid_settings_without_external_requests():
    def invalid_settings() -> Settings:
        raise RuntimeError("SECRET")

    checker = ExternalReadinessChecker(
        settings_provider=invalid_settings,
        http_get=lambda *_args, **_kwargs: None,
    )

    report = checker.check()

    assert report.ready is False
    assert report.checks == {
        "settings": "unavailable",
        "yandex": "not_checked",
        "telegram": "not_checked",
    }


def test_readiness_rejects_invalid_model_without_external_requests():
    settings = _settings()
    invalid = replace(settings, yc_model="unknown/latest")
    called = False

    def http_get(*_args, **_kwargs):
        nonlocal called
        called = True

    report = ExternalReadinessChecker(
        settings_provider=lambda: invalid,
        http_get=http_get,
    ).check()

    assert report.ready is False
    assert report.checks["settings"] == "unavailable"
    assert called is False


def test_readiness_reports_yandex_failure():
    def http_get(url: str, **_kwargs):
        if url.endswith("/v1/models"):
            return FakeResponse({}, status_code=503)
        return FakeResponse({"ok": True})

    report = ExternalReadinessChecker(
        settings_provider=_settings,
        http_get=http_get,
    ).check()

    assert report.ready is False
    assert report.checks["yandex"] == "unavailable"
    assert report.checks["telegram"] == "ok"


def test_readiness_reports_invalid_telegram_token():
    def http_get(url: str, **_kwargs):
        if url.endswith("/v1/models"):
            return FakeResponse({"data": []})
        return FakeResponse({"ok": False})

    report = ExternalReadinessChecker(
        settings_provider=_settings,
        http_get=http_get,
    ).check()

    assert report.ready is False
    assert report.checks["yandex"] == "ok"
    assert report.checks["telegram"] == "unavailable"
