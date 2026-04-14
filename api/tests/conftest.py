import os
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlparse

import fakeredis.aioredis
import pyotp
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core import redis_client as rc
from app.core.security import hash_password
from app.db.engine import get_db
from app.db.models import User
from app.main import app

# Test database — host port 5433 maps to container port 5432 (local dev default).
# In CI, override via TEST_DB_URL env var (port 5432, no conflict with Homebrew PG).
TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql+asyncpg://scada:scada_dev@localhost:5433/kingswalk_scada_test",
)

_TEST_DB_URL = TEST_DB_URL


def _make_test_engine():  # type: ignore[no-untyped-def]
    # Fresh engine per call: pytest-asyncio creates a new event loop per test function.
    # A module-level async engine's pool is bound to the loop at creation time, so
    # reusing it across tests causes InterfaceError. Per-call creation is the correct fix.
    return create_async_engine(TEST_DB_URL, echo=False, pool_size=2, max_overflow=0)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    engine = _make_test_engine()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def clean_tables() -> None:
    """Truncate user-data tables before each test for isolation."""
    import sqlalchemy  # noqa: PLC0415

    # Create a fresh engine per fixture call to avoid cross-loop connection reuse
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(
            sqlalchemy.text(
                "TRUNCATE core.users, core.session, core.audit_log, "
                "core.invite, core.password_reset, core.recovery_code, "
                "telemetry.raw_sample, events.event "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()
    yield


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
    ) as ac:
        yield ac


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


@pytest.fixture(autouse=True)
async def fake_redis():
    """Fresh in-memory Redis per test — prevents real Redis dependency in all tests."""
    server = fakeredis.FakeServer()
    r = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    rc._redis = r
    yield r
    await r.aclose()
    rc._redis = None


@pytest.fixture
async def mfa_operator(client: AsyncClient, operator_user: dict) -> dict:
    """Login, enroll MFA, confirm enrollment. Returns credentials + totp_secret + recovery_codes."""
    await client.post("/auth/login", json={
        "email": operator_user["email"],
        "password": operator_user["password"],
    })
    enroll_resp = await client.post("/auth/mfa/enroll")
    uri = enroll_resp.json()["provisioning_uri"]
    secret = parse_qs(urlparse(uri).query)["secret"][0]
    code = pyotp.TOTP(secret).now()
    confirm_resp = await client.post("/auth/mfa/confirm-enrollment", json={"code": code})
    recovery_codes = confirm_resp.json()["recovery_codes"]
    await client.post("/auth/logout")
    return {**operator_user, "totp_secret": secret, "recovery_codes": recovery_codes}
