# api/tests/test_login_lockout.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def http_client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://test"
    ) as ac:
        yield ac


async def test_fifth_failure_locks_account(http_client, operator_user):
    """Exactly 5 failures must trigger lock; 6th attempt rejected even with correct password."""
    for _ in range(5):
        r = await http_client.post(
            "/auth/login",
            json={"email": operator_user["email"], "password": "wrongpassword"},
        )
        assert r.status_code == 401

    r = await http_client.post(
        "/auth/login",
        json={"email": operator_user["email"], "password": operator_user["password"]},
    )
    assert r.status_code == 401
    assert "locked" in r.json()["error"].lower()


async def test_four_failures_still_allows_login(http_client, operator_user):
    """4 failures must NOT lock — 5th correct attempt succeeds."""
    for _ in range(4):
        await http_client.post(
            "/auth/login",
            json={"email": operator_user["email"], "password": "wrongpassword"},
        )

    r = await http_client.post(
        "/auth/login",
        json={"email": operator_user["email"], "password": operator_user["password"]},
    )
    assert r.status_code == 200
    assert r.json() == {"message": "Login successful"}


async def test_successful_login_clears_failure_counter(http_client, operator_user, fake_redis):
    """After a successful login, the failure counter is deleted (not just decremented)."""
    for _ in range(3):
        await http_client.post(
            "/auth/login",
            json={"email": operator_user["email"], "password": "wrongpassword"},
        )

    await http_client.post(
        "/auth/login",
        json={"email": operator_user["email"], "password": operator_user["password"]},
    )

    key = f"auth:fail:{operator_user['email']}"
    assert await fake_redis.exists(key) == 0


async def test_unknown_email_also_increments_counter(http_client, clean_tables, fake_redis):
    """Login failure for unknown email must still increment failure counter (timing normalised)."""
    for _ in range(5):
        await http_client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "anything"},
        )

    r = await http_client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "anything"},
    )
    assert r.status_code == 401
    assert "locked" in r.json()["error"].lower()
