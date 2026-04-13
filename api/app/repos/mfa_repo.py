# api/app/repos/mfa_repo.py
"""Recovery code CRUD — argon2id hashed, single-use, 10 per user.

Codes are 8 groups of 4 uppercase hex chars (128-bit entropy).
Format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
"""
import secrets
import uuid
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RecoveryCode

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
_CODE_COUNT = 10


def _generate_code() -> str:
    """Generate one recovery code: 8 groups of 4 uppercase hex chars (128-bit entropy)."""
    raw = secrets.token_hex(16).upper()  # 32 hex chars = 128 bits
    return "-".join(raw[i : i + 4] for i in range(0, 32, 4))


async def generate_recovery_codes(
    db: AsyncSession, user_id: uuid.UUID
) -> list[str]:
    """Generate 10 new recovery codes, invalidating all previous ones for this user.

    Returns plaintext codes — displayed once and never retrievable again.
    """
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
    plaintext_codes = [_generate_code() for _ in range(_CODE_COUNT)]
    for code in plaintext_codes:
        db.add(RecoveryCode(user_id=user_id, code_hash=_hasher.hash(code)))
    await db.commit()
    return plaintext_codes


async def verify_and_consume_recovery_code(
    db: AsyncSession, user_id: uuid.UUID, code: str
) -> bool:
    """Verify a recovery code and mark it used if valid.

    Scans unused codes for this user (at most 10). Returns True if valid, False otherwise.
    Never raises.
    """
    result = await db.execute(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user_id,
            RecoveryCode.used_at.is_(None),
        )
    )
    rows = result.scalars().all()

    for rc in rows:
        try:
            _hasher.verify(rc.code_hash, code)
            rc.used_at = datetime.now(UTC)
            await db.commit()
            return True
        except (VerifyMismatchError, VerificationError, InvalidHash):
            continue
    return False
