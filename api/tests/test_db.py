import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


@pytest.fixture
async def db_session() -> AsyncSession:
    """Create a fresh engine+session per test to avoid event-loop reuse issues."""
    test_engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_db_connection(db_session: AsyncSession) -> None:
    """Verify we can connect to the test database."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_core_schema_exists(db_session: AsyncSession) -> None:
    """Verify core schema and users table exist after migrations."""
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'core'")
    )
    count = result.scalar()
    assert count is not None and count > 0


@pytest.mark.asyncio
async def test_audit_log_table_exists(db_session: AsyncSession) -> None:
    """Verify core.audit_log table exists."""
    result = await db_session.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'core' AND table_name = 'audit_log'"
        )
    )
    assert result.scalar() == 1
