from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
from typing import Any, cast

import requests

logger = logging.getLogger(__name__)
DOH_URLS = (
    "https://1.1.1.1/dns-query",
    "https://8.8.8.8/resolve",
)
_original_getaddrinfo = socket.getaddrinfo
_cache: dict[str, tuple[float, list[str]]] = {}
_cache_lock = threading.Lock()
_installed = False


def _resolve_over_https(hostname: str) -> list[str]:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(hostname)
        if cached is not None and cached[0] > now:
            return cached[1]

    last_error: Exception | None = None
    for url in DOH_URLS:
        try:
            response = requests.get(
                url,
                params={"name": hostname, "type": "A"},
                headers={"Accept": "application/dns-json"},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
            answers = payload.get("Answer", []) if isinstance(payload, dict) else []
            addresses: list[str] = []
            ttl = 60
            for answer in answers:
                if not isinstance(answer, dict) or answer.get("type") != 1:
                    continue
                address = str(answer.get("data", ""))
                try:
                    ipaddress.IPv4Address(address)
                except ipaddress.AddressValueError:
                    continue
                addresses.append(address)
                ttl = min(ttl, max(10, int(answer.get("TTL", 60))))
            if addresses:
                unique_addresses = list(dict.fromkeys(addresses))
                with _cache_lock:
                    _cache[hostname] = (now + ttl, unique_addresses)
                return unique_addresses
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise socket.gaierror(f"Не удалось определить адрес {hostname}") from last_error
    raise socket.gaierror(f"Не удалось определить адрес {hostname}")


def _getaddrinfo(
    host: str | bytes | None,
    port: str | int | None,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
) -> list[tuple[Any, ...]]:
    try:
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        if host is None or family == socket.AF_INET6:
            raise
        hostname = host.decode() if isinstance(host, bytes) else host
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise

        results: list[tuple[Any, ...]] = []
        for address in _resolve_over_https(hostname):
            results.extend(
                _original_getaddrinfo(
                    address,
                    port,
                    socket.AF_INET,
                    type,
                    proto,
                    flags,
                )
            )
        logger.info("Адрес %s определён через запасной канал", hostname)
        return results


def install_dns_fallback() -> None:
    global _installed
    if _installed:
        return
    socket.getaddrinfo = cast(Any, _getaddrinfo)
    _installed = True
