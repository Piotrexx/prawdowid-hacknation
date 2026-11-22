"""Adaptery źródeł: listy HTML, API JSON i pojedyncze strony dzienne."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urljoin

import lxml.html

from app.ingest.extract import build_excerpt
from app.ingest.registry import SourceSpec

_MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9, "października": 10,
    "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}


@dataclass(frozen=True)
class RawDocument:
    url: str
    title: str
    excerpt: str = ""
    published_at: datetime | None = None
    fetch_content: bool = False


def _text(node) -> str:
    return " ".join(node.text_content().split()).strip()


def parse_dmy(value: str) -> datetime | None:
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", value)
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("T", " ")
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(cleaned[:length], fmt)
        except ValueError:
            continue
    return None


def govpl_list(html: str, spec: SourceSpec, limit: int) -> list[RawDocument]:
    """Listy na gov.pl mają powtarzalny blok `.art-prev` z tytułem i datą."""
    tree = lxml.html.fromstring(html)
    documents: list[RawDocument] = []
    seen: set[str] = set()
    for item in tree.xpath('//*[contains(@class,"art-prev")]//li'):
        anchors = item.xpath('.//*[contains(@class,"title")]//a[@href]')
        if not anchors:
            anchors = item.xpath(".//a[@href]")
        if not anchors:
            continue
        anchor = anchors[0]
        href = anchor.get("href") or ""
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        url = urljoin(spec.url, href)
        if url in seen or url.rstrip("/") == spec.url.rstrip("/"):
            continue
        title = _text(anchor)
        if not title:
            continue
        date_text = " ".join(item.xpath('.//*[contains(@class,"date")]//text()'))
        seen.add(url)
        documents.append(
            RawDocument(
                url=url,
                title=title,
                published_at=parse_dmy(date_text),
                fetch_content=True,
            )
        )
        if len(documents) >= limit:
            break
    return documents


def html_links(html: str, spec: SourceSpec, limit: int, pattern: str) -> list[RawDocument]:
    tree = lxml.html.fromstring(html)
    regex = re.compile(pattern)
    documents: list[RawDocument] = []
    seen: set[str] = set()
    for anchor in tree.xpath("//a[@href]"):
        href = (anchor.get("href") or "").strip()
        if not href or not regex.search(href):
            continue
        url = urljoin(spec.url, href)
        if url in seen:
            continue
        title = _text(anchor)
        if not title:
            continue
        seen.add(url)
        documents.append(RawDocument(url=url, title=title, fetch_content=True))
        if len(documents) >= limit:
            break
    return documents


def rso_documents(payloads: list[dict], spec: SourceSpec, limit: int) -> list[RawDocument]:
    now = datetime.now()
    merged: dict[int, dict] = {}
    for payload in payloads:
        for item in payload.get("newses", []) if isinstance(payload, dict) else []:
            item_id = item.get("id")
            if item_id is None:
                continue
            valid_to = parse_dt(item.get("valid_to"))
            if valid_to and valid_to < now - timedelta(days=1):
                continue
            merged[item_id] = item

    def sort_key(item: dict) -> tuple[int, str]:
        try:
            alarm = int(item.get("rso_alarm") or 0)
        except (TypeError, ValueError):
            alarm = 0
        return alarm, str(item.get("valid_from") or item.get("created_at") or "")

    documents: list[RawDocument] = []
    for item in sorted(merged.values(), key=sort_key, reverse=True)[:limit]:
        title = (item.get("title") or "").strip() or "Komunikat RSO"
        content = (item.get("content") or "").strip()
        location = (item.get("location_name") or item.get("river_name") or "").strip()
        shortcut = (item.get("shortcut") or "").strip()
        excerpt = build_excerpt(" ".join(part for part in [content, location, shortcut] if part))
        documents.append(
            RawDocument(
                url=f"https://www.gov.pl/web/gov/ostrzezenia#rso-{item.get('id')}",
                title=title,
                excerpt=excerpt,
                published_at=parse_dt(item.get("valid_from")) or parse_dt(item.get("created_at")),
            )
        )
    return documents


def imgw_documents(payload: list | dict, spec: SourceSpec, limit: int) -> list[RawDocument]:
    items = payload if isinstance(payload, list) else [payload]
    kind = spec.params.get("kind", "meteo")
    base = "https://meteo.imgw.pl/" if kind == "meteo" else "https://hydro.imgw.pl/"
    documents: list[RawDocument] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (item.get("nazwa_zdarzenia") or "").strip()
        if not name:
            continue
        level = (item.get("stopien") or "").strip()
        title = f"{name} – stopień {level}" if level else name
        parts = [item.get("tresc") or "", item.get("komentarz") or "", item.get("biuro") or ""]
        excerpt = build_excerpt(" ".join(part for part in parts if part))
        documents.append(
            RawDocument(
                url=f"{base}#{item.get('id')}",
                title=title,
                excerpt=excerpt,
                published_at=parse_dt(item.get("opublikowano")) or parse_dt(item.get("obowiazuje_od")),
            )
        )
    documents.sort(key=lambda document: document.published_at or datetime.min, reverse=True)
    return documents[:limit]


def _number(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def imgw_hydro_snapshot(payload: list, spec: SourceSpec, limit: int) -> list[RawDocument]:
    """Migawka sytuacji hydrologicznej: przekroczenia stanów albo jawny komunikat o ich braku."""
    exceeded: list[RawDocument] = []
    measured = 0
    for station in payload if isinstance(payload, list) else []:
        if not isinstance(station, dict):
            continue
        level = _number(station.get("stan_wody"))
        warning = _number(station.get("stan_ostrzegawczy"))
        alarm = _number(station.get("stan_alarmowy"))
        if level is None:
            continue
        measured += 1
        if warning is None or level < warning:
            continue
        state = "alarmowy" if alarm is not None and level >= alarm else "ostrzegawczy"
        station_name = (station.get("stacja") or "").strip()
        river = (station.get("rzeka") or "").strip()
        region = (station.get("wojewodztwo") or "").strip()
        title = f"Przekroczenie stanu {state} – {river}, {station_name}".strip(" –,")
        excerpt = build_excerpt(
            f"Stan wody {level:g} cm przekracza stan {state} "
            f"({warning:g} cm ostrzegawczy, {alarm:g} cm alarmowy). "
            f"Rzeka {river}, stacja {station_name}, województwo {region}. "
            f"Pomiar: {station.get('stan_wody_data_pomiaru') or 'brak daty'}."
        )
        exceeded.append(
            RawDocument(
                url=f"https://hydro.imgw.pl/#{station.get('id_stacji')}",
                title=title,
                excerpt=excerpt,
                published_at=parse_dt(station.get("stan_wody_data_pomiaru")),
            )
        )

    if exceeded:
        exceeded.sort(key=lambda document: document.published_at or datetime.min, reverse=True)
        return exceeded[:limit]

    today = datetime.now().strftime("%Y-%m-%d")
    return [
        RawDocument(
            url=f"https://hydro.imgw.pl/#sytuacja-{today}",
            title=f"IMGW – sytuacja hydrologiczna: brak przekroczeń ({today})",
            excerpt=(
                f"IMGW-PIB nie odnotowuje przekroczeń stanów ostrzegawczych ani alarmowych "
                f"na {measured} stacjach pomiarowych. Migawka z {today}."
            ),
            published_at=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
        )
    ]


def single_page_daily(html: str, spec: SourceSpec, limit: int) -> list[RawDocument]:
    tree = lxml.html.fromstring(html)
    content_nodes = tree.xpath('//*[contains(@class,"editor-content")]')
    if not content_nodes:
        return []
    text = _text(content_nodes[0])
    if not text:
        return []
    heading = tree.xpath("//article//h2//text()")
    heading_text = " ".join(heading).strip() or "Raport dobowy"
    published = _rcb_date(text)
    suffix = published.strftime("%Y-%m-%d") if published else datetime.now().strftime("%Y-%m-%d")
    title = f"{heading_text} – {published.strftime('%d.%m.%Y') if published else suffix}"
    return [
        RawDocument(
            url=f"{spec.url}#{suffix}",
            title=title,
            excerpt=build_excerpt(text, 3000),
            published_at=published,
        )
    ]


def _rcb_date(text: str) -> datetime | None:
    match = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", text[:400], re.IGNORECASE)
    if not match:
        return None
    day, month_name, year = match.groups()
    month = _MONTHS.get(month_name.lower())
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day))
    except ValueError:
        return None
