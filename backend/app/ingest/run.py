"""Ingest źródeł do korpusu: `python -m app.ingest.run --max 10`."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, replace
from datetime import datetime, time

from app.config import Settings, get_settings
from app.ingest import adapters
from app.ingest.extract import build_excerpt, content_hash
from app.ingest.http import DomainThrottle, get_html, get_json, get_page
from app.ingest.registry import SOURCES, SourceSpec, get_sources
from app.retrieval.corpus import CorpusStore
from app.retrieval.embeddings import Embedder, build_embedder
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
    if spec.adapter == "govpl_list":
        _, html = await get_html(spec.url, settings, throttle=throttle)
        return adapters.govpl_list(html, spec, limit)
    if spec.adapter == "html_links":
        _, html = await get_html(spec.url, settings, throttle=throttle)
        return adapters.html_links(html, spec, limit, spec.params["link_regex"])
    if spec.adapter == "rso_api":
        template = spec.params["api_template"]
        voivodeships = spec.params["voivodeships"]
        payloads = []
        for voivodeship in voivodeships:
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


async def _enrich(
    document: adapters.RawDocument,
    settings: Settings,
    throttle: DomainThrottle,
) -> tuple[adapters.RawDocument, str | None]:
    if not document.fetch_content:
        excerpt = document.excerpt or build_excerpt(document.title)
        return replace(document, excerpt=excerpt), None
    try:
        page = await get_page(document.url, settings, throttle=throttle)
    except UrlFetchError as exc:
        log.warning("nie udało się pobrać %s: %s", document.url, exc.message)
        return replace(document, excerpt=build_excerpt(document.title)), exc.message
    published = document.published_at
    if published is None and page.published is not None:
        published = datetime.combine(page.published, time.min)
    excerpt = build_excerpt(page.text) if page.text.strip() else build_excerpt(document.title)
    return (
        replace(
            document,
            title=page.title.strip() or document.title,
            published_at=published,
            excerpt=excerpt,
            fetch_content=False,
        ),
        None,
    )


async def _ingest_source(
    spec: SourceSpec,
    settings: Settings,
    corpus: CorpusStore,
    embedder: Embedder | None,
    throttle: DomainThrottle,
    limit: int,
) -> IngestReport:
    errors = 0
    details: list[str] = []
    try:
        documents = await _collect(spec, settings, throttle, limit)
    except Exception as exc:  # źródło nie może wywalić całego przebiegu
        log.warning("ingest %s nie powiódł się: %s", spec.key, exc)
        return IngestReport(spec.key, 0, 0, 0, 1, "error", str(exc)[:300])

    enriched: list[adapters.RawDocument] = []
    for document in documents:
        item, error = await _enrich(document, settings, throttle)
        if error:
            errors += 1
            details.append(error)
        enriched.append(item)

    hashes = {
        document.url: content_hash(spec.publisher, document.title, document.excerpt)
        for document in enriched
    }
    new_documents = []
    for document in enriched:
        existing_hash, has_embedding = corpus.get_index_state(document.url)
        if existing_hash != hashes[document.url] or (embedder is not None and not has_embedding):
            new_documents.append(document)

    vectors: list[list[float]] = []
    if new_documents and embedder is not None:
        try:
            vectors = embedder.embed_documents(
                [f"{spec.publisher}. {document.title}. {document.excerpt}" for document in new_documents]
            )
        except Exception as exc:
            log.warning("embeddingi dla %s nie powiodły się: %s", spec.key, exc)
            details.append(f"embedding: {exc}")
            errors += 1
            vectors = []

    vector_by_url = dict(zip((document.url for document in new_documents), vectors, strict=False))
    stored = 0
    unchanged = 0
    for document in enriched:
        vector = vector_by_url.get(document.url)
        try:
            result = corpus.upsert_article(
                source_key=spec.key,
                publisher=spec.publisher,
                title=document.title,
                excerpt=document.excerpt,
                url=document.url,
                published_at=document.published_at,
                content_hash=hashes[document.url],
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
    return IngestReport(spec.key, len(enriched), stored, unchanged, errors, status, "; ".join(details[:3]) or None)


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
