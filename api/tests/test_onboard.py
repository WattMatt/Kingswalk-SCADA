# api/tests/test_onboard.py
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

import app.repos.invite_repo as inv_repo
from app.core.security import create_invite_token
from app.main import app


@pytest.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as ac:
        yield ac


async def _make_invite_token(db_session, email="newbie@example.com", role="viewer"):
    """Helper: create a valid invite in the DB and return the raw JWT."""
    invite_id = uuid.uuid4()
    raw_token = create_invite_token(invite_id=str(invite_id), email=email, role=role)
    await inv_repo.create_invite_with_id(
        db_session,
        invite_id=invite_id,
        email=email,
        role=role,
        invited_by=None,
        raw_token=raw_token,
    )
    return raw_token


@pytest.fixture
async def db_session(clean_tables):
    from app.db.engine import get_db
    gen = app.dependency_overrides[get_db]()
    async for session in gen:
        yield session


async def test_onboard_creates_user_and_issues_tokens(http_client, db_session):
    """Valid invite token + credentials creates user and sets auth cookies."""
    raw_token = await _make_invite_token(db_session)
    resp = await http_client.post(
        "/auth/onboard",
        json={"token": raw_token, "full_name": "Alex New", "password": "SecurePass999!"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Account created"
    assert "access_token" in resp.cookies


async def test_onboard_viewer_no_mfa_required(http_client, db_session):
    """Viewer role does not require MFA enrollment — mfa_required is False."""
    raw_token = await _make_invite_token(db_session, role="viewer")
    resp = await http_client.post(
        "/auth/onboard",
        json={"token": raw_token, "full_name": "Viewer User", "password": "SecurePass999!"},
    )
    assert resp.status_code == 200
    assert resp.json()["mfa_required"] is False


async def test_onboard_operator_mfa_required(http_client, db_session):
    """Operator role must be prompted to enroll MFA — mfa_required is True."""
    raw_token = await _make_invite_token(db_session, email="ops@example.com", role="operator")
    resp = await http_client.post(
        "/auth/onboard",
        json={"token": raw_token, "full_name": "Ops User", "password": "SecurePass999!"},
    )
    assert resp.status_code == 200
    assert resp.json()["mfa_required"] is True


async def test_onboard_invalid_token(http_client, clean_tables):
    """Malformed JWT must return 401."""
    resp = await http_client.post(
        "/auth/onboard",
        json={"token": "not.a.jwt", "full_name": "Bad Actor", "password": "pass"},
    )
    assert resp.status_code == 401


async def test_onboard_token_cannot_be_reused(http_client, db_session):
    """After successful onboard, the same token must be rejected."""
    raw_token = await _make_invite_token(db_session, email="once@example.com")
    first_resp = await http_client.post(
        "/auth/onboard",
        json={"token": raw_token, "full_name": "Once Only", "password": "SecurePass999!"},
    )
    assert first_resp.status_code == 200  # ensure first use succeeded
    resp = await http_client.post(
        "/auth/onboard",
        json={"token": raw_token, "full_name": "Once Only", "password": "SecurePass999!"},
    )
    assert resp.status_code == 401
