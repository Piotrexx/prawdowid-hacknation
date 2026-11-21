"""Deterministyczna warstwa decyzji.

Model tylko PROPONUJE werdykt i wskazuje cytaty. Tutaj sprawdzamy, czy każdy cytat
naprawdę występuje w źródle, i dopiero z potwierdzonych cytatów wynika werdykt.
Dzięki temu etykieta wygenerowana przez model nigdy nie jest jedyną podstawą oceny,
a każda rozstrzygająca odpowiedź ma co najmniej jeden zweryfikowany dowód.
"""

import re
from datetime import date

from app.catalog import Document
from app.core.prompts import ClaimAssessment
from app.retrieval.index import Hit
from app.schemas import (
    VERDICT_LABELS,
    ClaimResult,
    Evidence,
    SourceRef,
    Strength,
    StrengthFactor,
    Verdict,
)
from app.textutil import collapse_ws, normalize_for_match

_MIN_QUOTE_CHARS = 12
_CONTEXT_ONLY_TIER = 3
_PASSAGE_REF_RE = re.compile(r"\s*\[P(\d+)\]")
_PASSAGE_ID_RE = re.compile(r"(\d+)")
_STANCE_ORDER = {"supports": 0, "refutes": 1, "context": 2}

_DECISIVE_STANCES: dict[Verdict, tuple[str, ...]] = {
    Verdict.CONFIRMED: ("supports",),
    Verdict.FALSE: ("refutes",),
    Verdict.MISLEADING: ("refutes", "context"),
}
_OPPOSING_STANCE = {Verdict.CONFIRMED: "refutes", Verdict.FALSE: "supports"}

_OVERRIDE_TEXT = {
    "conflict": "Wiarygodne źródła podają rozbieżne informacje, dlatego nie rozstrzygam. Zobacz materiały poniżej i oceń je samodzielnie.",
    "no_quote": "Nie znalazłem w źródłach fragmentu, który jednoznacznie potwierdza albo obala to twierdzenie.",
}


def source_ref(doc: Document, source_name: str) -> SourceRef:
    return SourceRef(
        doc_id=doc.id,
        title=doc.title,
        publisher=doc.publisher,
        url=doc.url,
        published_at=doc.published_at,
        retrieved_at=doc.retrieved_at,
        source_type=doc.source_type,
        source_name=source_name,
        license=doc.license,
        claim_reviewed=doc.claim_reviewed,
        rating=doc.rating,
    )


def validated_evidence(
    assessment: ClaimAssessment, hits: list[Hit], source_names: dict[str, str], today: date, archival_days: int
) -> tuple[list[Evidence], dict[int, str], int]:
    """Zostawia tylko oceny z cytatem obecnym w źródle. Zwraca też mapę numer fragmentu → id dowodu
    oraz liczbę odrzuconych cytatów (miernik jakości)."""
    accepted: list[tuple[int, str, str]] = []
    seen: set[tuple[str, str]] = set()
    rejected = 0
    for judgement in assessment.judgements:
        if judgement.stance == "irrelevant":
            continue
        match = _PASSAGE_ID_RE.search(judgement.passage_id)
        number = int(match.group(1)) if match else 0
        quote = collapse_ws(judgement.quote).strip("\"'„”“ ")
        if not 1 <= number <= len(hits) or len(quote) < _MIN_QUOTE_CHARS:
            rejected += 1
            continue
        passage = hits[number - 1].passage
        haystack = normalize_for_match(f"{passage.doc.title}\n{passage.text}")
        if normalize_for_match(quote) not in haystack:
            rejected += 1
            continue
        # Media (poziom 3) mogą dać kontekst, ale nie rozstrzygają – tak stanowi katalog źródeł.
        stance = "context" if passage.doc.tier >= _CONTEXT_ONLY_TIER else judgement.stance
        if (passage.doc.id, quote) not in seen:
            seen.add((passage.doc.id, quote))
            accepted.append((number, stance, quote))

    accepted.sort(key=lambda item: _STANCE_ORDER[item[1]])
    evidence, ref_map = [], {}
    for position, (number, stance, quote) in enumerate(accepted, 1):
        doc = hits[number - 1].passage.doc
        ref_map.setdefault(number, f"E{position}")
        evidence.append(
            Evidence(
                id=f"E{position}",
                stance=stance,
                quote=quote,
                source=source_ref(doc, source_names.get(doc.source_id, doc.publisher)),
                archival=doc.published_at is not None and (today - doc.published_at).days > archival_days,
            )
        )
    return evidence, ref_map, rejected


def resolve_verdict(proposed: Verdict, stances: set[str]) -> tuple[Verdict, bool, str | None]:
    """Zwraca (werdykt, czy źródła są sprzeczne, powód korekty propozycji modelu)."""
    supports, refutes, context = (s in stances for s in ("supports", "refutes", "context"))
    conflict = supports and refutes
    if proposed in (Verdict.NOT_VERIFIABLE, Verdict.INSUFFICIENT):
        return proposed, conflict, None
    if conflict:
        # Częściowo prawda, częściowo fałsz to klasyczne „wprowadzające w błąd”;
        # w pozostałych przypadkach sprzeczne źródła oznaczają wstrzymanie się od oceny.
        if proposed == Verdict.MISLEADING:
            return proposed, False, None
        return Verdict.INSUFFICIENT, True, "conflict"
    backed = {
        Verdict.CONFIRMED: supports,
        Verdict.FALSE: refutes,
        Verdict.MISLEADING: refutes or context,
    }[proposed]
    return (proposed, False, None) if backed else (Verdict.INSUFFICIENT, False, "no_quote")


def compute_strength(verdict: Verdict, evidence: list[Evidence], tiers: dict[str, int], today: date, archival_days: int) -> Strength:
    decisive = [e for e in evidence if e.stance in _DECISIVE_STANCES.get(verdict, ())]
    if not decisive:
        return Strength(
            level="brak",
            score=0.0,
            factors=[StrengthFactor(code="no_basis", label="Podstawa oceny", value="brak rozstrzygających dowodów", effect="neutral")],
        )

    best_tier = min(tiers.get(e.source.doc_id, 3) for e in decisive)
    tier_points, tier_text = {
        1: (0.35, "źródło pierwotne lub urzędowe"),
        2: (0.28, "organizacja fact-checkingowa lub międzynarodowa"),
    }.get(best_tier, (0.12, "media"))

    publishers = len({e.source.publisher for e in decisive})
    publisher_points = {1: 0.10, 2: 0.20}.get(publishers, 0.30)

    dates = [e.source.published_at for e in decisive if e.source.published_at]
    if not dates:
        recency_points, recency_text, recency_effect = 0.05, "źródła bez daty publikacji", "neutral"
    else:
        age = (today - max(dates)).days
        if age <= archival_days // 2:
            recency_points, recency_text, recency_effect = 0.20, f"najnowsze źródło z {max(dates).isoformat()}", "plus"
        elif age <= archival_days:
            recency_points, recency_text, recency_effect = 0.15, f"najnowsze źródło z {max(dates).isoformat()}", "plus"
        else:
            recency_points, recency_text, recency_effect = 0.05, f"materiał archiwalny (najnowsze źródło z {max(dates).isoformat()})", "minus"

    opposing = any(e.stance == _OPPOSING_STANCE.get(verdict) for e in evidence)
    agreement_points = -0.15 if opposing else 0.15

    score = round(min(max(tier_points + publisher_points + recency_points + agreement_points, 0.0), 1.0), 2)
    level = "mocna" if score >= 0.75 else "umiarkowana" if score >= 0.5 else "slaba"
    return Strength(
        level=level,
        score=score,
        factors=[
            StrengthFactor(code="source_quality", label="Jakość źródła", value=tier_text, effect="plus"),
            StrengthFactor(
                code="independent_sources",
                label="Niezależne źródła",
                value=f"{publishers} (różni wydawcy)",
                effect="plus" if publishers > 1 else "neutral",
            ),
            StrengthFactor(code="recency", label="Aktualność", value=recency_text, effect=recency_effect),
            StrengthFactor(
                code="agreement",
                label="Zgodność źródeł",
                value="część źródeł wskazuje inaczej" if opposing else "źródła są zgodne",
                effect="minus" if opposing else "plus",
            ),
        ],
    )


def _rewrite_refs(text: str, ref_map: dict[int, str]) -> str:
    def swap(match: re.Match) -> str:
        evidence_id = ref_map.get(int(match.group(1)))
        return f" [{evidence_id}]" if evidence_id else ""

    return collapse_ws(_PASSAGE_REF_RE.sub(swap, text))


def decide(
    *,
    claim_id: str,
    claim_text: str,
    risk: str,
    assessment: ClaimAssessment,
    hits: list[Hit],
    source_names: dict[str, str],
    today: date,
    archival_days: int,
) -> tuple[ClaimResult, int]:
    evidence, ref_map, rejected = validated_evidence(assessment, hits, source_names, today, archival_days)
    verdict, conflict, override = resolve_verdict(assessment.proposed_verdict, {e.stance for e in evidence})
    tiers = {h.passage.doc.id: h.passage.doc.tier for h in hits}
    justification = _OVERRIDE_TEXT[override] if override else _rewrite_refs(assessment.justification, ref_map)
    missing = _rewrite_refs(assessment.missing, ref_map) or None
    if verdict == Verdict.INSUFFICIENT and not missing:
        missing = "Nie udało się znaleźć źródła, które wprost potwierdza albo obala to twierdzenie."
    return (
        ClaimResult(
            id=claim_id,
            text=claim_text,
            verdict=verdict,
            verdict_label=VERDICT_LABELS[verdict],
            justification=justification,
            strength=compute_strength(verdict, evidence, tiers, today, archival_days),
            evidence=evidence,
            conflict=conflict,
            missing=missing,
            risk=risk,
        ),
        rejected,
    )


def unassessed(claim_id: str, claim_text: str, risk: str, verdict: Verdict, justification: str, missing: str | None = None) -> ClaimResult:
    """Wynik bez udziału modelu oceniającego: opinia/prognoza albo brak materiałów w korpusie."""
    return ClaimResult(
        id=claim_id,
        text=claim_text,
        verdict=verdict,
        verdict_label=VERDICT_LABELS[verdict],
        justification=justification,
        strength=compute_strength(verdict, [], {}, date.today(), 0),
        missing=missing,
        risk=risk,
    )
