# api/app/repos/password_reset_repo.py
import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PasswordReset


async def create_reset(
    db: AsyncSession, user_id, raw_token: str
) -> PasswordReset:
    """Store a hashed reset token. raw_token is sent via email; hash goes in DB."""
    reset = PasswordReset(
        user_id=user_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(reset)
    await db.commit()
    await db.refresh(reset)
    return reset


async def get_valid_reset(
    db: AsyncSession, raw_token: str
) -> PasswordReset | None:
    """Return unexpired, unused PasswordReset matching raw_token. None on any mismatch."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute(
        select(PasswordReset).where(
            PasswordReset.token_hash == token_hash,
            PasswordReset.used_at.is_(None),
            PasswordReset.expires_at > datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none()


async def consume_reset(db: AsyncSession, reset: PasswordReset) -> None:
    """Mark reset as used. Subsequent calls to get_valid_reset() will return None."""
    reset.used_at = datetime.now(UTC)
    await db.commit()
