"""Warstwa HTTP ingestu: throttling per domena i ponowienia."""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlsplit

import httpx

from app.config import Settings
from app.security.urlfetch import UrlFetchError, fetch_html, fetch_page

log = logging.getLogger("ingest.http")

_ATTEMPTS = 2


class DomainThrottle:
    def __init__(self, delay_s: float):
        self._delay = delay_s
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, host: str) -> asyncio.Lock:
        return self._locks.setdefault(host, asyncio.Lock())

    async def wait(self, url: str) -> None:
        host = urlsplit(url).hostname or ""
        async with self._lock(host):
            elapsed = time.monotonic() - self._last.get(host, 0.0)
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            self._last[host] = time.monotonic()


async def get_json(url: str, settings: Settings, *, throttle: DomainThrottle | None = None) -> dict | list:
    if throttle:
        await throttle.wait(url)
    headers = {"User-Agent": settings.crawler_user_agent, "Accept": "application/json"}
    last_error: Exception | None = None
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.ingest_timeout_s, headers=headers) as client:
                response = await client.get(url)
            if response.status_code >= 400:
                raise UrlFetchError("http_error", f"HTTP {response.status_code} dla {url}")
            if not response.content:
                return []
            return response.json()
        except (httpx.HTTPError, ValueError, UrlFetchError) as exc:
            last_error = exc
            if attempt < _ATTEMPTS:
                await asyncio.sleep(1.5 * attempt)
    raise UrlFetchError("http_error", f"Nie udało się pobrać {url}: {last_error}")


async def get_html(url: str, settings: Settings, *, throttle: DomainThrottle | None = None) -> tuple[str, str]:
    if throttle:
        await throttle.wait(url)
    return await fetch_html(url, settings)


async def get_page(url: str, settings: Settings, *, throttle: DomainThrottle | None = None):
    if throttle:
        await throttle.wait(url)
    return await fetch_page(url, settings)
