"""Mapa wydarzeń: grupowanie, k-anonimowość, decyzje moderatora i sprzątanie."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.events import EventGraph
from app.core.prompts import EventRelationship
from app.llm.base import Usage
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
from tests.conftest import ADMIN

API = "/api/v1"


def make_response(
    text: str,
    *,
    session: str = "sesja-mapy-0001",
    claim_text: str | None = None,
    keywords: list[str] | None = None,
    main_topic: str = "Temat testowy",
) -> CheckResponse:
    claim = claim_text or text
    return CheckResponse(
        id=uuid.uuid4().hex,
        created_at=datetime.now(UTC),
        channel="web",
        status=CheckStatus.COMPLETED,
        input=InputInfo(kind="text", text=text),
        claims=[
            ClaimResult(
                id="c1",
                text=claim,
                verdict=Verdict.INSUFFICIENT,
                verdict_label=VERDICT_LABELS[Verdict.INSUFFICIENT],
                justification="Brak wystarczających dowodów.",
                strength=Strength(level="slaba", score=0.2),
            )
        ],
        keywords=keywords or ["Testowo", "most"],
        main_topic=main_topic,
    )


def save(store: Store, response: CheckResponse, session: str) -> None:
    store.save_check(response, session, None)


async def test_same_claim_lands_in_one_event(settings):
    store = Store(settings.database_url)
    graph = EventGraph(settings, store, None)

    first = make_response("Most w Testowie runął podczas powodzi.", session="sesja-a-0001")
    second = make_response("Most w Testowie runął podczas powodzi.", session="sesja-b-0001")
    save(store, first, "sesja-a-0001")
    save(store, second, "sesja-b-0001")

    assert await graph.ingest_check(first) == 1
    assert await graph.ingest_check(second) == 1

    data = store.event_graph(window_days=90, limit=50)
    events = [node for node in data.nodes if node.kind == "event"]
    assert len(events) == 1
    detail = store.get_event_detail(events[0].id)
    assert detail is not None
    assert detail.event.member_count == 2
    assert {member.status for member in detail.members} == {"accepted"}


async def test_public_map_waits_for_k_anonymity(settings):
    store = Store(settings.database_url)
    graph = EventGraph(settings, store, None)

    responses = [
        make_response(
            f"Most w Testowie runął podczas powodzi. Wersja {index}.",
            session=f"sesja-pub-{index:04d}",
            claim_text="Most w Testowie runął podczas powodzi.",
            main_topic="Zawalenie mostu w Testowie",
        )
        for index in range(3)
    ]
    for index, response in enumerate(responses):
        save(store, response, f"sesja-pub-{index:04d}")

    assert await graph.ingest_check(responses[0]) == 1
    assert store.public_event_graph(min_members=3, window_days=90, limit=50).nodes == []

    for response in responses[1:]:
        await graph.ingest_check(response)

    public = store.public_event_graph(min_members=3, window_days=90, limit=50)
    [node] = public.nodes
    assert node.kind == "event"
    assert node.member_count == 3
    assert "Most w Testowie" not in node.label
    assert node.label == "Zawalenie mostu w Testowie"


async def test_rejecting_proposal_creates_separate_event(settings):
    store = Store(settings.database_url)
    graph = EventGraph(settings, store, None)

    first = make_response("Most w Testowie runął podczas powodzi.", session="sesja-rej-0001")
    second = make_response("Most w Testowie runął podczas powodzi.", session="sesja-rej-0002")
    save(store, first, "sesja-rej-0001")
    save(store, second, "sesja-rej-0002")
    await graph.ingest_check(first)
    await graph.ingest_check(second)

    event_id = next(
        node.id for node in store.event_graph(window_days=90, limit=50).nodes if node.kind == "event"
    )
    detail = store.get_event_detail(event_id)
    assert detail is not None and len(detail.members) == 2
    candidate = detail.members[-1]

    ok, new_event_id = store.review_event_member(
        event_id,
        candidate.id,
        status="rejected",
        reviewer="moderator@example.com",
    )
    assert ok and new_event_id
    old = store.get_event_detail(event_id)
    new = store.get_event_detail(new_event_id)
    assert old is not None and old.event.member_count == 1
    assert new is not None and new.event.member_count == 1
    assert new.members[0].source == "review"


async def test_deleting_session_removes_event(settings):
    store = Store(settings.database_url)
    graph = EventGraph(settings, store, None)

    response = make_response("Most w Testowie runął podczas powodzi.", session="sesja-del-0001")
    save(store, response, "sesja-del-0001")
    await graph.ingest_check(response)
    assert store.event_count() == 1

    store.delete_session("sesja-del-0001")
    assert store.event_count() == 0
    assert store.public_event_graph(min_members=1, window_days=90, limit=50).nodes == []


async def test_deleting_one_session_recomputes_aggregates(settings):
    store = Store(settings.database_url)
    graph = EventGraph(settings, store, None)

    first = make_response(
        "Most w Testowie runął podczas powodzi.",
        session="sesja-agg-0001",
        keywords=["Tajne", "powódź"],
        main_topic="Tajny temat pierwszy",
    )
    second = make_response(
        "Most w Testowie runął podczas powodzi dzisiaj.",
        session="sesja-agg-0002",
        keywords=["Remont", "miasto"],
        main_topic="Temat po usunięciu",
    )
    save(store, first, "sesja-agg-0001")
    save(store, second, "sesja-agg-0002")
    await graph.ingest_check(first)
    await graph.ingest_check(second)

    event_id = next(
        node.id for node in store.event_graph(window_days=90, limit=50).nodes if node.kind == "event"
    )
    before = store.get_event_detail(event_id)
    assert before is not None
    assert "Tajne" in before.event.keywords

    store.delete_session("sesja-agg-0001")
    after = store.get_event_detail(event_id)
    assert after is not None
    assert after.event.member_count == 1
    assert "Tajne" not in after.event.keywords
    assert after.event.keywords == ["Remont", "miasto"]
    assert after.event.topic == "Temat po usunięciu"
    assert "dzisiaj" in after.event.title


async def test_link_from_deleted_session_is_removed(settings):
    store = Store(settings.database_url)
    graph = EventGraph(settings, store, None)

    first = make_response("Most w Testowie runął podczas powodzi.", session="sesja-link-0001")
    second = make_response("Burmistrz Testowa otworzył nową szkołę.", session="sesja-link-0002")
    save(store, first, "sesja-link-0001")
    save(store, second, "sesja-link-0002")
    await graph.ingest_check(first)
    await graph.ingest_check(second)

    details = [
        store.get_event_detail(node.id)
        for node in store.event_graph(window_days=90, limit=50).nodes
        if node.kind == "event"
    ]
    first_event = next(item for item in details if item and item.members[0].check_id == first.id)
    second_event = next(item for item in details if item and item.members[0].check_id == second.id)
    link = store.add_event_link(
        src_event_id=first_event.event.id,
        dst_event_id=second_event.event.id,
        relation="related_topic",
        score=0.5,
        reason="Relacja testowa z drugiego zgłoszenia.",
        origin_check_id=second.id,
    )
    assert link is not None
    assert len(store.get_event_detail(first_event.event.id).links) == 1

    store.delete_session("sesja-link-0002")
    survivor = store.get_event_detail(first_event.event.id)
    assert survivor is not None
    assert survivor.links == []
    assert store.get_event_detail(second_event.event.id) is None
    assert store.event_count() == 1


async def test_llm_qualifier_accepts_gray_zone_pair(settings):
    class Qualifier:
        name = "fake"
        model = "fake-qualifier"

        async def structured(self, *, system, user, schema, effort="medium", images=None):
            assert schema is EventRelationship
            return (
                EventRelationship(
                    relation="same_event",
                    confidence=0.92,
                    reason="Ten sam most i ta sama powódź, inny opis skutku.",
                    evidence_a="Most w Testowie",
                    evidence_b="Most w Testowie",
                ),
                Usage(10, 10, 1),
            )

    tuned = settings.model_copy(
        update={
            "event_llm_qualifier_enabled": True,
            "event_link_auto_lexical": 0.6,
            "event_link_review_lexical": 0.1,
        }
    )
    store = Store(tuned.database_url)
    graph = EventGraph(tuned, store, None, provider_getter=lambda: Qualifier())

    first = make_response("Most w Testowie runął podczas powodzi.", session="sesja-llm-0001")
    second = make_response(
        "Most w Testowie został zamknięty z powodu remontu.", session="sesja-llm-0002"
    )
    save(store, first, "sesja-llm-0001")
    save(store, second, "sesja-llm-0002")

    await graph.ingest_check(first)
    await graph.ingest_check(second)

    event_id = next(
        node.id for node in store.event_graph(window_days=90, limit=50).nodes if node.kind == "event"
    )
    detail = store.get_event_detail(event_id)
    assert detail is not None
    assert detail.event.member_count == 2
    assert {member.source for member in detail.members} == {"auto", "llm"}


async def test_graph_api_and_public_view(client):
    store = client.app.state.store
    graph = client.app.state.event_graph
    for index in range(3):
        response = make_response(
            f"Twierdzenie testowe numer {index} o Testowie.",
            session=f"sesja-api-{index:04d}",
            claim_text="Twierdzenie testowe.",
            main_topic="Testowy materiał",
        )
        save(store, response, f"sesja-api-{index:04d}")
        assert await graph.ingest_check(response) == 1

    admin = client.get(f"{API}/admin/graph", headers=ADMIN)
    assert admin.status_code == 200, admin.text
    body = admin.json()
    events = [node for node in body["nodes"] if node["kind"] == "event"]
    assert len(events) == 1
    assert events[0]["member_count"] == 3

    public = client.get(f"{API}/public/event-map?window_days=90")
    assert public.status_code == 200, public.text
    public_events = [node for node in public.json()["nodes"] if node["kind"] == "event"]
    assert len(public_events) == 1
    assert "Twierdzenie testowe" not in public_events[0]["label"]

    unauthorized = client.get(f"{API}/admin/graph")
    assert unauthorized.status_code == 401


async def test_review_and_merge_endpoints(client):
    store = client.app.state.store
    graph = client.app.state.event_graph
    for index in range(2):
        response = make_response(
            "Most w Testowie runął podczas powodzi.",
            session=f"sesja-merge-{index:04d}",
            claim_text="Most w Testowie runął podczas powodzi.",
        )
        save(store, response, f"sesja-merge-{index:04d}")
        await graph.ingest_check(response)

    graph_body = client.get(f"{API}/admin/graph", headers=ADMIN).json()
    [event] = [node for node in graph_body["nodes"] if node["kind"] == "event"]
    detail = client.get(f"{API}/admin/graph/events/{event['id']}", headers=ADMIN).json()
    candidate = detail["members"][-1]

    split = client.patch(
        f"{API}/admin/graph/events/{event['id']}/members/{candidate['id']}",
        headers=ADMIN,
        json={"status": "rejected"},
    )
    assert split.status_code == 200, split.text
    split_body = split.json()
    assert split_body["event"]["id"] != event["id"]
    assert split_body["event"]["member_count"] == 1

    merged = client.post(
        f"{API}/admin/graph/events/{event['id']}/merge",
        headers=ADMIN,
        json={"source_event_id": split_body["event"]["id"]},
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["event"]["member_count"] == 2
    final = client.get(f"{API}/admin/graph", headers=ADMIN).json()
    assert len([node for node in final["nodes"] if node["kind"] == "event"]) == 1
