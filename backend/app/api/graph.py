"""Mapa wydarzeń: panel analityczny i publiczny, zagregowany widok."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import (
    ModeratorPrincipal,
    require_admin,
    require_moderator,
    require_superuser,
)
from app.schemas import (
    EventDetailOut,
    EventGraphResponse,
    EventLinkOut,
    EventLinkReview,
    EventMemberReview,
    EventMergeRequest,
    EventRebuildOut,
    EventRebuildRequest,
)

router = APIRouter(
    prefix="/admin/graph",
    tags=["mapa wydarzeń"],
    dependencies=[Depends(require_admin)],
)
public_router = APIRouter(prefix="/public", tags=["mapa wydarzeń"])


def _store(request: Request):
    return request.app.state.store


def _log(
    request: Request,
    principal: ModeratorPrincipal,
    *,
    action: str,
    detail: str,
    event_id: str | None = None,
) -> None:
    store = getattr(request.app.state, "moderator_store", None)
    if store is None:
        return
    store.log_action(
        moderator_id=principal.id,
        author_email=principal.email,
        author_name=principal.display_name,
        action=action,
        field="event_graph",
        value_after=event_id,
        detail=detail,
    )


@router.get("", response_model=EventGraphResponse)
def graph(
    request: Request,
    window_days: Annotated[int | None, Query(ge=1, le=3650)] = None,
    limit: Annotated[int | None, Query(ge=1, le=2000)] = None,
    include_proposed: bool = True,
) -> EventGraphResponse:
    settings = request.app.state.settings
    return _store(request).event_graph(
        window_days=window_days or settings.event_link_window_days,
        limit=limit or settings.event_graph_limit,
        include_proposed=include_proposed,
    )


@router.get("/events/{event_id}", response_model=EventDetailOut)
def event_detail(request: Request, event_id: str) -> EventDetailOut:
    detail = _store(request).get_event_detail(event_id)
    if detail is None:
        raise HTTPException(404, "Nie ma takiego wydarzenia.")
    return detail


@router.patch(
    "/events/{event_id}/members/{member_id}", response_model=EventDetailOut
)
def review_member(
    request: Request,
    event_id: str,
    member_id: int,
    payload: EventMemberReview,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> EventDetailOut:
    store = _store(request)
    ok, new_event_id = store.review_event_member(
        event_id,
        member_id,
        status=payload.status,
        reviewer=principal.email,
        note=payload.note,
    )
    if not ok:
        raise HTTPException(404, "Nie ma takiego kandydata w tym wydarzeniu.")
    _log(
        request,
        principal,
        action="status_change",
        detail=(
            f"mapa wydarzeń: {'zaakceptowano' if payload.status == 'accepted' else 'odrzucono'} "
            f"kandydata {member_id}"
        ),
        event_id=new_event_id or event_id,
    )
    detail = store.get_event_detail(new_event_id or event_id)
    if detail is None:
        raise HTTPException(404, "Wydarzenie zniknęło po decyzji moderatora.")
    return detail


@router.patch("/links/{link_id}", response_model=EventLinkOut)
def review_link(
    request: Request,
    link_id: int,
    payload: EventLinkReview,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> EventLinkOut:
    link = _store(request).review_event_link(
        link_id,
        status=payload.status,
        reviewer=principal.email,
        relation=payload.relation,
        note=payload.note,
    )
    if link is None:
        raise HTTPException(404, "Nie ma takiej relacji.")
    _log(
        request,
        principal,
        action="status_change",
        detail=f"mapa wydarzeń: relacja {link_id} → {payload.status}",
        event_id=link.src_event_id,
    )
    return link


@router.post("/events/{event_id}/merge", response_model=EventDetailOut)
def merge_events(
    request: Request,
    event_id: str,
    payload: EventMergeRequest,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> EventDetailOut:
    if payload.source_event_id == event_id:
        raise HTTPException(422, "Nie można scalić wydarzenia z samym sobą.")
    store = _store(request)
    ok = store.merge_events(payload.source_event_id, event_id, principal.email)
    if not ok:
        raise HTTPException(404, "Nie znaleziono wydarzenia do scalenia.")
    _log(
        request,
        principal,
        action="edit",
        detail=f"mapa wydarzeń: scalono {payload.source_event_id} z {event_id}",
        event_id=event_id,
    )
    detail = store.get_event_detail(event_id)
    if detail is None:
        raise HTTPException(404, "Wydarzenie docelowe zniknęło.")
    return detail


@router.post("/events/{event_id}/members/{member_id}/split", response_model=EventDetailOut)
def split_member(
    request: Request,
    event_id: str,
    member_id: int,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> EventDetailOut:
    store = _store(request)
    new_event_id = store.split_event_member(event_id, member_id, principal.email)
    if new_event_id is None:
        raise HTTPException(404, "Nie ma takiego członka wydarzenia.")
    _log(
        request,
        principal,
        action="edit",
        detail=f"mapa wydarzeń: wydzielono członka {member_id} do {new_event_id}",
        event_id=new_event_id,
    )
    detail = store.get_event_detail(new_event_id)
    if detail is None:
        raise HTTPException(404, "Nowe wydarzenie nie powstało.")
    return detail


@router.post(
    "/rebuild",
    response_model=EventRebuildOut,
    dependencies=[Depends(require_superuser)],
)
async def rebuild(
    request: Request,
    payload: EventRebuildRequest,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> EventRebuildOut:
    settings = request.app.state.settings
    limit = min(payload.limit, settings.event_rebuild_limit)
    processed, events, skipped = await request.app.state.event_graph.rebuild(
        limit, reset=payload.reset
    )
    _log(
        request,
        principal,
        action="edit",
        detail=(
            f"mapa wydarzeń: przebudowa grafu, przetworzono {processed} zgłoszeń, "
            f"pominięto {skipped}"
        ),
    )
    return EventRebuildOut(
        processed_checks=processed, events=events, skipped=skipped
    )


@public_router.get("/event-map", response_model=EventGraphResponse)
def public_graph(
    request: Request,
    window_days: Annotated[int, Query(ge=1, le=3650)] = 90,
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
) -> EventGraphResponse:
    """Zagregowana mapa: bez treści zgłoszeń i bez danych sesji.

    Wydarzenie pojawia się dopiero po przekroczeniu progu k-anonimowości.
    """
    settings = request.app.state.settings
    return _store(request).public_event_graph(
        min_members=settings.event_public_min_members,
        window_days=window_days,
        limit=min(limit or settings.event_public_limit, settings.event_public_limit),
    )
