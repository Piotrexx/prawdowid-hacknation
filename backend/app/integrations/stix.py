"""Eksport STIX 2.1 z werdyktami, cytatami i mapowaniem DISARM (bez serwera OpenCTI)."""

from __future__ import annotations

from datetime import UTC, datetime

from stix2 import Bundle, ExternalReference, Identity, Note, Report

from app.integrations.disarm import disarm_summary
from app.schemas import CheckResponse


def _now() -> datetime:
    return datetime.now(UTC)


def _created(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def stix_bundle(results: list[CheckResponse]) -> str:
    identity = Identity(
        name="Prawdowid",
        description="Weryfikacja informacji oparta na jawnych źródłach i cytatach.",
        identity_class="system",
    )
    objects: list = [identity]
    for result in results:
        created = _created(result.created_at)
        notes = []
        if result.claims:
            for claim in result.claims:
                refs = [
                    ExternalReference(source_name="Prawdowid źródło", url=evidence.source.url)
                    for evidence in claim.evidence
                ]
                content = (
                    f"Twierdzenie: {claim.text}\n"
                    f"Werdykt: {claim.verdict_label}\n"
                    f"Siła dowodów: {claim.strength.level} ({claim.strength.score})\n"
                    f"Uzasadnienie: {claim.justification}\n"
                    f"Sprzeczność źródeł: {'tak' if claim.conflict else 'nie'}"
                )
                if claim.evidence:
                    content += "\nCytaty:\n" + "\n".join(
                        f"- [{evidence.id}/{evidence.stance}] {evidence.quote} ({evidence.source.url})"
                        for evidence in claim.evidence
                    )
                note = Note(
                    allow_custom=True,
                    content=content,
                    object_refs=[identity.id],
                    created=created,
                    modified=created,
                    external_references=refs or None,
                    x_prawdowid_claim_id=claim.id,
                    x_prawdowid_verdict=claim.verdict.value,
                    x_prawdowid_risk=claim.risk,
                    x_prawdowid_disarm=disarm_summary(claim.verdict.value),
                )
                notes.append(note)
                objects.append(note)
        else:
            note = Note(
                allow_custom=True,
                content=(
                    f"Sprawdzenie {result.id} zakończone statusem {result.status.value}. "
                    f"Komunikat: {result.status_message or 'brak'}"
                ),
                object_refs=[identity.id],
                created=created,
                modified=created,
                x_prawdowid_status=result.status.value,
            )
            notes.append(note)
            objects.append(note)
        report = Report(
            allow_custom=True,
            name=f"Prawdowid – sprawdzenie {result.id}",
            description=result.justification or result.summary or "Sprawdzenie informacji.",
            published=created,
            created=created,
            modified=created,
            report_types=["threat-report"],
            object_refs=[note.id for note in notes] or [identity.id],
            external_references=[
                ExternalReference(source_name="Prawdowid sprawdzenie", url=source.url)
                for source in result.source_articles[:20]
            ]
            or None,
            x_prawdowid_check_id=result.id,
            x_prawdowid_status=result.status.value,
            x_prawdowid_summary_verdict=result.verdict.value if result.verdict else None,
        )
        objects.append(report)
    return Bundle(objects=objects, allow_custom=True).serialize(pretty=True)
