"""Tekstowa postać wyniku dla kanałów bez interfejsu graficznego (SMS, komunikatory).
Treść merytoryczna pochodzi z tego samego `CheckResponse`, co w kanale WWW."""

import re

from app.schemas import CheckResponse, CheckStatus, ClaimResult
from app.textutil import truncate

_EVIDENCE_REF_RE = re.compile(r"\s*\[E\d+\]")
_STRENGTH_LABELS = {"mocna": "mocna", "umiarkowana": "umiarkowana", "slaba": "słaba"}
_FOOTER = "To pomoc w ocenie informacji, a nie wyrok. Przeczytaj źródła."


def _claim_block(number: int, claim: ClaimResult) -> str:
    lines = [f"{number}. „{truncate(claim.text, 160)}”", f"Wynik: {claim.verdict_label.upper()}"]
    if claim.strength.level in _STRENGTH_LABELS:
        lines[-1] += f" (siła podstawy: {_STRENGTH_LABELS[claim.strength.level]})"
    lines.append(_EVIDENCE_REF_RE.sub("", claim.justification))
    if claim.conflict:
        lines.append("Źródła podają rozbieżne informacje.")
    if claim.evidence:
        source = claim.evidence[0].source
        published = f", {source.published_at.isoformat()}" if source.published_at else ""
        lines.append(f"Źródło: {source.publisher}{published}: {source.url}")
    return "\n".join(lines)


def render_text(response: CheckResponse, details_url: str, max_claims: int = 2) -> str:
    if response.status != CheckStatus.COMPLETED:
        return response.status_message or "Nie udało się wykonać sprawdzenia."
    parts = ["Prawdowid – wynik sprawdzenia"]
    parts += [_claim_block(n, c) for n, c in enumerate(response.claims[:max_claims], 1)]
    if len(response.claims) > max_claims:
        parts.append(f"Pozostałe twierdzenia ({len(response.claims) - max_claims}) znajdziesz pod linkiem poniżej.")
    parts += [w.message for w in response.warnings if w.code in ("injection_detected", "source_status")]
    if response.incident_matches:
        parts.append("Kontekst: podobna treść była już opisywana przez weryfikatorów. To nie przesądza o ocenie.")
    if response.moderator_case.message:
        parts.append(response.moderator_case.message)
    parts.append(f"Wszystkie źródła i szczegóły: {details_url}")
    parts.append(_FOOTER)
    return "\n\n".join(parts)
