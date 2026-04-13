import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AuditLog, Session, User

logger = structlog.get_logger()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch an active, non-deleted user by email."""
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Fetch an active, non-deleted user by primary key."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def create_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    refresh_token: str,
    ip: str | None,
    user_agent: str | None,
) -> Session:
    """Create a new session, storing the SHA-256 hash of the refresh token."""
    session = Session(
        id=session_id,
        user_id=user_id,
        refresh_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_token_ttl_seconds),
        ip=ip,
        user_agent=user_agent,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_valid_session(
    db: AsyncSession, session_id: uuid.UUID, refresh_token_raw: str
) -> Session | None:
    """Return session if ID matches, hash matches, not revoked, not expired."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(UTC),
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    expected = hashlib.sha256(refresh_token_raw.encode()).hexdigest()
    return session if session.refresh_hash == expected else None


async def rotate_session(
    db: AsyncSession, session: Session, new_refresh_token_raw: str
) -> None:
    """Atomically replace refresh hash — no grace period."""
    session.refresh_hash = hashlib.sha256(new_refresh_token_raw.encode()).hexdigest()
    await db.commit()


async def revoke_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    """Mark a session as revoked."""
    await db.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


async def write_audit(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    """Append an immutable audit log entry."""
    entry = AuditLog(
        action=action,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        payload=payload or {},
    )
    db.add(entry)
    await db.commit()
