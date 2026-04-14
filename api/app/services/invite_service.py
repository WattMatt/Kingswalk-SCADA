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

    Stages the DB row, sends the email (raises on failure — nothing commits),
    then commits. This ensures no orphaned rows if email delivery fails.
    """
    invite_id = uuid.uuid4()
    raw_token = create_invite_token(
        invite_id=str(invite_id), email=email, role=role
    )
    invite_repo.stage_invite_with_id(
        db,
        invite_id=invite_id,
        email=email,
        role=role,
        invited_by=admin.id,
        raw_token=raw_token,
    )
    await email_client.send_invite_email(email, raw_token)
    await db.commit()
