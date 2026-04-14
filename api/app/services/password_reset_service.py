# api/app/services/password_reset_service.py
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import email as email_client
from app.core.exceptions import AuthError
from app.core.redis_client import get_redis
from app.core.security import hash_password
from app.repos import password_reset_repo, user_repo

_EMAIL_RATE_LIMIT = 3     # max requests per email per hour
_IP_RATE_LIMIT = 10       # max requests per IP per hour
_RATE_WINDOW = 3600       # 1 hour in seconds


async def _check_rate_limit(email: str, ip: str | None) -> None:
    """Raise AuthError if rate limit exceeded."""
    redis = await get_redis()

    email_key = f"pwd_reset:email:{email}"
    pipe = redis.pipeline()
    pipe.incr(email_key)
    pipe.expire(email_key, _RATE_WINDOW)
    results = await pipe.execute()
    count: int = results[0]
    if count > _EMAIL_RATE_LIMIT:
        raise AuthError("Too many password reset requests. Try again later.")

    if ip:
        ip_key = f"pwd_reset:ip:{ip}"
        ip_pipe = redis.pipeline()
        ip_pipe.incr(ip_key)
        ip_pipe.expire(ip_key, _RATE_WINDOW)
        ip_results = await ip_pipe.execute()
        ip_count: int = ip_results[0]
        if ip_count > _IP_RATE_LIMIT:
            raise AuthError("Too many requests from this IP. Try again later.")


async def _send_reset_email(db: AsyncSession, email: str, raw_token: str) -> None:
    """Internal helper — named function so tests can monkeypatch it."""
    await email_client.send_password_reset_email(email, raw_token)


async def request_reset(db: AsyncSession, email: str, ip: str | None) -> None:
    """
    Rate-limit, then send reset email if the user exists.
    Always returns normally — caller must return 200 to avoid user enumeration.
    """
    await _check_rate_limit(email, ip)
    user = await user_repo.get_user_by_email(db, email)
    if user is None:
        return  # Silent — no user enumeration

    raw_token = secrets.token_urlsafe(32)
    await password_reset_repo.create_reset(db, user.id, raw_token)
    await _send_reset_email(db, user.email, raw_token)
    await user_repo.write_audit(
        db, action="auth.password_reset_requested", user_id=user.id, ip=ip
    )


async def confirm_reset(db: AsyncSession, raw_token: str, new_password: str) -> None:
    """Verify token, change password, revoke all sessions — atomic commit."""
    reset = await password_reset_repo.get_valid_reset(db, raw_token)
    if reset is None:
        raise AuthError("Invalid or expired reset token")

    user = await user_repo.get_user_by_id(db, reset.user_id)
    if user is None:
        raise AuthError("User not found")

    new_hash = hash_password(new_password)
    await user_repo.stage_update_password(db, user.id, new_hash)
    password_reset_repo.stage_consume_reset(reset)
    await user_repo.stage_revoke_all_sessions(db, user.id)
    await db.commit()

    await user_repo.write_audit(
        db, action="auth.password_reset_confirmed", user_id=user.id
    )
