# api/tests/test_password_reset.py
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

import app.services.password_reset_service as prs
from app.main import app


@pytest.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as ac:
        yield ac


async def test_reset_request_returns_200_for_unknown_email(http_client, clean_tables, fake_redis):
    """No user enumeration — unknown email still returns 200."""
    resp = await http_client.post(
        "/auth/password-reset/request", json={"email": "ghost@example.com"}
    )
    assert resp.status_code == 200
    assert "message" in resp.json()


async def test_reset_request_sends_email_for_known_user(
    http_client, operator_user, fake_redis, monkeypatch
):
    """Known email triggers email dispatch."""
    sent: list[str] = []

    async def mock_send(db, email, raw_token):  # noqa: ARG001
        sent.append(email)

    monkeypatch.setattr(prs, "_send_reset_email", mock_send)

    await http_client.post(
        "/auth/password-reset/request", json={"email": operator_user["email"]}
    )
    assert len(sent) == 1
    assert sent[0] == operator_user["email"]


async def test_reset_confirm_changes_password(
    http_client, operator_user, fake_redis, monkeypatch
):
    """Valid reset token changes the password and revokes all sessions."""
    tokens: list[str] = []

    async def capture_token(db, email, raw_token):  # noqa: ARG001
        tokens.append(raw_token)

    monkeypatch.setattr(prs, "_send_reset_email", capture_token)

    await http_client.post(
        "/auth/password-reset/request", json={"email": operator_user["email"]}
    )
    token = tokens[0]

    resp = await http_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "BrandNewPass777!"},
    )
    assert resp.status_code == 200

    # Old password must no longer work
    login_old = await http_client.post(
        "/auth/login",
        json={"email": operator_user["email"], "password": operator_user["password"]},
    )
    assert login_old.status_code == 401

    # New password must work
    login_new = await http_client.post(
        "/auth/login",
        json={"email": operator_user["email"], "password": "BrandNewPass777!"},
    )
    assert login_new.status_code == 200


async def test_reset_token_is_single_use(
    http_client, operator_user, fake_redis, monkeypatch
):
    """The same reset token cannot be used twice."""
    tokens: list[str] = []

    async def capture_token(db, email, raw_token):  # noqa: ARG001
        tokens.append(raw_token)

    monkeypatch.setattr(prs, "_send_reset_email", capture_token)

    await http_client.post(
        "/auth/password-reset/request", json={"email": operator_user["email"]}
    )
    token = tokens[0]

    first = await http_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "FirstChange888!"},
    )
    assert first.status_code == 200

    resp = await http_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "SecondChange888!"},
    )
    assert resp.status_code == 401


async def test_reset_rate_limit_per_email(
    http_client, operator_user, fake_redis, monkeypatch
):
    """4th reset request for the same email within 1 hour is rate-limited."""
    monkeypatch.setattr(prs, "_send_reset_email", AsyncMock())

    for _ in range(3):
        r = await http_client.post(
            "/auth/password-reset/request", json={"email": operator_user["email"]}
        )
        assert r.status_code == 200

    resp = await http_client.post(
        "/auth/password-reset/request", json={"email": operator_user["email"]}
    )
    assert resp.status_code == 401  # AuthError maps to 401; 429 is a future enhancement


async def test_invalid_reset_token_rejected(http_client, clean_tables, fake_redis):
    """Bogus token must return 401."""
    resp = await http_client.post(
        "/auth/password-reset/confirm",
        json={"token": "notarealtoken", "password": "anything"},
    )
    assert resp.status_code == 401


async def test_reset_revokes_existing_sessions(
    http_client, operator_user, fake_redis, monkeypatch
):
    """Sessions issued before reset must be invalidated after reset completes."""
    tokens: list[str] = []

    async def capture_token(db, email, raw_token):  # noqa: ARG001
        tokens.append(raw_token)

    monkeypatch.setattr(prs, "_send_reset_email", capture_token)

    # Log in to get a session cookie
    login_resp = await http_client.post(
        "/auth/login",
        json={"email": operator_user["email"], "password": operator_user["password"]},
    )
    assert login_resp.status_code == 200

    # Request + capture reset token
    await http_client.post(
        "/auth/password-reset/request", json={"email": operator_user["email"]}
    )
    token = tokens[0]

    # Perform reset
    await http_client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "password": "NewSecurePass555!"},
    )

    # The refresh token from before the reset must now be rejected (session revoked in DB)
    refresh_resp = await http_client.post("/auth/refresh")
    assert refresh_resp.status_code == 401
