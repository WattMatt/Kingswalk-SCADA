"""Tests for threshold evaluation — event generation with 5-min dedup."""
import pytest

from app.services.threshold_service import evaluate_sample


@pytest.mark.asyncio
async def test_no_thresholds_no_events(clean_tables: None) -> None:
    """With no threshold rules, evaluate_sample creates no events."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        events_created = await evaluate_sample(
            db, device_id="MB_1_1_breaker_0", register_address=0, raw_value=999
        )
    await engine.dispose()
    assert events_created == 0


@pytest.mark.asyncio
async def test_exceeds_high_threshold_creates_event(clean_tables: None) -> None:
    """raw_value > warning_high creates a warning event."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(text(
            "INSERT INTO events.threshold (asset_class, metric, warning_low, warning_high) "
            "VALUES ('raw', 'MB_1_1_breaker_0:0', 100, 500)"
        ))
        await db.commit()
        events_created = await evaluate_sample(
            db, device_id="MB_1_1_breaker_0", register_address=0, raw_value=600
        )
    await engine.dispose()
    assert events_created == 1


@pytest.mark.asyncio
async def test_within_band_no_event(clean_tables: None) -> None:
    """raw_value within [warning_low, warning_high] creates no event."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(text(
            "INSERT INTO events.threshold (asset_class, metric, warning_low, warning_high) "
            "VALUES ('raw', 'MB_1_1_breaker_0:0', 100, 500)"
        ))
        await db.commit()
        events_created = await evaluate_sample(
            db, device_id="MB_1_1_breaker_0", register_address=0, raw_value=300
        )
    await engine.dispose()
    assert events_created == 0


@pytest.mark.asyncio
async def test_dedup_prevents_second_event(clean_tables: None) -> None:
    """Second call within 5 minutes with same kind does not create duplicate event."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(text(
            "INSERT INTO events.threshold (asset_class, metric, warning_low, warning_high) "
            "VALUES ('raw', 'MB_1_1_breaker_0:0', 100, 500)"
        ))
        await db.commit()
        first = await evaluate_sample(
            db, device_id="MB_1_1_breaker_0", register_address=0, raw_value=600
        )
        second = await evaluate_sample(
            db, device_id="MB_1_1_breaker_0", register_address=0, raw_value=700
        )
    await engine.dispose()
    assert first == 1
    assert second == 0  # deduped


@pytest.mark.asyncio
async def test_critical_band_overrides_warning(clean_tables: None) -> None:
    """Value outside critical_high fires critical severity, not warning."""
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import Event
    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(text(
            "INSERT INTO events.threshold "
            "(asset_class, metric, warning_low, warning_high, error_low, error_high, "
            "critical_low, critical_high) "
            "VALUES ('raw', 'MB_1_1_breaker_0:0', 100, 400, 50, 450, 10, 500)"
        ))
        await db.commit()
        events_created = await evaluate_sample(
            db, device_id="MB_1_1_breaker_0", register_address=0, raw_value=600
        )
        result = await db.execute(select(Event).where(Event.kind.like("threshold:%")))
        event = result.scalars().first()
    await engine.dispose()
    assert events_created == 1
    assert event is not None
    assert event.severity == "critical"


@pytest.mark.asyncio
async def test_below_low_threshold_creates_event(clean_tables: None) -> None:
    """raw_value < warning_low also creates a warning event."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from tests.conftest import _make_test_engine

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(text(
            "INSERT INTO events.threshold (asset_class, metric, warning_low, warning_high) "
            "VALUES ('raw', 'MB_1_1_breaker_0:0', 100, 500)"
        ))
        await db.commit()
        events_created = await evaluate_sample(
            db, device_id="MB_1_1_breaker_0", register_address=0, raw_value=50
        )
    await engine.dispose()
    assert events_created == 1
