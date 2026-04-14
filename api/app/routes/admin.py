# api/app/routes/admin.py
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_role
from app.db.engine import get_db
from app.db.models import User
from app.services import invite_service

admin_router = APIRouter(prefix="/admin", tags=["admin"])


class InviteRequest(BaseModel):
    """Admin invite payload."""

    email: EmailStr
    role: Literal["admin", "operator", "viewer"]


@admin_router.post("/invite")
async def invite_user(
    body: InviteRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Send an onboarding invite email to a new user (admin-only)."""
    await invite_service.create_invite(db, body.email, body.role, current_user)
    return {"message": "Invite sent"}
