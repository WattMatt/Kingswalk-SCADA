import uuid

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import set_auth_cookies
from app.core.exceptions import AuthError
from app.core.rbac import get_current_user
from app.core.security import (
    create_mfa_pending_token,
    decode_invite_token,
    decode_token,
    generate_csrf_token,
    hash_password,
)
from app.db.engine import get_db
from app.db.models import User
from app.repos import invite_repo, user_repo
from app.services import auth_service, password_reset_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str


class OnboardRequest(BaseModel):
    """Onboarding payload — submitted with invite JWT from email link."""

    token: str
    full_name: str
    password: str


class PasswordResetRequestBody(BaseModel):
    email: EmailStr


class PasswordResetConfirmBody(BaseModel):
    token: str
    password: str


class UserResponse(BaseModel):
    """Public user fields returned by /auth/me."""

    id: str
    email: str
    full_name: str
    role: str



@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Authenticate with email + password.

    If MFA is enabled: sets mfa_pending cookie, returns {"mfa_required": true}.
    If MFA is disabled: sets full auth cookies, returns {"message": "Login successful"}.
    """
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user = await auth_service.authenticate(db, body.email, body.password, ip)

    if user.mfa_enabled:
        mfa_token = create_mfa_pending_token(user_id=str(user.id))
        response.set_cookie(
            "mfa_pending",
            mfa_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=300,
        )
        return {"mfa_required": True}

    access_token, refresh_token, _ = await auth_service.issue_tokens(
        db, user, ip, user_agent
    )
    set_auth_cookies(response, access_token, refresh_token, csrf_token=generate_csrf_token())
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
    set_auth_cookies(response, new_access, new_refresh, csrf_token=generate_csrf_token())
    return {"message": "Token refreshed"}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Clear auth cookies and revoke the server-side session."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = decode_token(refresh_token, expected_aud="refresh")
            session_id = uuid.UUID(str(payload["session_id"]))
            await user_repo.revoke_session(db, session_id)
        except Exception:
            pass  # Token invalid/expired — still clear cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/auth/refresh")
    response.delete_cookie("csrf_token")
    return {"message": "Logged out"}


@router.post("/onboard")
async def onboard(
    body: OnboardRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """
    Complete user onboarding from an invite link.

    Decodes the invite JWT, verifies the invite record is valid and unused,
    creates the user account, marks the invite accepted, and issues full auth tokens.

    Returns mfa_required=True for admin/operator roles — frontend must redirect to /mfa/enroll.
    """
    try:
        payload = decode_invite_token(body.token)
        invite_id = uuid.UUID(str(payload["sub"]))
    except Exception as exc:
        raise AuthError("Invalid or expired invite token") from exc
    inv = await invite_repo.get_valid_invite(db, invite_id, body.token)
    if inv is None:
        raise AuthError("Invite not found, already used, or expired")

    existing = await user_repo.get_user_by_email(db, inv.email)
    if existing is not None:
        raise AuthError("An account with this email already exists")

    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    password_hash = hash_password(body.password)
    user = user_repo.stage_user(db, inv.email, body.full_name, password_hash, inv.role)
    invite_repo.stage_accept_invite(inv)
    await db.commit()
    await db.refresh(user)  # populate user.id, user.role etc.

    access_token, refresh_token, _ = await auth_service.issue_tokens(db, user, ip, user_agent)
    set_auth_cookies(response, access_token, refresh_token, csrf_token=generate_csrf_token())
    await user_repo.write_audit(db, action="auth.onboard", user_id=user.id, ip=ip)

    return {
        "message": "Account created",
        "mfa_required": user.role in ("admin", "operator"),
    }


@router.post("/password-reset/request")
async def password_reset_request(
    body: PasswordResetRequestBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Always returns 200 — never reveals whether the email is registered."""
    ip = request.client.host if request.client else None
    await password_reset_service.request_reset(db, body.email, ip)
    return {"message": "If that email is registered, a reset link has been sent"}


@router.post("/password-reset/confirm")
async def password_reset_confirm(
    body: PasswordResetConfirmBody,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Verify reset token and apply new password. Revokes all active sessions."""
    await password_reset_service.confirm_reset(db, body.token, body.password)
    return {"message": "Password updated. Please log in again."}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
    )
