import csv
import io
import json
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.ingest.registry import get_sources
from app.ingest.run import run_ingest
from app.integrations.stix import stix_bundle
from app.schemas import (
    ArchiveOut,
    CaseOut,
    CaseUpdate,
    CheckListItem,
    CheckResponse,
    MetricsResponse,
    SecurityEventOut,
)
from app.store.db import Store

router = APIRouter(prefix="/admin", tags=["moderator"], dependencies=[Depends(require_admin)])

_CSV_COLUMNS = [
    "check_id", "created_at", "channel", "status", "error_code", "input_kind", "input_text", "input_url",
    "claim_id", "claim_text", "verdict", "strength_level", "strength_score", "conflict", "risk",
    "source_urls", "moderator_case_id", "summary_verdict", "confidence", "keywords", "main_topic",
    "factcheck_count", "duration_ms", "tokens_in", "tokens_out", "bielik_tokens_in",
    "bielik_tokens_out", "cost_usd",
]


def _store(request: Request) -> Store:
    return request.app.state.store


@router.get("/metrics", response_model=MetricsResponse)
def metrics(request: Request) -> MetricsResponse:
    return _store(request).metrics()


@router.get("/cases", response_model=list[CaseOut])
def list_cases(request: Request, status: Literal["open", "in_review", "resolved"] | None = None) -> list[CaseOut]:
    return _store(request).list_cases(status=status)


@router.patch("/cases/{case_id}", response_model=CaseOut)
def update_case(request: Request, case_id: int, payload: CaseUpdate) -> CaseOut:
    updated = _store(request).update_case(case_id, status=payload.status, note=payload.note)
    if updated is None:
        raise HTTPException(404, "Nie ma takiej sprawy.")
    return updated


@router.get("/events", response_model=list[SecurityEventOut])
def list_events(request: Request, limit: Annotated[int, Query(ge=1, le=500)] = 50) -> list[SecurityEventOut]:
    return _store(request).list_events(limit)


@router.get("/checks", response_model=list[CheckListItem])
def list_checks(request: Request, limit: Annotated[int, Query(ge=1, le=500)] = 50) -> list[CheckListItem]:
    return _store(request).list_checks(limit)


@router.get("/archive", response_model=list[ArchiveOut])
def list_archives(request: Request, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[ArchiveOut]:
    return _store(request).list_archives(limit)


@router.delete("/archive/{archive_id}")
def delete_archive(request: Request, archive_id: str) -> dict[str, bool]:
    deleted = _store(request).delete_archive(archive_id)
    if not deleted:
        raise HTTPException(404, "Nie ma takiego materiału archiwalnego.")
    return {"deleted": True}


def _csv_safe(value: object) -> object:
    """Treść od użytkowników trafia do arkusza – neutralizujemy formuły (CSV injection)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _csv_rows(result: CheckResponse) -> list[dict]:
    base = {
        "check_id": result.id,
        "created_at": result.created_at.isoformat(),
        "channel": result.channel,
        "status": result.status.value,
        "error_code": result.error_code or "",
        "input_kind": result.input.kind,
        "input_text": result.input.text,
        "input_url": result.input.url or "",
        "moderator_case_id": result.moderator_case.case_id or "",
        "summary_verdict": result.verdict.value if result.verdict else "",
        "confidence": result.confidence if result.confidence is not None else "",
        "keywords": "; ".join(result.keywords),
        "main_topic": result.main_topic,
        "factcheck_count": len(result.fact_check_results),
        "duration_ms": result.meta.duration_ms,
        "tokens_in": result.meta.tokens_in,
        "tokens_out": result.meta.tokens_out,
        "bielik_tokens_in": result.meta.bielik_tokens_in,
        "bielik_tokens_out": result.meta.bielik_tokens_out,
        "cost_usd": result.meta.cost_usd if result.meta.cost_usd is not None else "",
    }
    if not result.claims:
        return [base]
    return [
        base
        | {
            "claim_id": claim.id,
            "claim_text": claim.text,
            "verdict": claim.verdict.value,
            "strength_level": claim.strength.level,
            "strength_score": claim.strength.score,
            "conflict": claim.conflict,
            "risk": claim.risk,
            "source_urls": " ".join(dict.fromkeys(e.source.url for e in claim.evidence)),
        }
        for claim in result.claims
    ]


@router.get("/export", summary="Eksport przebiegu sprawdzeń (CSV lub JSON)")
def export(request: Request, format: Literal["csv", "json"] = "csv") -> Response:
    results = _store(request).all_results()
    if format == "json":
        body = json.dumps([json.loads(r.model_dump_json()) for r in results], ensure_ascii=False, indent=2)
        media_type = "application/json"
    else:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS, restval="")
        writer.writeheader()
        for result in results:
            for row in _csv_rows(result):
                writer.writerow({k: _csv_safe(v) for k, v in row.items()})
        body, media_type = buffer.getvalue(), "text/csv; charset=utf-8"
    return Response(
        body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="prawdowid-export.{format}"'},
    )


@router.get("/export/stix", summary="Eksport sprawdzeń jako bundle STIX 2.1 (z mapowaniem DISARM)")
def export_stix(request: Request, check_id: str | None = None) -> Response:
    store = _store(request)
    results = [store.get_check(check_id)] if check_id else store.all_results()
    results = [result for result in results if result is not None]
    if not results:
        raise HTTPException(404, "Brak sprawdzeń do eksportu.")
    body = stix_bundle(results)
    return Response(
        body,
        media_type="application/stix+json",
        headers={"Content-Disposition": 'attachment; filename="prawdowid-stix.json"'},
    )


class IngestRequest(BaseModel):
    sources: list[str] | None = None
    max_per_source: int | None = Field(default=None, ge=1, le=50)


async def _run_ingest_task(app, only: list[str] | None, max_per_source: int | None) -> None:
    try:
        reports = await run_ingest(
            app.state.settings,
            app.state.corpus,
            getattr(app.state, "embedder", None),
            only=only,
            max_per_source=max_per_source,
        )
        app.state.last_ingest = [report.as_dict() for report in reports]
        app.state.context.reload()
    except Exception as exc:  # nie zostawiamy flagi „running” na zawsze
        app.state.last_ingest = [{"status": "error", "detail": str(exc)[:300]}]
    finally:
        app.state.ingest_running = False


@router.post("/corpus/ingest", status_code=202, summary="Uruchom ingest źródeł w tle")
async def trigger_ingest(
    request: Request,
    background: BackgroundTasks,
    payload: IngestRequest | None = None,
) -> dict:
    app = request.app
    if getattr(app.state, "ingest_running", False):
        raise HTTPException(status_code=409, detail="Ingest już trwa.")
    only = payload.sources if payload else None
    try:
        specs = get_sources(only)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    app.state.ingest_running = True
    background.add_task(
        _run_ingest_task,
        app,
        only,
        payload.max_per_source if payload else None,
    )
    return {
        "status": "started",
        "sources": [spec.key for spec in specs],
        "max_per_source": (payload.max_per_source if payload else None)
        or app.state.settings.ingest_max_per_source,
    }


@router.get("/corpus/stats", summary="Stan korpusu i ostatnie przebiegi ingestu")
def corpus_stats(request: Request) -> dict:
    app = request.app
    corpus = getattr(app.state, "corpus", None)
    if corpus is None:
        raise HTTPException(status_code=503, detail="Korpus nie jest skonfigurowany.")
    return {
        **corpus.stats(),
        "by_source": corpus.source_summary(),
        "running": getattr(app.state, "ingest_running", False),
        "last_ingest": getattr(app.state, "last_ingest", None),
        "runs": corpus.recent_ingest_runs(20),
    }
