# api/tests/test_invite_repo.py
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.engine import get_db
from app.db.models import Invite
from app.main import app
from app.repos import invite_repo


@pytest.fixture
async def db_session(clean_tables):  # noqa: ARG001
    """Fresh DB session per test — clean_tables ensures isolation."""
    gen = app.dependency_overrides[get_db]()
    async for session in gen:
        yield session


async def test_create_and_retrieve_invite(db_session: AsyncSession) -> None:
    """Stored invite is retrievable by ID + matching raw token."""
    invite_id = uuid.uuid4()
    raw_token = "raw_test_token_abc123"
    invite = await invite_repo.create_invite_with_id(
        db_session,
        invite_id=invite_id,
        email="newuser@example.com",
        role="viewer",
        invited_by=None,
        raw_token=raw_token,
    )
    assert invite.id == invite_id
    assert invite.email == "newuser@example.com"
    assert invite.accepted_at is None

    retrieved = await invite_repo.get_valid_invite(db_session, invite_id, raw_token)
    assert retrieved is not None
    assert retrieved.email == "newuser@example.com"


async def test_wrong_token_returns_none(db_session: AsyncSession) -> None:
    """Wrong raw token must not match even if invite ID is correct."""
    invite_id = uuid.uuid4()
    await invite_repo.create_invite_with_id(
        db_session,
        invite_id=invite_id,
        email="other@example.com",
        role="viewer",
        invited_by=None,
        raw_token="correct_token",
    )
    result = await invite_repo.get_valid_invite(db_session, invite_id, "wrong_token")
    assert result is None


async def test_accepted_invite_not_retrievable(db_session: AsyncSession) -> None:
    """After accept_invite(), get_valid_invite() returns None."""
    invite_id = uuid.uuid4()
    raw_token = "accept_test_token"
    invite = await invite_repo.create_invite_with_id(
        db_session,
        invite_id=invite_id,
        email="accept@example.com",
        role="operator",
        invited_by=None,
        raw_token=raw_token,
    )
    await invite_repo.accept_invite(db_session, invite)

    result = await invite_repo.get_valid_invite(db_session, invite_id, raw_token)
    assert result is None


async def test_expired_invite_not_retrievable(db_session: AsyncSession) -> None:
    """An invite whose expires_at is in the past must not be returned."""
    invite_id = uuid.uuid4()
    raw_token = "expire_test_token"
    expired_invite = Invite(
        id=invite_id,
        email="expired@example.com",
        role="viewer",
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        invited_by=None,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(expired_invite)
    await db_session.commit()

    result = await invite_repo.get_valid_invite(db_session, invite_id, raw_token)
    assert result is None
