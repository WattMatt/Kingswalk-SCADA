import uuid

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.security import decode_token
from app.db.engine import get_db
from app.db.models import User
from app.repos import user_repo


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: validate access token cookie, return authenticated user."""
    if not access_token:
        raise AuthError()
    try:
        payload = decode_token(access_token, expected_aud="access")
    except Exception as exc:
        raise AuthError() from exc

    user = await user_repo.get_user_by_id(db, uuid.UUID(payload["sub"]))  # type: ignore[arg-type]
    if user is None or not user.is_active:
        raise AuthError()
    return user


def require_role(*roles: str):  # type: ignore[no-untyped-def]
    """Return a FastAPI dependency that requires one of the given roles."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AuthError("Insufficient permissions")
        return user

    return _check
