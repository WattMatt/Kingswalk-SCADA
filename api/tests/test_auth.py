import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.models import User

_TEST_DB_URL = "postgresql+asyncpg://scada:scada_dev@localhost:5433/kingswalk_scada_test"


async def _seed_user(email: str, password: str, role: str = "operator") -> dict:
    """Insert a test user and return credentials. Uses fresh engine to avoid loop issues."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        user = User(
            email=email,
            full_name="Test User",
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
    await engine.dispose()
    return {"email": email, "password": password}


@pytest.fixture
async def operator_user(clean_tables: None) -> dict:  # noqa: ARG001
    return await _seed_user("operator@test.scada", "SecurePass123!")


@pytest.fixture
async def admin_user(clean_tables: None) -> dict:  # noqa: ARG001
    return await _seed_user("admin@test.scada", "AdminPass456!", role="admin")


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient, clean_tables: None) -> None:  # noqa: ARG001
    await _seed_user("user@test.scada", "correctpassword")
    response = await client.post(
        "/auth/login", json={"email": "user@test.scada", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "error" in response.json()


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient, clean_tables: None) -> None:  # noqa: ARG001
    """No user enumeration — unknown email looks same as wrong password."""
    response = await client.post(
        "/auth/login",
        json={"email": "nobody@nowhere.com", "password": "anything"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_fields_returns_422(client: AsyncClient, clean_tables: None) -> None:  # noqa: ARG001
    response = await client.post("/auth/login", json={"email": "x@x.com"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success_sets_httponly_cookies(
    client: AsyncClient, operator_user: dict
) -> None:
    response = await client.post("/auth/login", json=operator_user)
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert "csrf_token" in response.cookies
    cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "samesite=strict" in cookie_header.lower()


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient, clean_tables: None) -> None:  # noqa: ARG001
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token_returns_user(
    client: AsyncClient, operator_user: dict
) -> None:
    await client.post("/auth/login", json=operator_user)
    response = await client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == operator_user["email"]
    assert body["role"] == "operator"


@pytest.mark.asyncio
async def test_logout_clears_cookies(client: AsyncClient, operator_user: dict) -> None:
    await client.post("/auth/login", json=operator_user)
    response = await client.post("/auth/logout")
    assert response.status_code == 200
    assert client.cookies.get("access_token", "") == ""


@pytest.mark.asyncio
async def test_me_after_logout_returns_401(
    client: AsyncClient, operator_user: dict
) -> None:
    await client.post("/auth/login", json=operator_user)
    await client.post("/auth/logout")
    response = await client.get("/auth/me")
    assert response.status_code == 401
