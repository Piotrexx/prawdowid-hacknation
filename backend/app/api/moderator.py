"""Panel moderatora: logowanie, konto, komentarze, konta i przełącznik modelu."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from pydantic import BaseModel

from app.api.deps import (
    MODERATOR_COOKIE,
    ModeratorPrincipal,
    enforce_rate_limit,
    moderator_token_from_request,
    require_moderator,
    require_superuser,
)
from app.config import Settings
from app.llm import runtime
from app.llm.catalog import PROVIDERS_BY_KEY, provider_catalog
from app.schemas import (
    ActionOut,
    CommentCreate,
    CommentOut,
    LlmModelOut,
    LlmProviderOut,
    LlmSettingsOut,
    LlmSettingsUpdate,
    ModeratorCreate,
    ModeratorCreatedOut,
    ModeratorLogin,
    ModeratorLoginOut,
    ModeratorOut,
    ModeratorPasswordResetOut,
    ModeratorUpdate,
    PasswordChange,
    ProfileOut,
    ProfileStats,
    ProfileUpdate,
    PushPublicKeyOut,
    PushSubscriptionIn,
)
from app.security import passwords
from app.store.db import Store
from app.store.moderators import ModeratorStore

auth_router = APIRouter(prefix="/admin/auth", tags=["konto moderatora"])
router = APIRouter(prefix="/admin", tags=["moderator"])


def _store(request: Request) -> Store:
    return request.app.state.store


def _moderators(request: Request) -> ModeratorStore:
    return request.app.state.moderator_store


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _require_account(principal: ModeratorPrincipal) -> int:
    if principal.id is None:
        raise HTTPException(
            400, "Ta operacja wymaga konta moderatora (token techniczny jej nie obsługuje)."
        )
    return principal.id


def _profile(request: Request, moderator_id: int) -> ProfileOut:
    profile = _moderators(request).profile(moderator_id)
    if profile is None:
        raise HTTPException(404, "Nie ma takiego konta.")
    service = getattr(request.app.state, "notifications", None)
    return profile.model_copy(
        update={
            "email_available": bool(service and service.email_available),
            "push_available": bool(service and service.push_available),
            "discord_available": bool(service and service.discord_available),
        }
    )


def _log(
    request: Request,
    principal: ModeratorPrincipal,
    action: str,
    *,
    case_id: int | None = None,
    article_id: int | None = None,
    field: str | None = None,
    value_before: str | None = None,
    value_after: str | None = None,
    detail: str | None = None,
) -> None:
    _moderators(request).log_action(
        moderator_id=principal.id,
        author_email=principal.email,
        author_name=principal.display_name,
        action=action,
        case_id=case_id,
        article_id=article_id,
        field=field,
        value_before=value_before,
        value_after=value_after,
        detail=detail,
    )


# --- logowanie i konto ---


@auth_router.post(
    "/login",
    response_model=ModeratorLoginOut,
    dependencies=[Depends(enforce_rate_limit)],
)
def login(request: Request, response: Response, payload: ModeratorLogin) -> ModeratorLoginOut:
    row = _moderators(request).authenticate(payload.email, payload.password)
    if row is None:
        # Ten sam komunikat dla złego hasła i nieistniejącego konta.
        raise HTTPException(401, "Niepoprawny e-mail albo hasło.")
    settings = _settings(request)
    token, expires = _moderators(request).create_session(
        row.id,
        hours=settings.moderator_session_hours,
        user_agent=request.headers.get("User-Agent"),
    )
    response.set_cookie(
        MODERATOR_COOKIE,
        token,
        max_age=settings.moderator_session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.public_base_url.startswith("https"),
    )
    return ModeratorLoginOut(
        token=token,
        expires_at=expires,
        moderator=_moderators(request).get_moderator(row.id),  # type: ignore[arg-type]
    )


@auth_router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    token = moderator_token_from_request(request)
    if token:
        _moderators(request).delete_session(token)
    response.delete_cookie(MODERATOR_COOKIE)
    return {"logged_out": True}


@auth_router.get("/me", response_model=ProfileOut)
def me(
    request: Request,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> ProfileOut:
    if principal.id is None:
        # Token techniczny nie ma profilu – zwracamy konto techniczne tylko do odczytu.
        return ProfileOut(
            moderator=ModeratorOut(
                id=0,
                email=principal.email,
                display_name=principal.display_name,
                role="superuser",
                is_active=True,
                created_at=datetime.now(UTC),
            ),
            stats=ProfileStats(),
        )
    return _profile(request, principal.id)


@auth_router.patch("/me", response_model=ProfileOut)
def update_me(
    request: Request,
    payload: ProfileUpdate,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> ProfileOut:
    moderator_id = _require_account(principal)
    webhook = payload.discord_webhook_url
    if webhook:
        parts = urlsplit(webhook.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise HTTPException(422, "Adres webhooka Discorda musi być adresem http(s).")
        webhook = webhook.strip()
    updated = _moderators(request).update_profile(
        moderator_id,
        display_name=payload.display_name,
        notify_discord=payload.notify_discord,
        notify_email=payload.notify_email,
        notify_push=payload.notify_push,
        discord_webhook_url=webhook,
        comment_notify_threshold=payload.comment_notify_threshold,
    )
    if updated is None:
        raise HTTPException(404, "Nie ma takiego konta.")
    _log(request, principal, "account", field="profile", detail="zmiana ustawień konta")
    return _profile(request, moderator_id)


class PasswordChangeOut(BaseModel):
    changed: bool
    logged_out: bool = True


@auth_router.post("/me/password", response_model=PasswordChangeOut)
def change_password(
    request: Request,
    response: Response,
    payload: PasswordChange,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> PasswordChangeOut:
    moderator_id = _require_account(principal)
    row = _moderators(request).get_moderator_row(moderator_id)
    if row is None:
        raise HTTPException(404, "Nie ma takiego konta.")
    if not passwords.verify_password(payload.current_password, row.password_hash):
        raise HTTPException(400, "Obecne hasło jest niepoprawne.")
    passwords.check_password_strength(payload.new_password)
    _moderators(request).set_password(moderator_id, payload.new_password)
    response.delete_cookie(MODERATOR_COOKIE)
    _log(request, principal, "account", field="password", detail="zmiana hasła")
    return PasswordChangeOut(changed=True, logged_out=True)


@auth_router.get("/me/push-public-key", response_model=PushPublicKeyOut)
def push_public_key(
    request: Request,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> PushPublicKeyOut:
    _ = principal
    service = getattr(request.app.state, "notifications", None)
    if service is None:
        return PushPublicKeyOut(public_key="", configured=False)
    return service.public_key_out()


@auth_router.post("/me/push-subscription", status_code=204)
def subscribe_push(
    request: Request,
    payload: PushSubscriptionIn,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> Response:
    moderator_id = _require_account(principal)
    if not payload.endpoint.startswith("https://"):
        raise HTTPException(422, "Niepoprawny adres subskrypcji push.")
    _moderators(request).add_push_subscription(
        moderator_id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        user_agent=payload.user_agent or request.headers.get("User-Agent"),
    )
    return Response(status_code=204)


@auth_router.delete("/me/push-subscription", status_code=204)
def unsubscribe_push(
    request: Request,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
    endpoint: str = Query(min_length=10, max_length=2000),
) -> Response:
    moderator_id = _require_account(principal)
    owned = {
        sub.endpoint
        for sub in _moderators(request).list_push_subscriptions(moderator_id)
    }
    if endpoint in owned:
        _moderators(request).delete_push_subscription(endpoint)
    return Response(status_code=204)


# --- komentarze do spraw i artykułów ---
# Opinie moderatorów są na razie wyłączone także w backendzie.
# Zostawiamy implementację, ale nie rejestrujemy tras, żeby nie było
# niedziałających elementów w panelu.


# @router.get("/cases/{case_id}/comments", response_model=list[CommentOut])
def list_case_comments(
    request: Request,
    case_id: int,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[CommentOut]:
    _ = principal
    return _moderators(request).list_comments(case_id=case_id, limit=limit)


# @router.post("/cases/{case_id}/comments", response_model=CommentOut, status_code=201)
def add_case_comment(
    request: Request,
    background: BackgroundTasks,
    case_id: int,
    payload: CommentCreate,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> CommentOut:
    try:
        comment = _moderators(request).add_comment(
            moderator_id=principal.id,
            author_email=principal.email,
            author_name=principal.display_name or principal.email,
            body=payload.body,
            case_id=case_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    _log(request, principal, "comment", case_id=case_id, detail=payload.body[:180])
    service = getattr(request.app.state, "notifications", None)
    if service is not None:
        background.add_task(service.comment_added, comment)
    return comment


# @router.get("/articles/{article_id}/comments", response_model=list[CommentOut])
def list_article_comments(
    request: Request,
    article_id: int,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[CommentOut]:
    _ = principal
    return _moderators(request).list_comments(article_id=article_id, limit=limit)


# @router.post("/articles/{article_id}/comments", response_model=CommentOut, status_code=201)
def add_article_comment(
    request: Request,
    background: BackgroundTasks,
    article_id: int,
    payload: CommentCreate,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> CommentOut:
    try:
        comment = _moderators(request).add_comment(
            moderator_id=principal.id,
            author_email=principal.email,
            author_name=principal.display_name or principal.email,
            body=payload.body,
            article_id=article_id,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    _log(request, principal, "comment", article_id=article_id, detail=payload.body[:180])
    service = getattr(request.app.state, "notifications", None)
    if service is not None:
        background.add_task(service.comment_added, comment)
    return comment


# @router.delete("/comments/{comment_id}")
def delete_comment(
    request: Request,
    comment_id: int,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> dict[str, bool]:
    try:
        deleted = _moderators(request).delete_comment(
            comment_id, moderator_id=principal.id, is_superuser=principal.is_superuser
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if not deleted:
        raise HTTPException(404, "Nie ma takiego komentarza.")
    _log(request, principal, "comment_deleted", detail=f"komentarz nr {comment_id}")
    return {"deleted": True}


# --- konta moderatorów (superużytkownik) ---


@router.get("/moderators", response_model=list[ModeratorOut])
def list_moderators(
    request: Request,
    principal: Annotated[ModeratorPrincipal, Depends(require_superuser)],
) -> list[ModeratorOut]:
    _ = principal
    return _moderators(request).list_moderators()


@router.post("/moderators", response_model=ModeratorCreatedOut, status_code=201)
def create_moderator(
    request: Request,
    payload: ModeratorCreate,
    principal: Annotated[ModeratorPrincipal, Depends(require_superuser)],
) -> ModeratorCreatedOut:
    try:
        created = _moderators(request).create_moderator(
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            role=payload.role,
            created_by=principal.email,
            must_change_password=payload.must_change_password,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    _log(request, principal, "account", detail=f"utworzono konto {created.moderator.email}")
    return created


@router.patch("/moderators/{moderator_id}", response_model=ModeratorOut)
def update_moderator(
    request: Request,
    moderator_id: int,
    payload: ModeratorUpdate,
    principal: Annotated[ModeratorPrincipal, Depends(require_superuser)],
) -> ModeratorOut:
    if principal.id == moderator_id and (
        payload.is_active is False or payload.role == "moderator"
    ):
        raise HTTPException(422, "Nie możesz odebrać uprawnień własnemu kontu.")
    existing = _moderators(request).get_moderator(moderator_id)
    if existing is None:
        raise HTTPException(404, "Nie ma takiego konta.")
    superusers = [
        moderator
        for moderator in _moderators(request).list_moderators()
        if moderator.role == "superuser" and moderator.is_active
    ]
    if (
        existing.role == "superuser"
        and existing.is_active
        and (payload.is_active is False or payload.role == "moderator")
        and len(superusers) <= 1
    ):
        raise HTTPException(422, "Musi zostać co najmniej jedno aktywne konto superużytkownika.")
    try:
        updated = _moderators(request).update_moderator(
            moderator_id,
            display_name=payload.display_name,
            role=payload.role,
            is_active=payload.is_active,
            must_change_password=payload.must_change_password,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if updated is None:
        raise HTTPException(404, "Nie ma takiego konta.")
    _log(request, principal, "account", detail=f"zmiana konta {updated.email}")
    return updated


@router.post(
    "/moderators/{moderator_id}/reset-password", response_model=ModeratorPasswordResetOut
)
def reset_moderator_password(
    request: Request,
    moderator_id: int,
    principal: Annotated[ModeratorPrincipal, Depends(require_superuser)],
) -> ModeratorPasswordResetOut:
    result = _moderators(request).reset_password(moderator_id)
    if result is None:
        raise HTTPException(404, "Nie ma takiego konta.")
    moderator, generated = result
    _log(request, principal, "account", detail=f"reset hasła {moderator.email}")
    return ModeratorPasswordResetOut(moderator=moderator, generated_password=generated)


# --- model językowy ---


def _llm_out(request: Request, config: runtime.LlmConfig, *, configured: bool) -> LlmSettingsOut:
    public = runtime.public_settings(_settings(request), config)
    return LlmSettingsOut(**public, configured=configured)


@router.get("/llm/providers", response_model=list[LlmProviderOut])
def llm_providers(
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> list[LlmProviderOut]:
    _ = principal
    return [
        LlmProviderOut(
            key=provider.key,
            name=provider.name,
            icon=provider.icon,
            base_url=provider.base_url,
            requires_key=provider.requires_key,
            is_local=provider.is_local,
            note=provider.note,
            models=[
                LlmModelOut(
                    id=model.id,
                    label=model.label,
                    price_input=model.price_input,
                    price_output=model.price_output,
                )
                for model in provider.models
            ],
        )
        for provider in provider_catalog()
    ]


@router.get("/llm/settings", response_model=LlmSettingsOut)
def llm_settings(
    request: Request,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
) -> LlmSettingsOut:
    _ = principal
    config = getattr(request.app.state, "llm_config", None)
    if config is None:
        config = runtime.load_config(_store(request), _settings(request))
    provider = request.app.state.service._provider
    return _llm_out(request, config, configured=provider is not None)


@router.put("/llm/settings", response_model=LlmSettingsOut)
def update_llm_settings(
    request: Request,
    payload: LlmSettingsUpdate,
    principal: Annotated[ModeratorPrincipal, Depends(require_superuser)],
) -> LlmSettingsOut:
    if payload.provider not in PROVIDERS_BY_KEY:
        raise HTTPException(422, "Nieznany dostawca modelu.")
    current = runtime.load_config(_store(request), _settings(request))
    if payload.clear_api_key:
        api_key = None
    elif payload.api_key and payload.api_key.strip():
        api_key = payload.api_key.strip()
    else:
        api_key = current.api_key
    spec = PROVIDERS_BY_KEY[payload.provider]
    base_url = (payload.base_url or "").strip() or spec.base_url
    config = runtime.LlmConfig(
        provider=payload.provider,
        model=payload.model.strip(),
        base_url=base_url,
        api_key=api_key,
        price_input=payload.price_input if payload.price_input is not None else None,
        price_output=payload.price_output if payload.price_output is not None else None,
        json_mode=payload.json_mode or current.json_mode,
    )
    if config.price_input is None and config.price_output is None:
        catalog_prices = runtime.effective_prices(
            runtime.LlmConfig(
                provider=config.provider,
                model=config.model,
                base_url=config.base_url,
            )
        )
        config = runtime.LlmConfig(
            provider=config.provider,
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            price_input=catalog_prices[0],
            price_output=catalog_prices[1],
            json_mode=config.json_mode,
        )
    runtime.save_config(_store(request), config, principal.email)
    provider = runtime.apply_config(request.app.state.service, _settings(request), config)
    request.app.state.llm_config = config
    request.app.state.llm_ready = provider is not None
    _log(
        request,
        principal,
        "llm_change",
        field="model",
        value_before=current.model,
        value_after=f"{config.provider}/{config.model}",
        detail="zmiana modelu językowego w panelu",
    )
    return _llm_out(request, config, configured=provider is not None)


# --- pomocnicze ---


@router.get("/me/actions", response_model=list[ActionOut])
def my_actions(
    request: Request,
    principal: Annotated[ModeratorPrincipal, Depends(require_moderator)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ActionOut]:
    moderator_id = _require_account(principal)
    return _moderators(request).list_actions(moderator_id, limit=limit)
