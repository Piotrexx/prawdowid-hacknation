"""Konektory pobierające dokumenty ze źródeł katalogu. Każdy zwraca listę `SourceDocument`."""

import hashlib
import logging
import re
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.ingest.registry import SourceSpec
from app.retrieval.corpus import SourceDocument
from app.security.injection import sanitize_untrusted
from app.security.urlfetch import parse_robots
from app.textutil import collapse_ws, strip_html, truncate

log = logging.getLogger("ingest")

CLAIMREVIEW_FEED = "https://storage.googleapis.com/datacommons-feeds/factcheck/latest/data.json"
_TRACKING_PARAMS = ("utm_", "source", "fbclid", "gclid")
_PL_MONTHS = ("sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru")
_PL_DATE_RE = re.compile(r"(\d{1,2}) (\w{3,}) (\d{4})")
_GOVPL_ITEM_RE = re.compile(
    r'<span class="date">\s*(\d{2})\.(\d{2})\.(\d{4})\s*</span>.*?'
    r'<div class="title">\s*<a href="([^"]+)">(.*?)</a>.*?<div class="intro">(.*?)</div>',
    re.DOTALL,
)


class Fetcher:
    """Klient HTTP z opóźnieniem między żądaniami i poszanowaniem robots.txt."""

    def __init__(self, user_agent: str, delay_s: float = 0.5):
        self.user_agent = user_agent
        self.delay_s = delay_s
        self.client = httpx.Client(
            headers={"User-Agent": user_agent}, timeout=25.0, follow_redirects=True
        )
        self._robots: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            try:
                resp = self.client.get(f"{host}/robots.txt")
                self._robots[host] = parse_robots(resp.status_code, resp.text)
            except httpx.HTTPError:
                self._robots[host] = parse_robots(404, "")
        parser = self._robots[host]
        return parser is not None and parser.can_fetch(self.user_agent, url)

    def get(self, url: str) -> httpx.Response | None:
        if not self.allowed(url):
            log.warning("robots.txt nie pozwala pobrać %s – pomijam", url)
            return None
        time.sleep(self.delay_s)
        try:
            resp = self.client.get(url)
        except httpx.HTTPError as exc:
            log.warning("błąd pobierania %s: %s", url, exc)
            return None
        if resp.status_code != 200:
            log.warning("HTTP %s dla %s – pomijam", resp.status_code, url)
            return None
        return resp


def _doc_id(source_key: str, url: str, extra: str = "") -> str:
    return f"{source_key}:{hashlib.sha1((url + extra).encode()).hexdigest()[:12]}"


def _clean_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(_TRACKING_PARAMS)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _parse_polish_rss_date(value: str) -> date | None:
    """Część polskich kanałów podaje datę jako „pt, 13 lis 2026 …”, czego feedparser nie rozumie."""
    match = _PL_DATE_RE.search(value.lower())
    if not match or match.group(2)[:3] not in _PL_MONTHS:
        return None
    return date(int(match.group(3)), _PL_MONTHS.index(match.group(2)[:3]) + 1, int(match.group(1)))


def _make(
    src: SourceSpec, *, url: str, title: str, text: str, published: date | None, id_key: str = "", **extra
) -> SourceDocument:
    excerpt = truncate(collapse_ws(text), 600)
    return SourceDocument(
        external_id=_doc_id(src.key, url, id_key),
        source_key=src.key,
        # Znaki niewidoczne ze źródła (częste w kanałach RSS) nie mogą trafić do korpusu.
        title=collapse_ws(sanitize_untrusted(title)),
        publisher=src.publisher,
        url=url,
        source_type=src.source_type,
        tier=src.tier,
        license=src.license,
        storage=src.storage,
        published_at=published,
        text=sanitize_untrusted(text).strip(),
        excerpt=excerpt,
        **extra,
    )


def fetch_rss(src: SourceSpec, fetcher: Fetcher) -> list[SourceDocument]:
    import feedparser

    resp = fetcher.get(src.params["feed"])
    if resp is None:
        return []
    excerpt_chars = src.params.get("excerpt_chars", 600)
    docs = []
    for entry in feedparser.parse(resp.content).entries[: src.params.get("max_items", 30)]:
        link, title = entry.get("link"), strip_html(entry.get("title", ""))
        if not link or not title:
            continue
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = (
            date(stamp.tm_year, stamp.tm_mon, stamp.tm_mday)
            if stamp
            else _parse_polish_rss_date(entry.get("published", ""))
        )
        summary = truncate(strip_html(entry.get("summary", "")), excerpt_chars)
        text = f"{title}. {summary}" if summary and summary != title else title
        docs.append(_make(src, url=_clean_url(link), title=title, text=text, published=published))
    return docs


def fetch_govpl(src: SourceSpec, fetcher: Fetcher) -> list[SourceDocument]:
    import trafilatura

    docs = []
    for page in range(1, src.params.get("pages", 3) + 1):
        listing = fetcher.get(f"{src.params['listing']}?page={page}&size=10")
        if listing is None:
            break
        for day, month, year, href, raw_title, raw_intro in _GOVPL_ITEM_RE.findall(listing.text):
            url = urljoin(src.params["listing"], href)
            title, intro = strip_html(raw_title), strip_html(raw_intro)
            article = fetcher.get(url)
            body = trafilatura.extract(article.text, include_comments=False) if article else None
            docs.append(
                _make(
                    src,
                    url=url,
                    title=title,
                    text=body or f"{title}\n\n{intro}",
                    published=date(int(year), int(month), int(day)),
                )
            )
    return docs


def fetch_sejm_eli(src: SourceSpec, fetcher: Fetcher) -> list[SourceDocument]:
    p = src.params
    resp = fetcher.get(f"https://api.sejm.gov.pl/eli/acts/{p['publisher']}/{p['year']}")
    if resp is None:
        return []
    wanted = set(p.get("types", []))
    items = [i for i in resp.json()["items"] if not wanted or i.get("type") in wanted]
    items.sort(key=lambda i: i.get("promulgation") or "", reverse=True)
    docs = []
    for item in items[: p.get("limit", 60)]:
        facts = [
            f"Typ aktu: {item.get('type')}",
            f"Status: {item.get('status')}",
            f"Ogłoszono: {item.get('promulgation')} ({item.get('displayAddress')})",
        ]
        if item.get("entryIntoForce"):
            facts.append(f"Wejście w życie: {item['entryIntoForce']}")
        docs.append(
            _make(
                src,
                url=f"https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id={item['address']}",
                title=item["title"],
                text=f"{item['title']}\n" + ". ".join(facts) + ".",
                published=_parse_date(item.get("promulgation")),
            )
        )
    return docs


def _iter_claimreviews(feed_path: Path) -> Iterable[dict]:
    import ijson

    with feed_path.open("rb") as fh:
        for element in ijson.items(fh, "dataFeedElement.item"):
            for item in element.get("item") or []:
                item.setdefault("url", element.get("url"))
                yield item


def load_claimreviews(feed_path: Path, domains: set[str]) -> dict[str, list[dict]]:
    """Jedno przejście po ~200 MB pliku dla wszystkich źródeł ClaimReview naraz."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in _iter_claimreviews(feed_path):
        domain = urlsplit(item.get("url") or "").netloc.lower().removeprefix("www.")
        if domain in domains and item.get("claimReviewed"):
            grouped[domain].append(item)
    return grouped


def build_claimreview_docs(src: SourceSpec, items: list[dict]) -> list[SourceDocument]:
    items = sorted(items, key=lambda i: str(i.get("datePublished") or ""), reverse=True)
    docs = []
    for item in items[: src.params.get("max_items", 100)]:
        claim = collapse_ws(item["claimReviewed"])
        rating_obj = item.get("reviewRating") or {}
        rating = collapse_ws(str(rating_obj.get("alternateName") or rating_obj.get("ratingValue") or ""))
        reviewed = item.get("itemReviewed") or {}
        lines = [f"Sprawdzane twierdzenie: {claim}"]
        author = (reviewed.get("author") or {}).get("name")
        if author:
            lines.append(f"Autor twierdzenia: {collapse_ws(author)}")
        if rating:
            lines.append(f"Ocena redakcji: {rating}")
        if rating_obj.get("ratingExplanation"):
            lines.append(collapse_ws(rating_obj["ratingExplanation"]))
        appearances = [a.get("url") for a in reviewed.get("appearance") or [] if a.get("url")]
        docs.append(
            _make(
                src,
                url=item["url"],
                title=truncate(claim, 140),
                text="\n".join(lines),
                published=_parse_date(str(item.get("datePublished") or "")),
                # Jeden artykuł często ocenia kilka twierdzeń – każde to osobny rekord.
                id_key=claim,
                claim_reviewed=claim,
                rating=rating or None,
                appearance_urls=tuple(appearances[:5]),
            )
        )
    return docs


def download_claimreview_feed(fetcher: Fetcher, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("pobieram kanał ClaimReview do %s", target)
    with fetcher.client.stream("GET", CLAIMREVIEW_FEED) as resp, target.open("wb") as fh:
        resp.raise_for_status()
        for chunk in resp.iter_bytes():
            fh.write(chunk)


CONNECTORS: dict[str, Callable[[SourceSpec, Fetcher], list[SourceDocument]]] = {
    "rss": fetch_rss,
    "govpl": fetch_govpl,
    "sejm_eli": fetch_sejm_eli,
}


def utc_now() -> datetime:
    return datetime.now(UTC)
