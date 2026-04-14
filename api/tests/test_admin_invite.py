# api/tests/test_admin_invite.py
import pytest
from httpx import ASGITransport, AsyncClient

import app.services.invite_service as invite_svc
from app.main import app


@pytest.fixture
async def http_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as ac:
        yield ac


async def test_admin_can_send_invite(http_client, admin_user, fake_redis, monkeypatch):
    """POST /admin/invite by an admin sends invite and returns 200."""
    sent: list[dict] = []

    async def mock_send_invite(db, email, role, admin):  # noqa: ARG001
        sent.append({"email": email, "role": role})

    monkeypatch.setattr(invite_svc, "create_invite", mock_send_invite)

    await http_client.post(
        "/auth/login",
        json={"email": admin_user["email"], "password": admin_user["password"]},
    )

    resp = await http_client.post(
        "/admin/invite", json={"email": "newuser@example.com", "role": "viewer"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "Invite sent"}
    assert len(sent) == 1
    assert sent[0] == {"email": "newuser@example.com", "role": "viewer"}


async def test_operator_cannot_invite(http_client, operator_user, fake_redis):
    """POST /admin/invite by an operator must return 401."""
    await http_client.post(
        "/auth/login",
        json={"email": operator_user["email"], "password": operator_user["password"]},
    )
    resp = await http_client.post(
        "/admin/invite", json={"email": "newuser@example.com", "role": "viewer"}
    )
    assert resp.status_code == 401


async def test_unauthenticated_cannot_invite(http_client, clean_tables):
    """POST /admin/invite without auth cookie must return 401."""
    resp = await http_client.post(
        "/admin/invite", json={"email": "newuser@example.com", "role": "viewer"}
    )
    assert resp.status_code == 401


async def test_invalid_role_rejected(http_client, admin_user, fake_redis):
    """Role values outside admin/operator/viewer must return 422."""
    await http_client.post(
        "/auth/login",
        json={"email": admin_user["email"], "password": admin_user["password"]},
    )
    resp = await http_client.post(
        "/admin/invite", json={"email": "newuser@example.com", "role": "superuser"}
    )
    assert resp.status_code == 422
