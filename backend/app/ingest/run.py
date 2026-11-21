"""Ingest źródeł do korpusu PostgreSQL: `python -m app.ingest.run --max 10`."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, time
from pathlib import Path

from app.config import Settings, get_settings
from app.ingest import adapters
from app.ingest.connectors import (
    CONNECTORS,
    Fetcher,
    build_claimreview_docs,
    download_claimreview_feed,
    load_claimreviews,
)
from app.ingest.extract import build_excerpt, content_hash
from app.ingest.http import DomainThrottle, get_html, get_json, get_page
from app.ingest.registry import SOURCES, SourceSpec, get_sources
from app.retrieval.corpus import CorpusStore, SourceDocument
from app.retrieval.embeddings import Embedder, build_embedder
from app.security.injection import sanitize_untrusted
from app.security.urlfetch import UrlFetchError
from app.store.db import Store

log = logging.getLogger("ingest")


@dataclass
class IngestReport:
    source_key: str
    fetched: int
    stored: int
    unchanged: int
    errors: int
    status: str
    detail: str | None = None

    def as_dict(self) -> dict:
        return {
            "source_key": self.source_key,
            "fetched": self.fetched,
            "stored": self.stored,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "status": self.status,
            "detail": self.detail,
        }


async def _collect(spec: SourceSpec, settings: Settings, throttle: DomainThrottle, limit: int):
    if spec.adapter in CONNECTORS:
        fetcher = Fetcher(settings.crawler_user_agent, settings.ingest_request_delay_s)
        return await asyncio.to_thread(CONNECTORS[spec.adapter], spec, fetcher)
    if spec.adapter == "govpl_list":
        _, html = await get_html(spec.url, settings, throttle=throttle)
        return adapters.govpl_list(html, spec, limit)
    if spec.adapter == "html_links":
        _, html = await get_html(spec.url, settings, throttle=throttle)
        return adapters.html_links(html, spec, limit, spec.params["link_regex"])
    if spec.adapter == "rso_api":
        template = spec.params["api_template"]
        payloads = []
        for voivodeship in spec.params["voivodeships"]:
            payload = await get_json(template.format(voivodeship=voivodeship), settings, throttle=throttle)
            payloads.append(payload)
        return adapters.rso_documents(payloads, spec, limit)
    if spec.adapter == "imgw_json":
        payload = await get_json(spec.params["api_url"], settings, throttle=throttle)
        return adapters.imgw_documents(payload, spec, limit)
    if spec.adapter == "imgw_hydro_snapshot":
        payload = await get_json(spec.params["api_url"], settings, throttle=throttle)
        return adapters.imgw_hydro_snapshot(payload, spec, limit)
    if spec.adapter == "single_page_daily":
        _, html = await get_html(spec.url, settings, throttle=throttle)
        return adapters.single_page_daily(html, spec, limit)
    raise ValueError(f"Nieznany adapter: {spec.adapter}")


async def _enrich_raw(
    document: adapters.RawDocument, spec: SourceSpec, settings: Settings, throttle: DomainThrottle
) -> tuple[adapters.RawDocument, str | None]:
    if not document.fetch_content:
        return document, None
    try:
        page = await get_page(document.url, settings, throttle=throttle)
    except UrlFetchError as exc:
        log.warning("nie udało się pobrać %s: %s", document.url, exc.message)
        return replace(document, excerpt=build_excerpt(document.title)), exc.message
    published = document.published_at
    if published is None and page.published is not None:
        published = datetime.combine(page.published, time.min)
    text = page.text if page.text.strip() else document.title
    return (
        replace(
            document,
            title=page.title.strip() or document.title,
            published_at=published,
            excerpt=text,
            fetch_content=False,
        ),
        None,
    )


def _to_source_document(document: adapters.RawDocument, spec: SourceSpec) -> SourceDocument:
    text = sanitize_untrusted(document.excerpt or document.title).strip()
    if spec.storage != "full_text":
        text = build_excerpt(text, 1500)
    external_id = f"{spec.key}:{hashlib.sha1(document.url.encode()).hexdigest()[:12]}"
    return SourceDocument(
        external_id=external_id,
        source_key=spec.key,
        publisher=spec.publisher,
        title=document.title,
        text=text,
        excerpt=build_excerpt(text, 1500),
        url=document.url,
        published_at=document.published_at,
        source_type=spec.source_type,
        tier=spec.tier,
        license=spec.license,
        storage=spec.storage,
    )


def _claimreview_documents(
    spec: SourceSpec, settings: Settings, fetcher: Fetcher
) -> list[SourceDocument]:
    cache_dir = Path(settings.ingest_cache_dir) if settings.ingest_cache_dir else Path(tempfile.gettempdir()) / "prawdowid"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / "claimreview-feed.json"
    if not cache.exists():
        download_claimreview_feed(fetcher, cache)
    domain = spec.params.get("domain", "")
    grouped = load_claimreviews(cache, {domain})
    return build_claimreview_docs(spec, grouped.get(domain, []))


async def _ingest_source(
    spec: SourceSpec,
    settings: Settings,
    corpus: CorpusStore,
    embedder: Embedder | None,
    throttle: DomainThrottle,
    limit: int,
    documents: list | None = None,
) -> IngestReport:
    errors = 0
    details: list[str] = []
    if documents is None:
        try:
            documents = await _collect(spec, settings, throttle, limit)
        except Exception as exc:  # źródło nie może wywalić całego przebiegu
            log.warning("ingest %s nie powiódł się: %s", spec.key, exc)
            return IngestReport(spec.key, 0, 0, 0, 1, "error", str(exc)[:300])

    documents = documents[:limit]
    normalized: list[SourceDocument] = []
    for document in documents:
        if isinstance(document, SourceDocument):
            normalized.append(document)
            continue
        enriched, error = await _enrich_raw(document, spec, settings, throttle)
        if error:
            errors += 1
            details.append(error)
        normalized.append(_to_source_document(enriched, spec))

    hashes = {
        document.external_id: content_hash(document.publisher, document.title, document.text)
        for document in normalized
    }
    new_documents = []
    for document in normalized:
        existing_hash, has_embedding = corpus.get_index_state(document.external_id)
        if existing_hash != hashes[document.external_id] or (embedder is not None and not has_embedding):
            new_documents.append(document)

    vectors: list[list[float]] = []
    if new_documents and embedder is not None:
        try:
            vectors = embedder.embed_documents(
                [f"{document.publisher}. {document.title}. {document.text[:1500]}" for document in new_documents]
            )
        except Exception as exc:
            log.warning("embeddingi dla %s nie powiodły się: %s", spec.key, exc)
            details.append(f"embedding: {exc}")
            errors += 1
            vectors = []

    vector_by_id = dict(zip((document.external_id for document in new_documents), vectors, strict=False))
    stored = unchanged = 0
    for document in normalized:
        vector = vector_by_id.get(document.external_id)
        try:
            result = corpus.upsert_document(
                document,
                content_hash=hashes[document.external_id],
                embedding=vector,
                embedding_model=embedder.model if embedder and vector is not None else None,
            )
        except Exception as exc:
            log.warning("zapis %s nie powiódł się: %s", document.url, exc)
            errors += 1
            details.append(str(exc)[:120])
            continue
        if result.status == "unchanged":
            unchanged += 1
        else:
            stored += 1

    status = "ok" if not errors else "partial"
    return IngestReport(spec.key, len(normalized), stored, unchanged, errors, status, "; ".join(details[:3]) or None)


async def run_ingest(
    settings: Settings,
    corpus: CorpusStore,
    embedder: Embedder | None,
    *,
    only: list[str] | None = None,
    max_per_source: int | None = None,
) -> list[IngestReport]:
    specs = get_sources(only)
    throttle = DomainThrottle(settings.ingest_request_delay_s)
    limit_default = max_per_source or settings.ingest_max_per_source
    reports: list[IngestReport] = []
    for spec in specs:
        limit = min(limit_default, spec.max_items)
        run_id = corpus.start_ingest_run(spec.key)
        if spec.adapter == "claimreview":
            try:
                fetcher = Fetcher(settings.crawler_user_agent, settings.ingest_request_delay_s)
                documents = await asyncio.to_thread(_claimreview_documents, spec, settings, fetcher)
                report = await _ingest_source(
                    spec, settings, corpus, embedder, throttle, limit, documents=documents
                )
            except Exception as exc:
                report = IngestReport(spec.key, 0, 0, 0, 1, "error", str(exc)[:300])
        else:
            report = await _ingest_source(spec, settings, corpus, embedder, throttle, limit)
        corpus.finish_ingest_run(
            run_id,
            fetched=report.fetched,
            stored=report.stored,
            errors=report.errors,
            status=report.status,
            detail=report.detail,
        )
        reports.append(report)
        log.info(
            "ingest %s: pobrano=%d zapisano=%d bez zmian=%d błędy=%d",
            report.source_key,
            report.fetched,
            report.stored,
            report.unchanged,
            report.errors,
        )
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest źródeł Prawdowida do PostgreSQL/pgvector.")
    parser.add_argument("--only", help="lista kluczy źródeł oddzielona przecinkami")
    parser.add_argument("--max", type=int, default=None, help="maksymalna liczba dokumentów na źródło")
    parser.add_argument("--list", action="store_true", help="pokaż dostępne źródła i zakończ")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if args.list:
        for spec in SOURCES:
            print(f"{spec.key:24} {spec.adapter:18} {spec.url}")
        return 0

    settings = get_settings()
    store = Store(settings.database_url)
    corpus = CorpusStore(store.engine)
    embedder = build_embedder(settings)
    only = args.only.split(",") if args.only else None
    reports = asyncio.run(run_ingest(settings, corpus, embedder, only=only, max_per_source=args.max))
    print(json.dumps([report.as_dict() for report in reports], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
