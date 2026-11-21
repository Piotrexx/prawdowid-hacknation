"""Aktualizacja korpusu: `uv run python -m app.ingest.run [--only id1,id2] [--claimreview-cache plik]`."""

import argparse
import hashlib
import json
import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.catalog import Document, load_catalog
from app.config import get_settings
from app.ingest.connectors import (
    CLAIMREVIEW_FEED,
    CONNECTORS,
    Fetcher,
    build_claimreview_docs,
    load_claimreviews,
)
from app.textutil import site_domain

log = logging.getLogger("ingest")


def load_documents(path: Path) -> dict[str, Document]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        docs = [Document.model_validate_json(line) for line in fh if line.strip()]
    return {d.id: d for d in docs}


def _download_feed(fetcher: Fetcher, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    log.info("pobieram kanał ClaimReview (~200 MB) do %s", target)
    with fetcher.client.stream("GET", CLAIMREVIEW_FEED) as resp, target.open("wb") as fh:
        resp.raise_for_status()
        for chunk in resp.iter_bytes():
            fh.write(chunk)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    parser.add_argument("--claimreview-cache", type=Path, default=settings.index_dir / "claimreview-feed.json")
    args = parser.parse_args()
    only = {s for s in args.only.split(",") if s}

    catalog = load_catalog(settings.catalog_path)
    fetcher = Fetcher(settings.crawler_user_agent)
    out_path = settings.corpus_dir / "documents.jsonl"
    documents = load_documents(out_path)
    known = set(catalog.by_id())
    # Dokumenty źródeł usuniętych z katalogu nie mogą zostać w korpusie.
    documents = {k: d for k, d in documents.items() if d.source_id in known}

    selected = [s for s in catalog.sources if s.connector and (not only or s.id in only)]
    claim_sources = [s for s in selected if s.connector == "claimreview"]
    claim_items: dict[str, list[dict]] = {}
    if claim_sources:
        if not args.claimreview_cache.exists():
            _download_feed(fetcher, args.claimreview_cache)
        claim_items = load_claimreviews(args.claimreview_cache, {s.params["domain"] for s in claim_sources})

    report: dict[str, dict] = {}
    for src in selected:
        try:
            if src.connector == "claimreview":
                fetched = build_claimreview_docs(src, claim_items.get(src.params["domain"], []))
            else:
                fetched = CONNECTORS[src.connector](src, fetcher)
        except Exception as exc:  # jeden zepsuty konektor nie może zatrzymać aktualizacji
            log.exception("źródło %s nie powiodło się", src.id)
            report[src.id] = {"fetched": 0, "new": 0, "error": str(exc)}
            continue
        new = [d for d in fetched if d.id not in documents and d.text]
        documents.update({d.id: d for d in new})
        report[src.id] = {"fetched": len(fetched), "new": len(new)}
        log.info("%s: pobrano %d, nowych %d", src.id, len(fetched), len(new))

    ordered = sorted(documents.values(), key=lambda d: d.id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(d.model_dump_json() + "\n" for d in ordered)
    out_path.write_text(payload, encoding="utf-8")

    manifest = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "version": hashlib.sha256(payload.encode()).hexdigest()[:12],
        "documents": len(ordered),
        "domains": len({site_domain(d.url) for d in ordered}),
        "by_source": dict(Counter(d.source_id for d in ordered)),
        "by_type": dict(Counter(d.source_type for d in ordered)),
        "last_run": report,
    }
    (settings.corpus_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log.info("korpus: %d dokumentów, %d domen", manifest["documents"], manifest["domains"])


if __name__ == "__main__":
    main()
