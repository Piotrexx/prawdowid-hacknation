"""Odwrotne wyszukiwanie obrazu przez PicImageSearch (scraping, bez kluczy API).

Silniki bywają niestabilne (zmiany stron, limity, captcha), więc każdy działa niezależnie,
a jego awaria trafia do odpowiedzi jako status, a nie przerywa sprawdzenia.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

import httpx
from PicImageSearch import Bing, Network, Tineye, Yandex

log = logging.getLogger("image_search")

SUPPORTED_ENGINES = ("yandex", "tineye", "bing")
_PER_ENGINE_LIMIT = 8


@dataclass
class FoundImage:
    engine: str
    page_url: str
    image_url: str | None
    thumbnail_url: str | None
    title: str | None
    domain: str | None
    first_seen: date | None = None


@dataclass
class EngineResult:
    engine: str
    ok: bool
    found: list[FoundImage]
    total: int = 0
    error: str | None = None


def _domain(url: str) -> str | None:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.") or None


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


async def _yandex(client: httpx.AsyncClient, data: bytes) -> tuple[list[FoundImage], int]:
    resp = await Yandex(client=client).search(file=data)
    found = [
        FoundImage(
            engine="yandex",
            page_url=item.url,
            image_url=(item.origin.get("originalImage") or {}).get("url"),
            thumbnail_url=item.thumbnail or None,
            title=item.title or None,
            domain=item.source or _domain(item.url),
        )
        for item in resp.raw[:_PER_ENGINE_LIMIT]
    ]
    return found, len(resp.raw)


async def _tineye(client: httpx.AsyncClient, data: bytes) -> tuple[list[FoundImage], int]:
    resp = await Tineye(client=client).search(file=data)
    found = [
        FoundImage(
            engine="tineye",
            page_url=item.url,
            image_url=item.image_url or None,
            thumbnail_url=item.thumbnail or None,
            title=None,
            domain=item.domain or _domain(item.url),
            first_seen=_date(item.crawl_date),
        )
        for item in resp.raw[:_PER_ENGINE_LIMIT]
    ]
    return found, len(resp.raw)


async def _bing(client: httpx.AsyncClient, data: bytes) -> tuple[list[FoundImage], int]:
    # Wyłączony domyślnie: w PicImageSearch 3.12.11 wysyłanie pliku do Bing nie działa
    # (Bing zmienił stronę, biblioteka nie znajduje BCID).
    resp = await Bing(client=client).search(file=data)
    found = [
        FoundImage(
            engine="bing",
            page_url=item.url,
            image_url=item.image_url or None,
            thumbnail_url=item.thumbnail or None,
            title=item.name or None,
            domain=_domain(item.url),
        )
        for item in resp.pages_including[:_PER_ENGINE_LIMIT]
    ]
    return found, len(resp.pages_including)


_ENGINES: dict[str, Callable[[httpx.AsyncClient, bytes], Awaitable[tuple[list[FoundImage], int]]]] = {
    "yandex": _yandex,
    "tineye": _tineye,
    "bing": _bing,
}


async def _run_engine(name: str, client: httpx.AsyncClient, data: bytes, timeout_s: float) -> EngineResult:
    # TinEye potrafi jednorazowo nie odpowiedzieć w czasie, więc dostaje jedną ponowną próbę.
    attempts = 2 if name == "tineye" else 1
    error = ""
    for _ in range(attempts):
        try:
            found, total = await asyncio.wait_for(_ENGINES[name](client, data), timeout_s)
            return EngineResult(engine=name, ok=True, found=found, total=total)
        except TimeoutError:
            error = "przekroczono czas odpowiedzi"
        except Exception as exc:  # silniki scrapują strony, więc mogą paść na dowolnym etapie
            error = f"{type(exc).__name__}: {str(exc)[:120]}".rstrip(": ")
    log.warning("silnik %s niedostępny: %s", name, error)
    return EngineResult(engine=name, ok=False, found=[], error=error)


async def search_all(data: bytes, engines: list[str], timeout_s: float) -> list[EngineResult]:
    async with Network(timeout=timeout_s) as client:
        return list(await asyncio.gather(*(_run_engine(name, client, data, timeout_s) for name in engines)))
