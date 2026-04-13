# api/app/services/mfa_service.py
"""MFA business logic: enrollment, TOTP verification, recovery code fallback."""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_mfa_secret, encrypt_mfa_secret
from app.core.exceptions import AuthError
from app.core.totp import generate_totp_secret, get_provisioning_uri, verify_totp
from app.db.models import User
from app.repos import mfa_repo, user_repo

logger = structlog.get_logger()


async def begin_enrollment(db: AsyncSession, user: User) -> str:
    """Generate a new TOTP secret, encrypt + store it (mfa_enabled stays False).

    Returns the provisioning URI for QR code rendering.
    The user must call confirm_enrollment with a valid TOTP code to activate MFA.
    """
    secret = generate_totp_secret()
    encrypted = encrypt_mfa_secret(secret)

    # Store encrypted secret — mfa_enabled remains False until confirmed
    user.mfa_secret = encrypted
    await db.commit()
    logger.info("mfa.enrollment_started", user_id=str(user.id))
    return get_provisioning_uri(secret, user.email)


async def confirm_enrollment(
    db: AsyncSession, user: User, totp_code: str
) -> list[str]:
    """Verify the TOTP code against the pending secret, activate MFA, return recovery codes.

    Raises AuthError if code is wrong or no pending enrollment exists.
    Recovery codes are returned exactly once — store them or lose them.
    """
    if not user.mfa_secret:
        raise AuthError("No MFA enrollment in progress")

    decrypted_secret = decrypt_mfa_secret(user.mfa_secret)
    if not verify_totp(decrypted_secret, totp_code):
        raise AuthError("Invalid TOTP code")

    user.mfa_enabled = True
    await db.commit()
    recovery_codes = await mfa_repo.generate_recovery_codes(db, user.id)
    logger.info("mfa.enrollment_confirmed", user_id=str(user.id))
    return recovery_codes


async def verify_totp_for_user(db: AsyncSession, user: User, totp_code: str) -> None:
    """Verify a TOTP code during the MFA login step. Raises AuthError on failure."""
    if not user.mfa_secret:
        raise AuthError("MFA not configured")
    decrypted_secret = decrypt_mfa_secret(user.mfa_secret)
    if not verify_totp(decrypted_secret, totp_code):
        await user_repo.write_audit(db, action="auth.mfa_failed", user_id=user.id)
        raise AuthError("Invalid TOTP code")
    await user_repo.write_audit(db, action="auth.mfa_success", user_id=user.id)


async def verify_recovery_code_for_user(
    db: AsyncSession, user: User, code: str
) -> None:
    """Verify a recovery code during the MFA login step. Raises AuthError on failure.

    Valid code is marked used — cannot be reused.
    """
    valid = await mfa_repo.verify_and_consume_recovery_code(db, user.id, code)
    if not valid:
        await user_repo.write_audit(
            db, action="auth.recovery_code_failed", user_id=user.id
        )
        raise AuthError("Invalid recovery code")
    await user_repo.write_audit(
        db, action="auth.recovery_code_used", user_id=user.id
    )
