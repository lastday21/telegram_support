import socket

from app.infra import dns_fallback


def test_dns_fallback_uses_https_after_system_dns_failure(monkeypatch):
    calls = []

    def original(host, port, family=0, type=0, proto=0, flags=0):
        calls.append((host, port, family))
        if host == "lp.vk.com":
            raise socket.gaierror("dns failed")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]

    monkeypatch.setattr(dns_fallback, "_original_getaddrinfo", original)
    monkeypatch.setattr(
        dns_fallback,
        "_resolve_over_https",
        lambda hostname: ["93.186.237.7"],
    )

    result = dns_fallback._getaddrinfo(
        "lp.vk.com",
        443,
        socket.AF_UNSPEC,
        socket.SOCK_STREAM,
    )

    assert result[0][4] == ("93.186.237.7", 443)
    assert calls == [
        ("lp.vk.com", 443, socket.AF_UNSPEC),
        ("93.186.237.7", 443, socket.AF_INET),
    ]
