import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.redis_client import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.models import User
from app.repos import user_repo

# Dummy hash used to normalise timing when user is not found
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4"
    "$AAAAAAAAAAAAAAAAAAAAAA"
    "$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)

_LOCKOUT_ATTEMPTS = 5
_LOCKOUT_WINDOW = 900  # 15 minutes in seconds


async def _check_lockout(email: str, ip: str | None) -> None:
    """Raise AuthError if account or IP is currently locked out."""
    redis = await get_redis()
    if await redis.exists(f"auth:lock:{email}"):
        raise AuthError("Account temporarily locked. Try again later.")
    if ip and await redis.exists(f"auth:lock:ip:{ip}"):
        raise AuthError("Too many attempts from this IP. Try again later.")


async def _record_failure(email: str, ip: str | None) -> None:
    """Increment failure counters; set lock sentinel when threshold reached."""
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.incr(f"auth:fail:{email}")
    pipe.expire(f"auth:fail:{email}", _LOCKOUT_WINDOW)
    if ip:
        pipe.incr(f"auth:fail:ip:{ip}")
        pipe.expire(f"auth:fail:ip:{ip}", _LOCKOUT_WINDOW)
    results = await pipe.execute()

    email_count: int = results[0]
    if email_count >= _LOCKOUT_ATTEMPTS:
        await redis.set(f"auth:lock:{email}", "1", ex=_LOCKOUT_WINDOW)

    if ip:
        ip_count: int = results[2]
        if ip_count >= _LOCKOUT_ATTEMPTS:
            await redis.set(f"auth:lock:ip:{ip}", "1", ex=_LOCKOUT_WINDOW)


async def _clear_failure(email: str) -> None:
    """Delete failure counter after a successful login."""
    redis = await get_redis()
    await redis.delete(f"auth:fail:{email}")


async def authenticate(
    db: AsyncSession, email: str, password: str, ip: str | None
) -> User:
    """
    Validate credentials. Raises AuthError on any failure.

    Always runs password verification (even for unknown email) to prevent
    timing-based user enumeration. Enforces per-account and per-IP lockout
    via Redis (5 failures / 15 min window).
    """
    await _check_lockout(email, ip)

    user = await user_repo.get_user_by_email(db, email)
    candidate_hash = user.password_hash if user else _DUMMY_HASH

    password_ok = verify_password(password, candidate_hash)

    if not password_ok or user is None or not user.is_active:
        await _record_failure(email, ip)
        await user_repo.write_audit(db, action="auth.login_failed", ip=ip)
        raise AuthError("Invalid email or password")

    await _clear_failure(email)
    return user


async def issue_tokens(
    db: AsyncSession, user: User, ip: str | None, user_agent: str | None
) -> tuple[str, str, str]:
    """
    Create access token + refresh token, persist session.

    Returns: (access_token, refresh_token, session_id)
    """
    session_id = uuid.uuid4()

    # Generate tokens first — no placeholder ever stored
    refresh_token = create_refresh_token(
        user_id=str(user.id), session_id=str(session_id)
    )
    access_token = create_access_token(user_id=str(user.id), role=user.role)

    # Persist session with the real hash from the start
    await user_repo.create_session(
        db,
        session_id=session_id,
        user_id=user.id,
        refresh_token=refresh_token,
        ip=ip,
        user_agent=user_agent,
    )
    await user_repo.write_audit(db, action="auth.login", user_id=user.id, ip=ip)

    return access_token, refresh_token, str(session_id)


async def refresh_tokens(
    db: AsyncSession, refresh_token: str, ip: str | None
) -> tuple[str, str]:
    """
    Validate and rotate refresh token. Returns (new_access_token, new_refresh_token).
    """
    try:
        payload = decode_token(refresh_token, expected_aud="refresh")
        session_id = uuid.UUID(payload["session_id"])  # type: ignore[arg-type]
    except Exception as exc:
        raise AuthError("Invalid refresh token") from exc

    session = await user_repo.get_valid_session(db, session_id, refresh_token)
    if session is None:
        raise AuthError("Session expired or revoked")

    user = await user_repo.get_user_by_id(db, session.user_id)
    if user is None or not user.is_active:
        raise AuthError("User account unavailable")

    new_refresh = create_refresh_token(
        user_id=str(user.id), session_id=str(session_id)
    )
    new_access = create_access_token(user_id=str(user.id), role=user.role)

    await user_repo.rotate_session(db, session, new_refresh)
    await user_repo.write_audit(db, action="auth.token_refresh", user_id=session.user_id, ip=ip)

    return new_access, new_refresh
