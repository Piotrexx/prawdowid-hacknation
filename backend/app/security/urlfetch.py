"""Pobieranie strony wskazanej przez użytkownika z ochroną przed SSRF."""

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.config import Settings

_MAX_REDIRECTS = 4
_ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_ROBOTS_TTL_S = 3600
_robots_cache: dict[str, tuple[float, RobotFileParser | None]] = {}


class UrlFetchError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    published: date | None


@dataclass
class _Reply:
    status: int
    headers: httpx.Headers
    body: bytes


def parse_robots(status: int, text: str) -> RobotFileParser | None:
    """None oznacza zakaz dla wszystkich: tak traktujemy robots.txt zwracający 401/403."""
    if status in (401, 403):
        return None
    parser = RobotFileParser()
    parser.parse(text.splitlines() if status == 200 else [])
    return parser


async def _resolve_public_ip(host: str) -> str:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlFetchError("url_unreachable", "Nie udało się odnaleźć tej strony.") from exc
    addresses = [info[4][0] for info in infos]
    # Wystarczy jeden adres prywatny, żeby odrzucić host (ochrona przed mieszanymi rekordami DNS).
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        raise UrlFetchError("url_not_allowed", "Ten adres nie jest publiczną stroną internetową.")
    return addresses[0]


async def _get(client: httpx.AsyncClient, url: str, max_bytes: int) -> _Reply:
    """Jedno żądanie pod wcześniej zweryfikowany adres IP (bez ponownego zapytania DNS,
    co zamyka okno na DNS rebinding między walidacją a połączeniem)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UrlFetchError("url_invalid", "To nie wygląda na poprawny adres strony (http lub https).")
    if parts.port not in (None, 80, 443) or parts.username or parts.password:
        raise UrlFetchError("url_not_allowed", "Ten adres nie jest publiczną stroną internetową.")
    ip = await _resolve_public_ip(parts.hostname)
    netloc = f"[{ip}]" if ":" in ip else ip
    if parts.port:
        netloc += f":{parts.port}"
    pinned = parts._replace(netloc=netloc).geturl()
    request = client.build_request(
        "GET", pinned, headers={"Host": parts.netloc}, extensions={"sni_hostname": parts.hostname}
    )
    response = await client.send(request, stream=True)
    try:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise UrlFetchError("url_too_large", "Ta strona jest zbyt duża, żeby ją przeanalizować.")
    finally:
        await response.aclose()
    return _Reply(response.status_code, response.headers, bytes(body))


async def _robots_allow(client: httpx.AsyncClient, url: str, user_agent: str) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    cached = _robots_cache.get(origin)
    if cached is None or time.monotonic() - cached[0] > _ROBOTS_TTL_S:
        try:
            reply = await _get(client, f"{origin}/robots.txt", 500_000)
            parser = parse_robots(reply.status, reply.body.decode("utf-8", errors="replace"))
        except (httpx.HTTPError, UrlFetchError):
            parser = parse_robots(404, "")
        cached = (time.monotonic(), parser)
        _robots_cache[origin] = cached
    return cached[1] is not None and cached[1].can_fetch(user_agent, url)


def _extract(html: bytes, url: str) -> FetchedPage:
    import trafilatura

    doc = trafilatura.bare_extraction(html, url=url, include_comments=False, with_metadata=True)
    text = (getattr(doc, "text", None) or "").strip() if doc else ""
    if not text:
        raise UrlFetchError("url_no_content", "Nie udało się odczytać treści z tej strony.")
    published = None
    try:
        published = date.fromisoformat((getattr(doc, "date", None) or "")[:10])
    except ValueError:
        pass
    return FetchedPage(url=url, title=(getattr(doc, "title", None) or "").strip(), text=text, published=published)


async def _fetch_with_redirects(
    url: str, settings: Settings, *, max_bytes: int | None = None
) -> tuple[str, _Reply]:
    headers = {"User-Agent": settings.crawler_user_agent, "Accept": "text/html,*/*;q=0.5"}
    limit = max_bytes or settings.url_fetch_max_bytes
    async with httpx.AsyncClient(headers=headers, timeout=settings.url_fetch_timeout_s) as client:
        try:
            for _ in range(_MAX_REDIRECTS + 1):
                if not await _robots_allow(client, url, settings.crawler_user_agent):
                    raise UrlFetchError(
                        "url_blocked_by_site",
                        "Ta strona nie pozwala na automatyczne pobieranie treści.",
                    )
                reply = await _get(client, url, limit)
                if 300 <= reply.status < 400 and reply.headers.get("location"):
                    url = urljoin(url, reply.headers["location"])
                    continue
                break
            else:
                raise UrlFetchError("url_unreachable", "Ta strona przekierowuje zbyt wiele razy.")
        except httpx.HTTPError as exc:
            raise UrlFetchError("url_unreachable", "Nie udało się połączyć z tą stroną.") from exc
    if reply.status != 200:
        raise UrlFetchError("url_unreachable", f"Strona odpowiedziała błędem (kod {reply.status}).")
    return url, reply


def _check_content_type(reply: _Reply) -> None:
    content_type = reply.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_TYPES:
        raise UrlFetchError("url_unsupported_type", "Pod tym adresem nie ma strony z tekstem (np. to plik lub wideo).")


async def fetch_page(url: str, settings: Settings) -> FetchedPage:
    url, reply = await _fetch_with_redirects(url, settings)
    _check_content_type(reply)
    # trafilatura sama rozpoznaje kodowanie znaków, więc dostaje surowe bajty.
    return await asyncio.to_thread(_extract, reply.body, url)


async def fetch_html(url: str, settings: Settings) -> tuple[str, str]:
    """Pobiera surowy HTML (dla list linków w ingeście), z tą samą ochroną SSRF i robots.txt."""
    final_url, reply = await _fetch_with_redirects(url, settings)
    _check_content_type(reply)
    # aiter_bytes() już zdekompresował treść – usuwamy nagłówki, żeby httpx nie próbował tego drugi raz.
    headers = {
        key: value
        for key, value in reply.headers.items()
        if key.lower() not in ("content-encoding", "content-length")
    }
    text = httpx.Response(200, headers=headers, content=reply.body).text
    return final_url, text
