"""Dane demonstracyjne mapy wydarzeń.

Uruchom z katalogu backend:
    uv run python scripts/seed_demo_graph.py --reset

Skrypt usuwa wyłącznie poprzednie dane demo (sesja demo-graph-0001),
nie rusza prawdziwych zgłoszeń ani reszty grafu.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Uruchamiane jako `python scripts/...` – dodaj katalog backendu do importów.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings
from app.schemas import (
    VERDICT_LABELS,
    CheckResponse,
    CheckStatus,
    ClaimResult,
    InputInfo,
    Strength,
    Verdict,
)
from app.store.db import Store

DEMO_SESSION = "demo-graph-0001"
NOW = datetime.now(UTC)

GIS_ANCHOR = {
    "incident_id": "gis-ostrzezenia-publiczne",
    "title": "Ostrzeżenia publiczne GIS",
    "publisher": "Główny Inspektorat Sanitarny",
    "url": "https://www.gov.pl/web/gis/ostrzezenia-publiczne",
    "date": "2026-11-20",
    "note": "Publiczny katalog ostrzeżeń o żywności.",
}
CERT_ANCHOR = {
    "incident_id": "cert-polska",
    "title": "CERT Polska – zgłaszanie incydentów",
    "publisher": "CERT Polska",
    "url": "https://cert.pl/",
    "date": "2026-11-20",
    "note": "Publiczne ostrzeżenia o kampaniach phishingowych.",
}


def demo_check(
    text: str,
    claim_text: str,
    *,
    verdict: Verdict,
    topic: str,
    keywords: list[str],
    age_hours: int,
) -> CheckResponse:
    return CheckResponse(
        id=uuid.uuid4().hex,
        created_at=NOW - timedelta(hours=age_hours),
        channel="web",
        status=CheckStatus.COMPLETED,
        input=InputInfo(kind="text", text=text),
        summary=claim_text,
        main_topic=topic,
        keywords=keywords,
        claims=[
            ClaimResult(
                id="c1",
                text=claim_text,
                verdict=verdict,
                verdict_label=VERDICT_LABELS[verdict],
                justification="Dane demonstracyjne mapy wydarzeń.",
                strength=Strength(level="umiarkowana", score=0.55),
                risk="standard",
            )
        ],
        limitations=["Dane demonstracyjne — nie są wynikiem rzeczywistej weryfikacji."],
    )


def new_event(
    store: Store,
    check: CheckResponse,
    *,
    keywords: list[str],
    topic: str,
    anchors: list[dict],
    score: float,
    reason: str,
):
    claim = check.claims[0]
    return store.create_event_with_member(
        title=claim.text,
        topic=topic,
        summary=claim.text,
        keywords=keywords,
        risk=claim.risk,
        check_id=check.id,
        claim_id=claim.id,
        claim_text=claim.text,
        verdict=claim.verdict.value,
        score=score,
        reason=reason,
        status="accepted",
        source="manual",
        embedding=None,
        embedding_model="demo",
        anchors=anchors,
    )


def add_member(
    store: Store,
    event_id: str,
    check: CheckResponse,
    *,
    keywords: list[str],
    topic: str,
    anchors: list[dict],
    score: float,
    status: str = "accepted",
    reason: str = "Dane demonstracyjne: ta sama sytuacja.",
):
    claim = check.claims[0]
    return store.attach_event_member(
        event_id,
        check_id=check.id,
        claim_id=claim.id,
        claim_text=claim.text,
        verdict=claim.verdict.value,
        risk=claim.risk,
        score=score,
        reason=reason,
        status=status,
        source="manual",
        embedding=None,
        keywords=keywords,
        topic=topic,
        anchors=anchors,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Usuń poprzednie dane demo.")
    args = parser.parse_args()

    settings = get_settings()
    store = Store(settings.database_url)
    if args.reset:
        store.delete_session(DEMO_SESSION)

    # --- A: kampania smishingowa podszywająca się pod Pocztę Polską ---
    a_topic = "Oszustwa smishingowe podszywające się pod Pocztę Polską"
    a_keywords = ["Poczta Polska", "smishing", "dopłata 3 euro", "fałszywe SMS"]
    a1 = demo_check(
        "Poczta Polska ostrzega przed SMS-ami o dopłacie 3 euro do przesyłki.",
        "Poczta Polska ostrzega przed SMS-ami o dopłacie 3 euro do przesyłki.",
        verdict=Verdict.CONFIRMED,
        topic=a_topic,
        keywords=a_keywords,
        age_hours=30,
    )
    a2 = demo_check(
        "CERT Poczta Polska: fałszywe SMS-y z linkiem do płatności za paczkę.",
        "CERT Poczta Polska ostrzega przed fałszywymi SMS-ami z linkiem do płatności.",
        verdict=Verdict.CONFIRMED,
        topic=a_topic,
        keywords=a_keywords,
        age_hours=26,
    )
    a3 = demo_check(
        "Oszuści podszywają się pod Pocztę Polską i żądają dopłaty celnej.",
        "Oszuści podszywają się pod Pocztę Polską i żądają dopłaty celnej.",
        verdict=Verdict.CONFIRMED,
        topic=a_topic,
        keywords=a_keywords,
        age_hours=22,
    )
    for check in (a1, a2, a3):
        store.save_check(check, DEMO_SESSION, None)

    event_a = new_event(
        store,
        a1,
        keywords=a_keywords,
        topic=a_topic,
        anchors=[CERT_ANCHOR],
        score=0.96,
        reason="Dane demonstracyjne: ta sama kampania smishingowa.",
    )
    add_member(
        store, event_a.id, a2, keywords=a_keywords, topic=a_topic, anchors=[CERT_ANCHOR], score=0.88
    )
    add_member(
        store, event_a.id, a3, keywords=a_keywords, topic=a_topic, anchors=[CERT_ANCHOR], score=0.81
    )

    # --- A2: dementi, które trafia do moderatora jako sprzeczność ---
    a4 = demo_check(
        "Poczta Polska dementuje, że wysyła SMS-y o dopłacie 3 euro.",
        "Poczta Polska nie wysyła SMS-ów o dopłacie 3 euro.",
        verdict=Verdict.FALSE,
        topic="Dementi Poczty Polskiej",
        keywords=["Poczta Polska", "dementi", "smishing"],
        age_hours=12,
    )
    store.save_check(a4, DEMO_SESSION, None)
    event_a2 = new_event(
        store,
        a4,
        keywords=["Poczta Polska", "dementi", "smishing"],
        topic="Dementi Poczty Polskiej",
        anchors=[],
        score=0.7,
        reason="Osobne wydarzenie: dementi.",
    )
    store.add_event_link(
        src_event_id=event_a.id,
        dst_event_id=event_a2.id,
        relation="contradiction",
        score=0.86,
        reason="Dwa opisy tej samej sprawy: ostrzeżenie i dementi.",
        evidence={"claim": a4.claims[0].text, "event": a1.claims[0].text},
        model="demo",
        status="proposed",
        origin_check_id=a4.id,
    )

    # --- B: Listeria w boczku ---
    b_topic = "Wycofanie boczku Bell Polska z powodu Listerii"
    b_keywords = ["GIS", "Listeria", "boczek", "partia 40911"]
    b1 = demo_check(
        "GIS wycofuje partię 40911 boczku wędzonego Bell Polska z powodu Listerii.",
        "GIS wycofuje partię 40911 boczku wędzonego Bell Polska z powodu Listerii.",
        verdict=Verdict.CONFIRMED,
        topic=b_topic,
        keywords=b_keywords,
        age_hours=48,
    )
    b2 = demo_check(
        "Inspekcja Weterynaryjna potwierdza wycofanie partii 40911.",
        "Inspekcja Weterynaryjna potwierdza wycofanie partii 40911 boczku.",
        verdict=Verdict.CONFIRMED,
        topic=b_topic,
        keywords=b_keywords,
        age_hours=44,
    )
    b3 = demo_check(
        "Selgros informuje klientów o zwrocie boczku Bell Polska.",
        "Selgros informuje klientów o zwrocie boczku Bell Polska z partii 40911.",
        verdict=Verdict.CONFIRMED,
        topic=b_topic,
        keywords=b_keywords,
        age_hours=40,
    )
    for check in (b1, b2, b3):
        store.save_check(check, DEMO_SESSION, None)

    event_b = new_event(
        store,
        b1,
        keywords=b_keywords,
        topic=b_topic,
        anchors=[GIS_ANCHOR],
        score=0.95,
        reason="Dane demonstracyjne: to samo wycofanie produktu.",
    )
    add_member(
        store, event_b.id, b2, keywords=b_keywords, topic=b_topic, anchors=[GIS_ANCHOR], score=0.9
    )
    add_member(
        store, event_b.id, b3, keywords=b_keywords, topic=b_topic, anchors=[GIS_ANCHOR], score=0.84
    )

    # --- C: pleśń w wodzie Jurajska ---
    c_topic = "Wycofanie wody Jurajska Sport z powodu pleśni"
    c_keywords = ["GIS", "Jurajska Sport", "pleśń", "wycofanie"]
    c1 = demo_check(
        "GIS wycofuje wodę Jurajska Sport 700 ml z powodu pleśni.",
        "GIS wycofuje wodę Jurajska Sport 700 ml z powodu pleśni.",
        verdict=Verdict.CONFIRMED,
        topic=c_topic,
        keywords=c_keywords,
        age_hours=20,
    )
    c2 = demo_check(
        "Państwowa Inspekcja Sanitarna ostrzega przed wodą Jurajska Sport.",
        "Państwowa Inspekcja Sanitarna ostrzega przed wodą Jurajska Sport 700 ml.",
        verdict=Verdict.CONFIRMED,
        topic=c_topic,
        keywords=c_keywords,
        age_hours=18,
    )
    c3 = demo_check(
        "Producent informuje o wycofaniu partii wody Jurajska Sport.",
        "Producent informuje o wycofaniu partii wody Jurajska Sport 700 ml.",
        verdict=Verdict.CONFIRMED,
        topic=c_topic,
        keywords=c_keywords,
        age_hours=16,
    )
    for check in (c1, c2, c3):
        store.save_check(check, DEMO_SESSION, None)

    event_c = new_event(
        store,
        c1,
        keywords=c_keywords,
        topic=c_topic,
        anchors=[GIS_ANCHOR],
        score=0.95,
        reason="Dane demonstracyjne: to samo wycofanie produktu.",
    )
    add_member(
        store, event_c.id, c2, keywords=c_keywords, topic=c_topic, anchors=[GIS_ANCHOR], score=0.89
    )
    add_member(
        store, event_c.id, c3, keywords=c_keywords, topic=c_topic, anchors=[GIS_ANCHOR], score=0.83
    )

    store.add_event_link(
        src_event_id=event_b.id,
        dst_event_id=event_c.id,
        relation="related_topic",
        score=0.79,
        reason="Oba wydarzenia to ostrzeżenia GIS o wycofaniu produktu.",
        evidence={"claim": c1.claims[0].text, "event": b1.claims[0].text},
        model="demo",
        status="accepted",
        origin_check_id=c1.id,
    )

    graph = store.event_graph(window_days=365, limit=100)
    public = store.public_event_graph(
        min_members=settings.event_public_min_members,
        window_days=365,
        limit=100,
    )
    print("Gotowe. Dane demonstracyjne mapy wydarzeń:")
    print(f"  wydarzenia w panelu: {len([n for n in graph.nodes if n.kind == 'event'])}")
    print(f"  wydarzenia publiczne: {len([n for n in public.nodes if n.kind == 'event'])}")
    print(f"  relacje: {len([e for e in graph.edges if e.relation != 'anchor'])}")
    print("  panel:  http://localhost:3000/moderator -> Mapa wydarzeń")
    print("  public: http://localhost:3000/mapa")
    print(f"  ID: A={event_a.id}, B={event_b.id}, C={event_c.id}, A2={event_a2.id}")


if __name__ == "__main__":
    main()
