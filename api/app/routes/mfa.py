# api/app/routes/mfa.py
"""MFA enrollment and verification endpoints.

Enrollment flow (user is already logged in):
  POST /auth/mfa/enroll           → returns provisioning_uri
  POST /auth/mfa/confirm-enrollment { code } → returns recovery_codes, activates MFA

Login MFA flow (user has mfa_pending cookie from POST /auth/login):
  POST /auth/mfa/verify   { code } → issues access + refresh tokens
  POST /auth/mfa/recovery { code } → issues access + refresh tokens
"""
import uuid

import jwt
from fastapi import APIRouter, Cookie, Depends, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.rbac import get_current_user
from app.core.security import decode_mfa_pending_token
from app.db.engine import get_db
from app.db.models import User
from app.repos import user_repo
from app.routes.auth import _set_auth_cookies
from app.services import auth_service, mfa_service

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


class ConfirmEnrollmentRequest(BaseModel):
    code: str


class MfaVerifyRequest(BaseModel):
    code: str


class MfaRecoveryRequest(BaseModel):
    code: str


@router.post("/enroll")
async def enroll(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Begin MFA enrollment. Returns provisioning URI for QR code rendering."""
    provisioning_uri = await mfa_service.begin_enrollment(db, current_user)
    return {"provisioning_uri": provisioning_uri}


@router.post("/confirm-enrollment")
async def confirm_enrollment(
    body: ConfirmEnrollmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Confirm MFA enrollment with a valid TOTP code. Returns 10 recovery codes (shown once)."""
    recovery_codes = await mfa_service.confirm_enrollment(db, current_user, body.code)
    return {
        "recovery_codes": recovery_codes,
        "message": "MFA enabled. Store these recovery codes safely — they will not be shown again.",
    }


@router.post("/verify")
async def verify_totp(
    body: MfaVerifyRequest,
    response: Response,
    mfa_pending: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Exchange mfa_pending cookie + TOTP code for full auth tokens."""
    if not mfa_pending:
        raise AuthError("No MFA session in progress")
    try:
        payload = decode_mfa_pending_token(mfa_pending)
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired MFA session") from exc

    user = await user_repo.get_user_by_id(db, uuid.UUID(str(payload["sub"])))
    if user is None or not user.is_active:
        raise AuthError("User not found")

    await mfa_service.verify_totp_for_user(db, user, body.code)

    access_token, refresh_token, _ = await auth_service.issue_tokens(
        db, user, ip=None, user_agent=None
    )
    _set_auth_cookies(response, access_token, refresh_token)
    response.delete_cookie("mfa_pending")
    return {"message": "MFA verified"}


@router.post("/recovery")
async def use_recovery_code(
    body: MfaRecoveryRequest,
    response: Response,
    mfa_pending: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Exchange mfa_pending cookie + recovery code for full auth tokens."""
    if not mfa_pending:
        raise AuthError("No MFA session in progress")
    try:
        payload = decode_mfa_pending_token(mfa_pending)
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired MFA session") from exc

    user = await user_repo.get_user_by_id(db, uuid.UUID(str(payload["sub"])))
    if user is None or not user.is_active:
        raise AuthError("User not found")

    await mfa_service.verify_recovery_code_for_user(db, user, body.code)

    access_token, refresh_token, _ = await auth_service.issue_tokens(
        db, user, ip=None, user_agent=None
    )
    _set_auth_cookies(response, access_token, refresh_token)
    response.delete_cookie("mfa_pending")
    return {"message": "Recovery code accepted"}
