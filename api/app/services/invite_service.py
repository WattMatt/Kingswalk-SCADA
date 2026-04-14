# api/app/services/invite_service.py
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import email as email_client
from app.core.security import create_invite_token
from app.db.models import User
from app.repos import invite_repo


async def create_invite(
    db: AsyncSession, email: str, role: str, admin: User
) -> None:
    """
    Create an invite record and dispatch the invite email.

    1. Generate invite_id before the JWT (so the ID can be embedded in the token).
    2. Create JWT — the raw token is the JWT string itself.
    3. Store SHA-256(raw_token) in DB for revocation.
    4. Send email with raw token in the link.
    """
    invite_id = uuid.uuid4()
    raw_token = create_invite_token(
        invite_id=str(invite_id), email=email, role=role
    )
    await invite_repo.create_invite_with_id(
        db,
        invite_id=invite_id,
        email=email,
        role=role,
        invited_by=admin.id,
        raw_token=raw_token,
    )
    await email_client.send_invite_email(email, raw_token)
