from datetime import UTC, datetime

import pytest
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.repos import event_repo, telemetry_repo
from app.repos.telemetry_repo import RawSampleRow


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


# ─── Phase 2b: raw_sample + event repo ───────────────────────────────────────

_TS = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
async def clean_telemetry(clean_tables: None) -> None:  # type: ignore[misc]
    """Truncate raw_sample and events.event before each test."""
    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text(
            "TRUNCATE telemetry.raw_sample, events.event RESTART IDENTITY CASCADE"
        ))
    await engine.dispose()
    yield  # type: ignore[misc]


@pytest.mark.asyncio
async def test_insert_raw_batch_stores_samples(clean_telemetry: None) -> None:
    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        samples = [
            RawSampleRow(ts=_TS, device_id="MB_1_1_breaker_0", register_address=0, raw_value=1),
            RawSampleRow(ts=_TS, device_id="MB_1_1_breaker_1", register_address=1, raw_value=0),
        ]
        inserted = await telemetry_repo.insert_raw_batch(db, samples)
    await engine.dispose()
    assert inserted == 2


@pytest.mark.asyncio
async def test_insert_raw_batch_deduplicates(clean_telemetry: None) -> None:
    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        s = RawSampleRow(ts=_TS, device_id="MB_1_1", register_address=0, raw_value=100)
        await telemetry_repo.insert_raw_batch(db, [s])
        # Duplicate — same PK, different raw_value. Must not raise; row count = 0.
        inserted = await telemetry_repo.insert_raw_batch(db, [s])
    await engine.dispose()
    assert inserted == 0


@pytest.mark.asyncio
async def test_insert_raw_batch_empty_is_noop(clean_telemetry: None) -> None:
    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        inserted = await telemetry_repo.insert_raw_batch(db, [])
    await engine.dispose()
    assert inserted == 0


@pytest.mark.asyncio
async def test_insert_event_and_dedup_guard(clean_telemetry: None) -> None:
    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        exists_before = await event_repo.recent_event_exists(db, kind="over_voltage")
        await event_repo.insert_event(
            db,
            severity="warning",
            kind="over_voltage",
            message="test threshold exceeded",
        )
        exists_after = await event_repo.recent_event_exists(db, kind="over_voltage")
    await engine.dispose()
    assert exists_before is False
    assert exists_after is True
