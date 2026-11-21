"""Pomiar mierników z sekcji 6 wymagań na prawdziwym korpusie i prawdziwym modelu.

    uv run python -m eval.run_eval [--cases eval/cases.jsonl] [--out eval/out]

Każde uruchomienie wysyła zapytania do skonfigurowanego modelu (koszt!). Zestaw jury
(≥30 przypadków) wystarczy zapisać w tym samym formacie JSONL i wskazać przez --cases.
"""

import argparse
import asyncio
import csv
import json
import os
import statistics
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI

from app.config import get_settings
from app.core.pipeline import Submission
from app.llm.factory import build_provider
from app.main import build_state, load_embedder
from app.schemas import CheckResponse, CheckStatus, Verdict

_CATEGORICAL = {Verdict.CONFIRMED, Verdict.FALSE, Verdict.MISLEADING}


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
    """Przypadki testowe zawierają jedno twierdzenie, więc porównujemy pierwszy werdykt."""
    if result.status != CheckStatus.COMPLETED or not result.claims:
        return f"status:{result.status.value}"
    return result.claims[0].verdict.value


def fingerprint(result: CheckResponse) -> list:
    return [(c.verdict.value, sorted(e.source.url for e in c.evidence)) for c in result.claims]


async def run(cases_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Osobna baza (albo baza testowa) – wyniki nie zależą od wcześniejszych sprawdzeń.
    database_url = os.getenv("EVAL_DATABASE_URL") or os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://prawdowid:prawdowid@localhost:5432/prawdowid_test",
    )
    settings = get_settings().model_copy(update={"database_url": database_url})
    app = FastAPI()
    build_state(app, settings, provider=build_provider(settings), embedder=load_embedder(settings))
    service = app.state.service
    cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    rows, results = [], {}
    for case in cases:
        result = await service.check(Submission.from_message("web", f"eval-{case['id']}", case["text"]))
        results[case["id"]] = result
        expected = case.get("expected_verdict") or f"status:{case.get('expected_status')}"
        row = {
            "id": case["id"],
            "scenario": case.get("scenario", ""),
            "expected": expected,
            "predicted": predicted(result),
            "correct": predicted(result) == expected,
            "error_code": result.error_code or "",
            "duration_ms": result.meta.duration_ms,
            "cost_usd": result.meta.cost_usd,
            "injection_flagged": any(w.code == "injection_detected" for w in result.warnings),
            "case_id": result.moderator_case.case_id,
        }
        if case.get("consistency"):
            other = await service.check(Submission.from_message("web", f"eval-repeat-{case['id']}", case["text"]))
            # Dwa identyczne błędy techniczne to nie jest spójność merytoryczna.
            row["repeat_consistent"] = (
                result.status == other.status == CheckStatus.COMPLETED and fingerprint(other) == fingerprint(result)
            )
        if case.get("same_case_as"):
            row["case_deduplicated"] = row["case_id"] is not None and row["case_id"] == results[case["same_case_as"]].moderator_case.case_id
        rows.append(row)
        print(f"{row['id']:5} {'OK ' if row['correct'] else 'ŹLE'} oczekiwano={expected} wynik={row['predicted']} ({row['duration_ms']} ms)")

    technical = [r for r in rows if r["predicted"] == "status:error"]
    verdict_rows = [r for r in rows if not r["expected"].startswith("status:")]
    abstain = [r for r in verdict_rows if r["expected"] == Verdict.INSUFFICIENT.value]
    attacks = {c["id"] for c in cases if c.get("attack")}
    attack_rows = [r for r in rows if r["id"] in attacks]
    categorical = [c for r in results.values() for c in r.claims if c.verdict in _CATEGORICAL]
    consistency = [r["repeat_consistent"] for r in rows if "repeat_consistent" in r]
    dedup = [r["case_deduplicated"] for r in rows if "case_deduplicated" in r]
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    by_scenario = defaultdict(list)
    for r in rows:
        by_scenario[r["scenario"]].append(r["correct"])

    report = {
        "cases": len(rows),
        "model": f"{settings.llm_provider}:{settings.llm_model}",
        "corpus_version": app.state.retriever.version,
        "retrieval_mode": app.state.retriever.mode,
        "technical_errors": len(technical),
        "verdict_macro_f1": macro_f1([(r["expected"], r["predicted"]) for r in verdict_rows]),
        "accuracy": ratio(sum(r["correct"] for r in rows), len(rows)),
        "citation_coverage": ratio(sum(1 for c in categorical if c.evidence), len(categorical)),
        "abstention_accuracy": ratio(sum(r["correct"] for r in abstain), len(abstain)),
        # Atak jest odparty, gdy werdykt się nie zmienił i zdarzenie zostało odnotowane.
        "injection_resistance": ratio(sum(r["correct"] and r["injection_flagged"] for r in attack_rows), len(attack_rows)),
        "repeat_consistency": ratio(sum(consistency), len(consistency)),
        "case_deduplication": ratio(sum(dedup), len(dedup)),
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
    # Poprawność cytowań wymaga oceny człowieka – eksportujemy pary (twierdzenie, cytat) do ręcznego przeglądu.
    with (out_dir / "citations_to_review.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["case_id", "claim", "verdict", "stance", "quote", "source_url", "supports_claim (tak/nie)"])
        for case_id, result in results.items():
            for claim in result.claims:
                for evidence in claim.evidence:
                    writer.writerow([case_id, claim.text, claim.verdict.value, evidence.stance, evidence.quote, evidence.source.url, ""])
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path(__file__).parent / "cases.jsonl")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "out")
    args = parser.parse_args()
    report = asyncio.run(run(args.cases, args.out))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["technical_errors"]:
        print(f"\nUWAGA: {report['technical_errors']} przypadków zakończyło się błędem technicznym (np. brak klucza API) – mierniki nie są miarodajne.")


if __name__ == "__main__":
    main()
