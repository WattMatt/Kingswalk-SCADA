# api/tests/test_notification_service.py
"""Unit tests for notification_service and send_alarm_email.

The conftest fake_redis fixture is autouse=True — all tests here
already have an in-memory Redis via rc._redis without explicitly
requesting the fixture.
"""
from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notification_service import (
    _ESCALATION_KEY_PREFIX,
    _ESCALATION_TIMEOUT_SEC,
    _process_escalations,
    _register_escalation,
    cancel_escalation,
    notify_new_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_id: int = 1,
    severity: str = "critical",
    kind: str = "breaker_tripped",
    message: str = "CB-01 tripped",
    ts: datetime | None = None,
) -> Any:
    """Build a mock Event object."""
    event = MagicMock()
    event.id = event_id
    event.severity = severity
    event.kind = kind
    event.message = message
    event.ts = ts or datetime.now(UTC)
    return event


def _make_db(emails: list[str] | None = None) -> Any:
    """Return a mock AsyncSession that yields a list of email addresses."""
    db = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = emails if emails is not None else ["op@kw.test"]
    result = MagicMock()
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _close_coro_task(*args: Any, **kwargs: Any) -> MagicMock:
    """Side-effect for mocked asyncio.create_task: close dangling coroutines."""
    for arg in args:
        if inspect.iscoroutine(arg):
            arg.close()
    return MagicMock()


# ---------------------------------------------------------------------------
# notify_new_event — severity filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_skips_info_severity() -> None:
    """info events must not trigger any notification logic."""
    db = _make_db()
    event = _make_event(severity="info")

    with patch("app.services.notification_service._get_notification_recipients") as mock_get:
        await notify_new_event(db, event)
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_notify_creates_task_for_critical() -> None:
    """Critical events should schedule an email task."""
    db = _make_db(["admin@kw.test", "op@kw.test"])
    event = _make_event(severity="critical")

    with patch("asyncio.create_task", side_effect=_close_coro_task) as mock_task:
        await notify_new_event(db, event)

    assert mock_task.called, "asyncio.create_task should be called for a critical event"


@pytest.mark.asyncio
async def test_notify_creates_task_for_warning() -> None:
    """Warning events are in the email tier."""
    db = _make_db(["op@kw.test"])
    event = _make_event(severity="warning")

    with patch("asyncio.create_task", side_effect=_close_coro_task) as mock_task:
        await notify_new_event(db, event)

    assert mock_task.called


@pytest.mark.asyncio
async def test_notify_no_task_when_no_recipients() -> None:
    """No email task should be created when there are no operators or admins."""
    db = _make_db(emails=[])
    event = _make_event(severity="error")

    with patch("asyncio.create_task", side_effect=_close_coro_task) as mock_task:
        await notify_new_event(db, event)

    mock_task.assert_not_called()


# ---------------------------------------------------------------------------
# notify_new_event — escalation registration (via fake Redis)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_registers_escalation_in_redis(fake_redis: Any) -> None:
    """notify_new_event should write an escalation key to Redis."""
    db = _make_db()
    event = _make_event(event_id=99, severity="critical")

    with patch("asyncio.create_task", side_effect=_close_coro_task):
        await notify_new_event(db, event)

    raw = await fake_redis.get(f"{_ESCALATION_KEY_PREFIX}99")
    assert raw is not None, "Escalation key should exist in Redis"
    data = json.loads(raw)
    assert data["event_id"] == 99
    assert data["severity"] == "critical"


# ---------------------------------------------------------------------------
# cancel_escalation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_escalation_removes_redis_key(fake_redis: Any) -> None:
    """cancel_escalation should delete the Redis key for the given event."""
    key = f"{_ESCALATION_KEY_PREFIX}42"
    payload = json.dumps(
        {"event_id": 42, "created_at": datetime.now(UTC).isoformat(), "severity": "error"}
    )
    await fake_redis.set(key, payload)

    await cancel_escalation(42)

    result = await fake_redis.get(key)
    assert result is None, "Key should be deleted after cancel"


@pytest.mark.asyncio
async def test_cancel_escalation_tolerates_missing_key(fake_redis: Any) -> None:
    """Cancelling a non-existent key should not raise."""
    await cancel_escalation(9999)  # No such key — must not raise


# ---------------------------------------------------------------------------
# _register_escalation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_escalation_writes_correct_fields(fake_redis: Any) -> None:
    """_register_escalation stores event_id, severity, and created_at in Redis."""
    ts = datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC)
    event = _make_event(event_id=7, severity="warning", ts=ts)

    await _register_escalation(event)

    raw = await fake_redis.get(f"{_ESCALATION_KEY_PREFIX}7")
    assert raw is not None
    data = json.loads(raw)
    assert data["event_id"] == 7
    assert data["severity"] == "warning"
    assert "2026-04-17" in data["created_at"]


@pytest.mark.asyncio
async def test_register_escalation_sets_ttl(fake_redis: Any) -> None:
    """The Redis key should have a TTL larger than the escalation timeout."""
    event = _make_event(event_id=8, severity="error")

    await _register_escalation(event)

    ttl = await fake_redis.ttl(f"{_ESCALATION_KEY_PREFIX}8")
    assert ttl > _ESCALATION_TIMEOUT_SEC


# ---------------------------------------------------------------------------
# _process_escalations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_escalations_fires_tier2_for_old_entry(fake_redis: Any) -> None:
    """A stale escalation entry (created in 2000) must trigger tier-2."""
    old_ts = datetime(2000, 1, 1, tzinfo=UTC)
    key = f"{_ESCALATION_KEY_PREFIX}5"
    await fake_redis.set(key, json.dumps({
        "event_id": 5,
        "created_at": old_ts.isoformat(),
        "severity": "critical",
    }))

    _tier2_path = "app.services.notification_service._fire_tier2"
    with patch(_tier2_path, new_callable=AsyncMock) as mock_fire:
        await _process_escalations()

    mock_fire.assert_awaited_once()
    fired_event_id = mock_fire.call_args[0][0]
    assert fired_event_id == 5

    # Key must be deleted after escalation fires
    assert await fake_redis.get(key) is None


@pytest.mark.asyncio
async def test_process_escalations_skips_recent_entry(fake_redis: Any) -> None:
    """A freshly-created entry must NOT trigger tier-2."""
    now_ts = datetime.now(UTC)
    key = f"{_ESCALATION_KEY_PREFIX}6"
    await fake_redis.set(key, json.dumps({
        "event_id": 6,
        "created_at": now_ts.isoformat(),
        "severity": "warning",
    }))

    _tier2_path = "app.services.notification_service._fire_tier2"
    with patch(_tier2_path, new_callable=AsyncMock) as mock_fire:
        await _process_escalations()

    mock_fire.assert_not_awaited()
    # Key must still exist
    assert await fake_redis.get(key) is not None


@pytest.mark.asyncio
async def test_process_escalations_deletes_malformed_key(fake_redis: Any) -> None:
    """Malformed JSON in an escalation key must be silently cleaned up."""
    key = f"{_ESCALATION_KEY_PREFIX}bad"
    await fake_redis.set(key, "NOT_JSON")

    _tier2_path = "app.services.notification_service._fire_tier2"
    with patch(_tier2_path, new_callable=AsyncMock) as mock_fire:
        await _process_escalations()  # Must not raise

    mock_fire.assert_not_awaited()
    assert await fake_redis.get(key) is None


# ---------------------------------------------------------------------------
# send_alarm_email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_alarm_email_noops_without_api_key() -> None:
    """send_alarm_email must be a no-op when resend_api_key is empty."""
    from app.core.email import send_alarm_email

    with patch("app.core.email.settings") as mock_settings:
        mock_settings.resend_api_key = ""
        # Should complete without network activity
        await send_alarm_email(
            event_id=1,
            severity="critical",
            kind="breaker_tripped",
            message="Test alarm",
            ts=datetime.now(UTC),
            recipients=["test@kw.test"],
        )


@pytest.mark.asyncio
async def test_send_alarm_email_calls_send_per_recipient() -> None:
    """send_alarm_email should call _send exactly once per recipient."""
    from app.core.email import send_alarm_email

    with (
        patch("app.core.email.settings") as mock_settings,
        patch("app.core.email._send", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.resend_api_key = "re_test"
        mock_settings.app_url = "http://localhost:5173"
        await send_alarm_email(
            event_id=2,
            severity="warning",
            kind="voltage_out_of_range",
            message="L1 247V",
            ts=datetime.now(UTC),
            recipients=["a@kw.test", "b@kw.test"],
        )

    assert mock_send.await_count == 2


@pytest.mark.asyncio
async def test_send_alarm_email_subject_includes_severity_and_kind() -> None:
    """The email subject should contain the severity label and kind."""
    from app.core.email import send_alarm_email

    subjects: list[str] = []

    async def capture_send(to_email: str, subject: str, html: str) -> None:
        subjects.append(subject)

    with (
        patch("app.core.email.settings") as mock_settings,
        patch("app.core.email._send", side_effect=capture_send),
    ):
        mock_settings.resend_api_key = "re_test"
        mock_settings.app_url = "http://localhost:5173"
        await send_alarm_email(
            event_id=3,
            severity="critical",
            kind="breaker_tripped",
            message="Trip alarm",
            ts=datetime.now(UTC),
            recipients=["admin@kw.test"],
        )

    assert subjects, "Expected at least one email"
    subject = subjects[0]
    assert "CRITICAL" in subject
    assert "BREAKER TRIPPED" in subject
