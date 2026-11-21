import csv
import io
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.deps import require_admin
from app.schemas import (
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
    "check_id", "created_at", "channel", "status", "error_code", "input_kind", "input_text",
    "claim_id", "claim_text", "verdict", "strength_level", "strength_score", "conflict", "risk",
    "source_urls", "moderator_case_id", "duration_ms", "tokens_in", "tokens_out", "cost_usd",
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
        "moderator_case_id": result.moderator_case.case_id or "",
        "duration_ms": result.meta.duration_ms,
        "tokens_in": result.meta.tokens_in,
        "tokens_out": result.meta.tokens_out,
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
