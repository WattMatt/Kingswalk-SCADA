from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.rbac import get_current_user
from app.core.security import generate_csrf_token
from app.db.engine import get_db
from app.db.models import User
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public user fields returned by /auth/me."""

    id: str
    email: str
    full_name: str
    role: str


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly, Secure, SameSite=Strict auth cookies per SPEC §A.5."""
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=900,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/auth/refresh",
        max_age=604800,
    )
    # CSRF: NOT HttpOnly — must be readable by JS for double-submit pattern
    response.set_cookie(
        "csrf_token",
        generate_csrf_token(),
        httponly=False,
        samesite="strict",
        max_age=900,
        path="/",
    )


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Authenticate with email + password. Sets HttpOnly cookies on success."""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    user = await auth_service.authenticate(db, body.email, body.password, ip)
    access_token, refresh_token = await auth_service.issue_tokens(
        db, user, ip, user_agent
    )
    _set_auth_cookies(response, access_token, refresh_token)
    return {"message": "Login successful"}


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Rotate refresh token. Reads from HttpOnly cookie."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise AuthError("No refresh token")
    ip = request.client.host if request.client else None
    new_access, new_refresh = await auth_service.refresh_tokens(db, token, ip)
    _set_auth_cookies(response, new_access, new_refresh)
    return {"message": "Token refreshed"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear all auth cookies."""
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/auth/refresh")
    response.delete_cookie("csrf_token", path="/")
    return {"message": "Logged out"}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
    )
