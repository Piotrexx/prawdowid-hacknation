import csv
import io
import json
import statistics
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, func

from app.api.deps import require_admin
from app.schemas import CheckStatus
from app.store.db import Store, CheckRow

router = APIRouter(prefix="/admin", tags=["moderator"], dependencies=[Depends(require_admin)])

_CSV_COLUMNS = [
    "check_id", "created_at", "channel", "status", "error_code", "input_url", "input_title",
    "verdict", "confidence", "keywords", "main_topic", "factcheck_count",
    "duration_ms", "tokens_in", "tokens_out", "bielik_tokens_in", "bielik_tokens_out", "cost_usd",
]


def _store(request: Request) -> Store:
    return request.app.state.store


@router.get("/metrics")
def metrics(request: Request) -> dict:
    store = _store(request)
    with store._session() as db:
        total = db.scalar(select(func.count()).select_from(CheckRow)) or 0
        by_status = dict(db.execute(select(CheckRow.status, func.count()).group_by(CheckRow.status)).all())
        by_channel = dict(db.execute(select(CheckRow.channel, func.count()).group_by(CheckRow.channel)).all())
        errors = dict(db.execute(select(CheckRow.error_code, func.count()).where(CheckRow.error_code.isnot(None)).group_by(CheckRow.error_code)).all())
        verdicts = {}
        factcheck_counts = []
        durations = []
        for row in db.scalars(select(CheckRow.result).where(CheckRow.status == CheckStatus.COMPLETED.value)):
            if row.get("verdict"):
                v = row["verdict"]
                verdicts[v] = verdicts.get(v, 0) + 1
            factcheck_counts.append(len(row.get("fact_check_results", [])))
            durations.append(row.get("meta", {}).get("duration_ms", 0))
        return {
            "checks_total": total,
            "by_status": by_status,
            "by_channel": by_channel,
            "by_verdict": verdicts,
            "avg_factchecks": round(sum(factcheck_counts) / len(factcheck_counts), 2) if factcheck_counts else 0,
            "median_duration_ms": int(statistics.median(durations)) if durations else None,
            "errors": errors,
        }


@router.get("/checks")
def list_checks(request: Request, limit: Annotated[int, Query(ge=1, le=500)] = 50) -> list[dict]:
    store = _store(request)
    results = []
    with store._session() as db:
        rows = db.scalars(select(CheckRow).order_by(CheckRow.created_at.desc()).limit(limit))
        for row in rows:
            r = row.result
            results.append({
                "id": row.id,
                "created_at": row.created_at.isoformat(),
                "channel": row.channel,
                "status": row.status,
                "url": r.get("input", {}).get("url"),
                "title": r.get("input", {}).get("title"),
                "verdict": r.get("verdict"),
                "confidence": r.get("confidence"),
                "keywords": r.get("keywords", []),
                "factcheck_count": len(r.get("fact_check_results", [])),
                "duration_ms": r.get("meta", {}).get("duration_ms"),
            })
    return results


def _csv_safe(value: object) -> object:
    """Treść od użytkowników trafia do arkusza – neutralizujemy formuły (CSV injection)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@router.get("/export", summary="Eksport przebiegu sprawdzeń (CSV lub JSON)")
def export(request: Request, format: Literal["csv", "json"] = "csv") -> Response:
    store = _store(request)
    with store._session() as db:
        rows = db.scalars(select(CheckRow).order_by(CheckRow.created_at.desc()))
        if format == "json":
            body = json.dumps([r.result for r in rows], ensure_ascii=False, indent=2)
            media_type = "application/json"
        else:
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS, restval="")
            writer.writeheader()
            for row in rows:
                r = row.result
                writer.writerow({
                    k: _csv_safe(v) for k, v in {
                        "check_id": row.id,
                        "created_at": row.created_at.isoformat(),
                        "channel": row.channel,
                        "status": row.status,
                        "error_code": row.error_code or "",
                        "input_url": r.get("input", {}).get("url", ""),
                        "input_title": r.get("input", {}).get("title", ""),
                        "verdict": r.get("verdict", ""),
                        "confidence": r.get("confidence", ""),
                        "keywords": "; ".join(r.get("keywords", [])),
                        "main_topic": r.get("main_topic", ""),
                        "factcheck_count": len(r.get("fact_check_results", [])),
                        "duration_ms": r.get("meta", {}).get("duration_ms", ""),
                        "tokens_in": r.get("meta", {}).get("tokens_in", ""),
                        "tokens_out": r.get("meta", {}).get("tokens_out", ""),
                        "bielik_tokens_in": r.get("meta", {}).get("bielik_tokens_in", ""),
                        "bielik_tokens_out": r.get("meta", {}).get("bielik_tokens_out", ""),
                        "cost_usd": r.get("meta", {}).get("cost_usd", ""),
                    }.items()
                })
            body, media_type = buffer.getvalue(), "text/csv; charset=utf-8"
    return Response(
        body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="prawdowid-export.{format}"'},
    )