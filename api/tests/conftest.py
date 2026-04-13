import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.engine import get_db
from app.main import app

# Test database — host port 5433 maps to container port 5432 (local dev default).
# In CI, override via TEST_DB_URL env var (port 5432, no conflict with Homebrew PG).
TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql+asyncpg://scada:scada_dev@localhost:5433/kingswalk_scada_test",
)


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
                "TRUNCATE core.users, core.session, core.audit_log RESTART IDENTITY CASCADE"
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
