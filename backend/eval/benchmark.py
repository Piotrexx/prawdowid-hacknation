"""Prosty pomiar czasu odpowiedzi (mediana, p95) dla tekstu/URL.

Uruchamianie na działającej instancji:

    PRAWDOWID_URL=http://localhost:8000 \
    PRAWDOWID_SESSION=sesja-benchmark-1 \
    PRAWDOWID_CONSENT=2026-11-21 \
    uv run python -m eval.benchmark --n 10 --text "..."

Domyślnie wysyła krótkie zapytanie tekstowe. Wymaga aktywnej zgody (POST /consent).
"""

from __future__ import annotations

import argparse
import os
import statistics
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("PRAWDOWID_URL", "http://localhost:8000"))
    parser.add_argument("--session", default=os.getenv("PRAWDOWID_SESSION", "sesja-benchmark-1"))
    parser.add_argument("--consent", default=os.getenv("PRAWDOWID_CONSENT", "2026-11-21"))
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--text", default="Czy wiadomo, ile osób mieszka w Warszawie?")
    args = parser.parse_args()

    base = args.url.rstrip("/") + "/api/v1"
    client = httpx.Client(timeout=180.0)
    client.cookies.set("prawdowid_session", args.session)
    client.cookies.set("prawdowid_privacy_consent", args.consent)
    client.post(
        f"{base}/consent",
        json={"session_id": args.session, "policy_version": args.consent, "accepted": True},
    )
    durations: list[int] = []
    costs: list[float] = []
    for index in range(args.n):
        started = time.perf_counter()
        response = client.post(f"{base}/checks", json={"text": f"{args.text} (próba {index + 1})"})
        elapsed = int((time.perf_counter() - started) * 1000)
        response.raise_for_status()
        result = response.json()
        durations.append(elapsed)
        if result.get("meta", {}).get("cost_usd") is not None:
            costs.append(float(result["meta"]["cost_usd"]))
        print(f"{index + 1}/{args.n}: {elapsed} ms, status={result['status']}")
    ordered = sorted(durations)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(f"mediana={int(statistics.median(ordered))} ms, p95={p95} ms, n={len(ordered)}")
    if costs:
        print(f"koszt łącznie=${sum(costs):.4f}, koszt 1000 zapytań=${sum(costs) / len(costs) * 1000:.2f}")


if __name__ == "__main__":
    main()
