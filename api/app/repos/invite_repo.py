# api/app/repos/invite_repo.py
import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import INVITE_TOKEN_TTL_SECONDS
from app.db.models import Invite


def stage_invite_with_id(
    db: AsyncSession,
    *,
    invite_id: uuid.UUID,
    email: str,
    role: str,
    invited_by: uuid.UUID | None,
    raw_token: str,
) -> Invite:
    """
    Stage an invite for insertion without committing.

    Use this in service-layer code that controls the transaction boundary.
    Call db.commit() after the email is successfully sent.
    """
    invite = Invite(
        id=invite_id,
        email=email,
        role=role,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        invited_by=invited_by,
        expires_at=datetime.now(UTC) + timedelta(seconds=INVITE_TOKEN_TTL_SECONDS),
    )
    db.add(invite)
    return invite


async def create_invite_with_id(
    db: AsyncSession,
    *,
    invite_id: uuid.UUID,
    email: str,
    role: str,
    invited_by: uuid.UUID | None,
    raw_token: str,
) -> Invite:
    """
    Create an invite record with a pre-generated ID.

    The ID is generated before the JWT so it can be embedded in the token payload.
    raw_token is the full JWT string — its SHA-256 hash is stored for revocation checks.
    """
    invite = Invite(
        id=invite_id,
        email=email,
        role=role,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        invited_by=invited_by,
        expires_at=datetime.now(UTC) + timedelta(seconds=INVITE_TOKEN_TTL_SECONDS),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def get_valid_invite(
    db: AsyncSession, invite_id: uuid.UUID, raw_token: str
) -> Invite | None:
    """
    Return invite if: ID matches, token hash matches, not yet accepted, not expired.
    Returns None on any mismatch — never raises.
    """
    result = await db.execute(
        select(Invite).where(
            Invite.id == invite_id,
            Invite.accepted_at.is_(None),
            Invite.expires_at > datetime.now(UTC),
        )
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        return None
    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return invite if hmac.compare_digest(invite.token_hash, expected_hash) else None


async def accept_invite(db: AsyncSession, invite: Invite) -> None:
    """Mark invite as accepted. Subsequent calls to get_valid_invite() will return None."""
    invite.accepted_at = datetime.now(UTC)
    await db.commit()
