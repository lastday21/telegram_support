import requests
import pytest

from app.infra.yandex_resilience import (
    YandexCallPolicy,
    YandexCircuitOpenError,
)


def test_yandex_policy_retries_temporary_connection_errors():
    calls = 0
    delays = []
    policy = YandexCallPolicy(
        retry_delays=(1, 2),
        sleeper=delays.append,
    )

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise requests.ConnectionError("temporary")
        return "ok"

    assert policy.execute(operation) == "ok"
    assert calls == 3
    assert delays == [1, 2]


def test_yandex_policy_does_not_retry_client_errors():
    calls = 0
    delays = []
    response = requests.Response()
    response.status_code = 400
    error = requests.HTTPError("bad request", response=response)
    policy = YandexCallPolicy(retry_delays=(1, 2), sleeper=delays.append)

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise error

    with pytest.raises(requests.HTTPError):
        policy.execute(operation)

    assert calls == 1
    assert delays == []


def test_yandex_policy_blocks_calls_after_repeated_failures_and_recovers():
    now = [100.0]
    policy = YandexCallPolicy(
        retry_delays=(),
        failure_limit=2,
        recovery_seconds=10,
        clock=lambda: now[0],
    )

    def failed() -> None:
        raise requests.Timeout("temporary")

    with pytest.raises(requests.Timeout):
        policy.execute(failed)
    with pytest.raises(requests.Timeout):
        policy.execute(failed)
    with pytest.raises(YandexCircuitOpenError):
        policy.execute(lambda: "not called")

    now[0] += 11
    assert policy.execute(lambda: "recovered") == "recovered"
    assert policy.blocked_for() == 0
