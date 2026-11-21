"""Pomiar jakości nowego pipeline'u fake news na prawdziwym modelu.

    uv run python -m eval.run_eval [--cases eval/cases.jsonl] [--out eval/out]

Każde uruchomienie wysyła zapytania do skonfigurowanego modelu (koszt!).
Zestaw przypadków testowych w formacie JSONL:
{
  "id": "case-1",
  "url": "https://example.org/article",
  "expected_verdict": "fake_news",
  "scenario": "fake_news_detection"
}
"""

import argparse
import asyncio
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI

from app.config import get_settings
from app.core.pipeline import VerificationService
from app.llm.factory import build_provider
from app.main import build_state
from app.schemas import CheckRequest, CheckResponse, CheckStatus, VerdictLabel
from app.store.db import Store


def macro_f1(pairs: list[tuple[str, str]]) -> float | None:
    """Macro-F1 po klasach, które występują w oczekiwanych wynikach."""
    labels = {expected for expected, _ in pairs}
    scores = []
    for label in labels:
        tp = sum(1 for e, p in pairs if e == label and p == label)
        fp = sum(1 for e, p in pairs if e != label and p == label)
        fn = sum(1 for e, p in pairs if e == label and p != label)
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return round(statistics.mean(scores), 3) if scores else None


def ratio(hits: int, total: int) -> float | None:
    return round(hits / total, 3) if total else None


def predicted(result: CheckResponse) -> str:
    """Zwraca werdykt lub status błędu."""
    if result.status != CheckStatus.COMPLETED or result.verdict is None:
        return f"status:{result.status.value}"
    return result.verdict.value


async def run(cases_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    database = out_dir / "eval.db"
    database.unlink(missing_ok=True)
    settings = get_settings().model_copy(update={"database_url": f"sqlite:///{database}"})
    app = FastAPI()
    build_state(app, settings, provider=build_provider(settings))
    service: VerificationService = app.state.service

    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    rows, results = [], {}
    for case in cases:
        request = CheckRequest(url=case["url"], session_id=f"eval-{case['id']}")
        result = await service.check(request)
        results[case["id"]] = result
        expected = case.get("expected_verdict") or f"status:{case.get('expected_status', 'completed')}"
        row = {
            "id": case["id"],
            "scenario": case.get("scenario", ""),
            "expected": expected,
            "predicted": predicted(result),
            "correct": predicted(result) == expected,
            "error_code": result.error_code or "",
            "duration_ms": result.meta.duration_ms,
            "cost_usd": result.meta.cost_usd,
            "confidence": result.confidence or 0.0,
        }
        if case.get("consistency"):
            other = await service.check(CheckRequest(url=case["url"], session_id=f"eval-repeat-{case['id']}"))
            row["repeat_consistent"] = (
                result.status == other.status == CheckStatus.COMPLETED
                and result.verdict == other.verdict
            )
        rows.append(row)
        print(f"{row['id']:5} {'OK ' if row['correct'] else 'ŻLE'} oczekiwano={expected} wynik={row['predicted']} ({row['duration_ms']} ms)")

    technical = [r for r in rows if r["predicted"] == "status:error"]
    verdict_rows = [r for r in rows if not r["expected"].startswith("status:")]
    attack_rows = [r for r in rows if "attack" in cases[rows.index(r)]]
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    by_scenario = defaultdict(list)
    for r in rows:
        by_scenario[r["scenario"]].append(r["correct"])

    report = {
        "cases": len(rows),
        "model": f"{settings.llm_provider}:{settings.llm_model}",
        "bielik_model": settings.bielik_model,
        "technical_errors": len(technical),
        "verdict_macro_f1": macro_f1([(r["expected"], r["predicted"]) for r in verdict_rows]),
        "accuracy": ratio(sum(r["correct"] for r in rows), len(rows)),
        "abstention_accuracy": None,  # Nowy pipeline nie ma INSUFFICIENT
        "repeat_consistency": ratio(
            sum(r.get("repeat_consistent", False) for r in rows if "repeat_consistent" in r),
            len([r for r in rows if "repeat_consistent" in r])
        ),
        "median_duration_ms": int(statistics.median(r["duration_ms"] for r in rows)) if rows else None,
        "cost_usd_total": round(sum(costs), 4) if costs else None,
        "cost_usd_per_100": round(sum(costs) / len(costs) * 100, 2) if costs else None,
        "accuracy_by_scenario": {k: ratio(sum(v), len(v)) for k, v in sorted(by_scenario.items())},
    }
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "results.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=sorted({k for r in rows for k in r}), restval="")
        writer.writeheader()
        writer.writerows(rows)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path(__file__).parent / "cases.jsonl")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    args = parser.parse_args()
    report = asyncio.run(run(args.cases, args.out))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["technical_errors"]:
        print(f"\nUWAGA: {report['technical_errors']} przypadków zakończyło się błędem technicznym – mierniki nie są miarodajne.")


if __name__ == "__main__":
    main()