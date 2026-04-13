# api/tests/test_mfa_repo.py
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.models import User

TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql+asyncpg://scada:scada_dev@localhost:5433/kingswalk_scada_test",
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh engine + session per test — avoids asyncio event loop conflicts."""
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_size=2, max_overflow=0)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE core.recovery_code, core.audit_log, core.session, core.users "
            "RESTART IDENTITY CASCADE"
        ))
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def test_user_id(db_session: AsyncSession) -> uuid.UUID:
    user = User(
        email="mfa-repo-test@test.scada",
        full_name="MFA Repo Test",
        password_hash=hash_password("TestPass123!"),
        role="operator",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


@pytest.mark.asyncio
async def test_generate_recovery_codes_returns_10(
    db_session: AsyncSession, test_user_id: uuid.UUID
) -> None:
    from app.repos.mfa_repo import generate_recovery_codes
    codes = await generate_recovery_codes(db_session, test_user_id)
    assert len(codes) == 10


@pytest.mark.asyncio
async def test_recovery_codes_have_correct_format(
    db_session: AsyncSession, test_user_id: uuid.UUID
) -> None:
    from app.repos.mfa_repo import generate_recovery_codes
    codes = await generate_recovery_codes(db_session, test_user_id)
    for code in codes:
        parts = code.split("-")
        assert len(parts) == 8, f"Expected 8 groups, got {len(parts)} in {code!r}"
        for part in parts:
            assert len(part) == 4, f"Expected 4-char groups, got {len(part)} in {part!r}"


@pytest.mark.asyncio
async def test_verify_and_consume_valid_code(
    db_session: AsyncSession, test_user_id: uuid.UUID
) -> None:
    from app.repos.mfa_repo import generate_recovery_codes, verify_and_consume_recovery_code
    codes = await generate_recovery_codes(db_session, test_user_id)
    result = await verify_and_consume_recovery_code(db_session, test_user_id, codes[0])
    assert result is True


@pytest.mark.asyncio
async def test_recovery_code_single_use(
    db_session: AsyncSession, test_user_id: uuid.UUID
) -> None:
    from app.repos.mfa_repo import generate_recovery_codes, verify_and_consume_recovery_code
    codes = await generate_recovery_codes(db_session, test_user_id)
    await verify_and_consume_recovery_code(db_session, test_user_id, codes[0])
    result = await verify_and_consume_recovery_code(db_session, test_user_id, codes[0])
    assert result is False


@pytest.mark.asyncio
async def test_wrong_code_returns_false(
    db_session: AsyncSession, test_user_id: uuid.UUID
) -> None:
    from app.repos.mfa_repo import generate_recovery_codes, verify_and_consume_recovery_code
    await generate_recovery_codes(db_session, test_user_id)
    result = await verify_and_consume_recovery_code(
        db_session, test_user_id, "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-0000-1111"
    )
    assert result is False


@pytest.mark.asyncio
async def test_generate_codes_invalidates_previous(
    db_session: AsyncSession, test_user_id: uuid.UUID
) -> None:
    from app.repos.mfa_repo import generate_recovery_codes, verify_and_consume_recovery_code
    old_codes = await generate_recovery_codes(db_session, test_user_id)
    _new_codes = await generate_recovery_codes(db_session, test_user_id)
    result = await verify_and_consume_recovery_code(db_session, test_user_id, old_codes[0])
    assert result is False
