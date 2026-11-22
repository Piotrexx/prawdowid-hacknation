"""Konta moderatorów, sesje, komentarze, audyt i subskrypcje powiadomień."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.schemas import (
    ActionOut,
    CommentOut,
    ModeratorCreatedOut,
    ModeratorOut,
    ProfileOut,
    ProfileStats,
)
from app.security import passwords
from app.store.models import (
    ArticleRow,
    CaseCommentRow,
    CaseRow,
    ModeratorActionRow,
    ModeratorRow,
    ModeratorSessionRow,
    PushSubscriptionRow,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def _moderator_out(row: ModeratorRow, *, private: bool = True) -> ModeratorOut:
    return ModeratorOut(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,  # type: ignore[arg-type]
        is_active=row.is_active,
        created_at=_aware(row.created_at) or _now(),
        created_by=row.created_by,
        last_login_at=_aware(row.last_login_at),
        must_change_password=row.must_change_password,
        notify_discord=row.notify_discord,
        notify_email=row.notify_email,
        notify_push=row.notify_push,
        discord_webhook_url=row.discord_webhook_url if private else None,
        comment_notify_threshold=row.comment_notify_threshold,
    )


class ModeratorStore:
    def __init__(self, engine: Engine):
        self._engine = engine

    def _session(self) -> Session:
        return Session(self._engine, expire_on_commit=False)

    # --- konta ---

    def bootstrap_superuser(
        self,
        email: str,
        password: str | None,
        display_name: str = "Superużytkownik",
    ) -> tuple[ModeratorOut, bool, str | None]:
        """Pierwsze konto superużytkownika. Zwraca (konto, utworzono, wygenerowane hasło)."""
        normalized = passwords.normalize_email(email)
        if not passwords.valid_email(normalized):
            raise ValueError("Niepoprawny adres e-mail konta startowego.")
        with self._session() as db:
            existing = db.scalars(select(ModeratorRow).where(ModeratorRow.email == normalized)).first()
            if existing:
                return _moderator_out(existing), False, None
            generated = None if password else passwords.generate_password()
            secret = password or generated
            assert secret is not None
            passwords.check_password_strength(secret)
            row = ModeratorRow(
                email=normalized,
                password_hash=passwords.hash_password(secret),
                display_name=display_name.strip() or "Superużytkownik",
                role="superuser",
                is_active=True,
                created_at=_now(),
                created_by=None,
                must_change_password=generated is not None,
            )
            db.add(row)
            db.commit()
            return _moderator_out(row), True, generated

    def create_moderator(
        self,
        *,
        email: str,
        password: str | None,
        display_name: str,
        role: str,
        created_by: str,
        must_change_password: bool = True,
    ) -> ModeratorCreatedOut:
        normalized = passwords.normalize_email(email)
        if not passwords.valid_email(normalized):
            raise ValueError("Podaj poprawny adres e-mail.")
        if role not in ("moderator", "superuser"):
            raise ValueError("Nieznana rola konta.")
        generated = None if password else passwords.generate_password()
        secret = password or generated
        assert secret is not None
        passwords.check_password_strength(secret)
        with self._session() as db:
            duplicate = db.scalars(select(ModeratorRow).where(ModeratorRow.email == normalized)).first()
            if duplicate:
                raise ValueError("Konto z tym adresem e-mail już istnieje.")
            row = ModeratorRow(
                email=normalized,
                password_hash=passwords.hash_password(secret),
                display_name=display_name.strip() or normalized.split("@", 1)[0],
                role=role,
                is_active=True,
                created_at=_now(),
                created_by=created_by,
                must_change_password=must_change_password,
            )
            db.add(row)
            db.commit()
            return ModeratorCreatedOut(
                moderator=_moderator_out(row), generated_password=generated
            )

    def list_moderators(self) -> list[ModeratorOut]:
        with self._session() as db:
            rows = db.scalars(select(ModeratorRow).order_by(ModeratorRow.created_at))
            return [_moderator_out(row) for row in rows]

    def get_moderator(self, moderator_id: int) -> ModeratorOut | None:
        with self._session() as db:
            row = db.get(ModeratorRow, moderator_id)
            return _moderator_out(row) if row else None

    def get_moderator_row(self, moderator_id: int) -> ModeratorRow | None:
        with self._session() as db:
            return db.get(ModeratorRow, moderator_id)

    def get_by_email(self, email: str) -> ModeratorRow | None:
        normalized = passwords.normalize_email(email)
        with self._session() as db:
            return db.scalars(select(ModeratorRow).where(ModeratorRow.email == normalized)).first()

    def authenticate(self, email: str, password: str) -> ModeratorRow | None:
        normalized = passwords.normalize_email(email)
        with self._session() as db:
            row = db.scalars(select(ModeratorRow).where(ModeratorRow.email == normalized)).first()
            if row is None or not row.is_active:
                return None
            if not passwords.verify_password(password, row.password_hash):
                return None
            if passwords.needs_rehash(row.password_hash):
                row.password_hash = passwords.hash_password(password)
            row.last_login_at = _now()
            db.commit()
            return row

    def update_moderator(
        self,
        moderator_id: int,
        *,
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        must_change_password: bool | None = None,
    ) -> ModeratorOut | None:
        with self._session() as db:
            row = db.get(ModeratorRow, moderator_id)
            if row is None:
                return None
            if display_name is not None:
                row.display_name = display_name.strip()
            if role is not None:
                if role not in ("moderator", "superuser"):
                    raise ValueError("Nieznana rola konta.")
                row.role = role
            if is_active is not None:
                row.is_active = is_active
            if must_change_password is not None:
                row.must_change_password = must_change_password
            db.commit()
            if is_active is False:
                self.delete_sessions_for(moderator_id)
            return _moderator_out(row)

    def update_profile(
        self,
        moderator_id: int,
        *,
        display_name: str | None = None,
        notify_discord: bool | None = None,
        notify_email: bool | None = None,
        notify_push: bool | None = None,
        discord_webhook_url: str | None = None,
        comment_notify_threshold: int | None = None,
    ) -> ModeratorOut | None:
        with self._session() as db:
            row = db.get(ModeratorRow, moderator_id)
            if row is None:
                return None
            if display_name is not None:
                row.display_name = display_name.strip()
            if notify_discord is not None:
                row.notify_discord = notify_discord
            if notify_email is not None:
                row.notify_email = notify_email
            if notify_push is not None:
                row.notify_push = notify_push
            if discord_webhook_url is not None:
                row.discord_webhook_url = discord_webhook_url.strip() or None
            if comment_notify_threshold is not None:
                row.comment_notify_threshold = comment_notify_threshold
            db.commit()
            return _moderator_out(row)

    def set_password(
        self, moderator_id: int, new_password: str, *, must_change: bool = False
    ) -> ModeratorOut | None:
        passwords.check_password_strength(new_password)
        with self._session() as db:
            row = db.get(ModeratorRow, moderator_id)
            if row is None:
                return None
            row.password_hash = passwords.hash_password(new_password)
            row.must_change_password = must_change
            db.commit()
            result = _moderator_out(row)
        self.delete_sessions_for(moderator_id)
        return result

    def reset_password(self, moderator_id: int) -> tuple[ModeratorOut, str] | None:
        generated = passwords.generate_password()
        updated = self.set_password(moderator_id, generated, must_change=True)
        if updated is None:
            return None
        return updated, generated

    # --- sesje ---

    def create_session(
        self, moderator_id: int, *, hours: int, user_agent: str | None = None
    ) -> tuple[str, datetime]:
        token = passwords.new_session_token()
        now = _now()
        expires = now + timedelta(hours=hours)
        with self._session() as db:
            db.add(
                ModeratorSessionRow(
                    token_hash=passwords.token_fingerprint(token),
                    moderator_id=moderator_id,
                    created_at=now,
                    expires_at=expires,
                    last_seen_at=now,
                    user_agent=(user_agent or "")[:200] or None,
                )
            )
            db.commit()
        return token, expires

    def login_link(
        self,
        moderator_id: int,
        *,
        base_url: str,
        hours: int,
        user_agent: str = "auto-login",
    ) -> str:
        """Jednorazowy link, który od razu loguje do panelu (token w #, nie w logach serwera)."""
        token, _ = self.create_session(moderator_id, hours=hours, user_agent=user_agent)
        return f"{base_url.rstrip('/')}/moderator#token={token}"

    def resolve_session(self, token: str) -> ModeratorRow | None:
        fingerprint = passwords.token_fingerprint(token)
        with self._session() as db:
            session = db.get(ModeratorSessionRow, fingerprint)
            if session is None:
                return None
            now = _now()
            if _aware(session.expires_at) is not None and _aware(session.expires_at) < now:
                db.delete(session)
                db.commit()
                return None
            row = db.get(ModeratorRow, session.moderator_id)
            if row is None or not row.is_active:
                db.delete(session)
                db.commit()
                return None
            session.last_seen_at = now
            db.commit()
            return row

    def delete_session(self, token: str) -> None:
        with self._session() as db:
            db.execute(
                delete(ModeratorSessionRow).where(
                    ModeratorSessionRow.token_hash == passwords.token_fingerprint(token)
                )
            )
            db.commit()

    def delete_sessions_for(self, moderator_id: int) -> int:
        with self._session() as db:
            result = db.execute(
                delete(ModeratorSessionRow).where(ModeratorSessionRow.moderator_id == moderator_id)
            )
            db.commit()
            return int(result.rowcount or 0)

    def purge_expired_sessions(self) -> int:
        with self._session() as db:
            result = db.execute(
                delete(ModeratorSessionRow).where(ModeratorSessionRow.expires_at < _now())
            )
            db.commit()
            return int(result.rowcount or 0)

    # --- komentarze ---

    def add_comment(
        self,
        *,
        moderator_id: int | None,
        author_email: str,
        author_name: str,
        body: str,
        case_id: int | None = None,
        article_id: int | None = None,
    ) -> CommentOut:
        if (case_id is None) == (article_id is None):
            raise ValueError("Komentarz musi dotyczyć dokładnie jednej sprawy albo jednego artykułu.")
        text = body.strip()
        if not text:
            raise ValueError("Komentarz nie może być pusty.")
        with self._session() as db:
            if case_id is not None and db.get(CaseRow, case_id) is None:
                raise LookupError("Nie ma takiej sprawy.")
            if article_id is not None and db.get(ArticleRow, article_id) is None:
                raise LookupError("Nie ma takiego artykułu.")
            row = CaseCommentRow(
                case_id=case_id,
                article_id=article_id,
                moderator_id=moderator_id,
                author_email=author_email,
                author_name=author_name,
                body=text,
                created_at=_now(),
            )
            db.add(row)
            db.commit()
            return self._comment_out(db, row)

    def _comment_out(self, db: Session, row: CaseCommentRow) -> CommentOut:
        case_claim = None
        article_title = None
        if row.case_id is not None:
            case = db.get(CaseRow, row.case_id)
            case_claim = (case.claim_text if case else "")[:180] or None
        if row.article_id is not None:
            article = db.get(ArticleRow, row.article_id)
            article_title = article.title if article else None
        return CommentOut(
            id=row.id,
            case_id=row.case_id,
            article_id=row.article_id,
            moderator_id=row.moderator_id,
            author_email=row.author_email,
            author_name=row.author_name,
            body=row.body,
            created_at=_aware(row.created_at) or _now(),
            edited_at=_aware(row.edited_at),
            case_claim_preview=case_claim,
            article_title=article_title,
        )

    def list_comments(
        self,
        *,
        case_id: int | None = None,
        article_id: int | None = None,
        limit: int = 200,
    ) -> list[CommentOut]:
        with self._session() as db:
            query = select(CaseCommentRow).order_by(CaseCommentRow.created_at.asc()).limit(limit)
            if case_id is not None:
                query = query.where(CaseCommentRow.case_id == case_id)
            if article_id is not None:
                query = query.where(CaseCommentRow.article_id == article_id)
            return [self._comment_out(db, row) for row in db.scalars(query)]

    def count_comments(self, *, case_id: int | None = None, article_id: int | None = None) -> int:
        with self._session() as db:
            query = select(func.count()).select_from(CaseCommentRow)
            if case_id is not None:
                query = query.where(CaseCommentRow.case_id == case_id)
            if article_id is not None:
                query = query.where(CaseCommentRow.article_id == article_id)
            return int(db.scalar(query) or 0)

    def delete_comment(
        self, comment_id: int, *, moderator_id: int | None, is_superuser: bool
    ) -> bool:
        with self._session() as db:
            row = db.get(CaseCommentRow, comment_id)
            if row is None:
                return False
            if not is_superuser and row.moderator_id != moderator_id:
                raise PermissionError("Możesz usunąć tylko własny komentarz.")
            db.delete(row)
            db.commit()
            return True

    def comments_by_author(self, moderator_id: int, limit: int = 50) -> list[CommentOut]:
        with self._session() as db:
            rows = db.scalars(
                select(CaseCommentRow)
                .where(CaseCommentRow.moderator_id == moderator_id)
                .order_by(CaseCommentRow.created_at.desc())
                .limit(limit)
            )
            return [self._comment_out(db, row) for row in rows]

    # --- audyt ---

    def log_action(
        self,
        *,
        moderator_id: int | None,
        author_email: str,
        author_name: str,
        action: str,
        case_id: int | None = None,
        article_id: int | None = None,
        field: str | None = None,
        value_before: str | None = None,
        value_after: str | None = None,
        detail: str | None = None,
    ) -> None:
        with self._session() as db:
            db.add(
                ModeratorActionRow(
                    moderator_id=moderator_id,
                    author_email=author_email,
                    author_name=author_name,
                    case_id=case_id,
                    article_id=article_id,
                    action=action,
                    field=field,
                    value_before=value_before,
                    value_after=value_after,
                    detail=detail,
                    created_at=_now(),
                )
            )
            db.commit()

    def list_actions(self, moderator_id: int, limit: int = 100) -> list[ActionOut]:
        with self._session() as db:
            rows = db.scalars(
                select(ModeratorActionRow)
                .where(ModeratorActionRow.moderator_id == moderator_id)
                .order_by(ModeratorActionRow.created_at.desc())
                .limit(limit)
            )
            result = []
            for row in rows:
                claim = None
                if row.case_id is not None:
                    case = db.get(CaseRow, row.case_id)
                    claim = (case.claim_text if case else "")[:180] or None
                result.append(
                    ActionOut(
                        id=row.id,
                        action=row.action,
                        field=row.field,
                        value_before=row.value_before,
                        value_after=row.value_after,
                        detail=row.detail,
                        case_id=row.case_id,
                        article_id=row.article_id,
                        case_claim_preview=claim,
                        created_at=_aware(row.created_at) or _now(),
                    )
                )
            return result

    def profile(self, moderator_id: int) -> ProfileOut | None:
        with self._session() as db:
            row = db.get(ModeratorRow, moderator_id)
            if row is None:
                return None
            stats = ProfileStats(
                comments=int(
                    db.scalar(
                        select(func.count())
                        .select_from(CaseCommentRow)
                        .where(CaseCommentRow.moderator_id == moderator_id)
                    )
                    or 0
                ),
                status_changes=int(
                    db.scalar(
                        select(func.count())
                        .select_from(ModeratorActionRow)
                        .where(
                            ModeratorActionRow.moderator_id == moderator_id,
                            ModeratorActionRow.action == "status_change",
                        )
                    )
                    or 0
                ),
                edits=int(
                    db.scalar(
                        select(func.count())
                        .select_from(ModeratorActionRow)
                        .where(
                            ModeratorActionRow.moderator_id == moderator_id,
                            ModeratorActionRow.action == "edit",
                        )
                    )
                    or 0
                ),
                cases_touched=int(
                    db.scalar(
                        select(func.count(func.distinct(ModeratorActionRow.case_id))).where(
                            ModeratorActionRow.moderator_id == moderator_id,
                            ModeratorActionRow.case_id.is_not(None),
                        )
                    )
                    or 0
                ),
            )
        return ProfileOut(
            moderator=_moderator_out(row),
            stats=stats,
            comments=self.comments_by_author(moderator_id, 50),
            actions=self.list_actions(moderator_id, 100),
        )

    # --- Web Push ---

    def add_push_subscription(
        self,
        moderator_id: int,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str | None = None,
    ) -> None:
        with self._session() as db:
            existing = db.scalars(
                select(PushSubscriptionRow).where(PushSubscriptionRow.endpoint == endpoint)
            ).first()
            if existing:
                existing.moderator_id = moderator_id
                existing.p256dh = p256dh
                existing.auth = auth
                existing.user_agent = (user_agent or "")[:200] or None
            else:
                db.add(
                    PushSubscriptionRow(
                        moderator_id=moderator_id,
                        endpoint=endpoint,
                        p256dh=p256dh,
                        auth=auth,
                        user_agent=(user_agent or "")[:200] or None,
                        created_at=_now(),
                    )
                )
            db.commit()

    def list_push_subscriptions(self, moderator_id: int) -> list[PushSubscriptionRow]:
        with self._session() as db:
            return list(
                db.scalars(
                    select(PushSubscriptionRow).where(
                        PushSubscriptionRow.moderator_id == moderator_id
                    )
                )
            )

    def delete_push_subscription(self, endpoint: str) -> None:
        with self._session() as db:
            db.execute(delete(PushSubscriptionRow).where(PushSubscriptionRow.endpoint == endpoint))
            db.commit()

    def touch_push_subscription(self, endpoint: str) -> None:
        with self._session() as db:
            row = db.scalars(
                select(PushSubscriptionRow).where(PushSubscriptionRow.endpoint == endpoint)
            ).first()
            if row:
                row.last_used_at = _now()
                db.commit()

    # --- ustawienia aplikacji ---

    def get_setting(self, key: str) -> dict[str, Any] | None:
        return StoreProxy.get_setting(self._engine, key)

    def set_setting(self, key: str, value: dict[str, Any], updated_by: str | None) -> None:
        StoreProxy.set_setting(self._engine, key, value, updated_by)


class StoreProxy:
    """Dostęp do `app_settings` bez dziedziczenia po `Store` (unikamy cyklu importów)."""

    @staticmethod
    def get_setting(engine: Engine, key: str) -> dict[str, Any] | None:
        from app.store.models import AppSettingRow

        with Session(engine, expire_on_commit=False) as db:
            row = db.get(AppSettingRow, key)
            return dict(row.value or {}) if row else None

    @staticmethod
    def set_setting(
        engine: Engine, key: str, value: dict[str, Any], updated_by: str | None
    ) -> None:
        from app.store.models import AppSettingRow

        with Session(engine, expire_on_commit=False) as db:
            row = db.get(AppSettingRow, key)
            if row is None:
                row = AppSettingRow(key=key, value=value, updated_at=_now(), updated_by=updated_by)
                db.add(row)
            else:
                row.value = value
                row.updated_at = _now()
                row.updated_by = updated_by
            db.commit()
