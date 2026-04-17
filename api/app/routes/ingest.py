"""Telemetry ingest endpoint — edge gateway batch ingest.

Route: POST /ingest/telemetry  (registered under /api/ingest prefix)

Authentication: static ``Authorization: Bearer <EDGE_INGEST_TOKEN>``
header — NOT a user JWT.  This is a machine-to-machine token shared
between the edge gateway and the backend.

For each sample in the batch:
  1. Map ``(raw_value, comms_loss)`` → breaker state string.
  2. Bulk-insert all valid samples into ``telemetry.breaker_state``.
  3. Detect state changes relative to the previous latest reading.
  4. Broadcast ``breaker_update`` (or ``comms_loss``) via ws_manager.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import UUID4, BaseModel, field_validator
from sqlalchemy import text

from app.core.config import settings
from app.db.engine import AsyncSessionLocal
from app.services.ws_manager import ws_manager

logger = structlog.get_logger()

router = APIRouter(tags=["ingest"])


# ── Pydantic models ──────────────────────────────────────────────────────────


class TelemetrySample(BaseModel):
    """A single Modbus register reading from the edge gateway."""

    asset_id: UUID4
    timestamp: datetime
    register: str
    raw_value: int
    comms_loss: bool = False


class TelemetryBatch(BaseModel):
    """Batch payload POSTed by the edge gateway."""

    gateway_id: str
    samples: list[TelemetrySample]

    @field_validator("samples")
    @classmethod
    def samples_not_empty(cls, v: list[TelemetrySample]) -> list[TelemetrySample]:
        if not v:
            raise ValueError("samples must not be empty")
        return v


class IngestResponse(BaseModel):
    accepted: int
    rejected: int


# ── State mapping ─────────────────────────────────────────────────────────────


def _map_state(raw_value: int, comms_loss: bool) -> str:
    """Convert a Modbus raw_value + comms_loss flag to a breaker state string."""
    if comms_loss:
        return "unknown"
    mapping = {1: "closed", 0: "open", 2: "tripped"}
    return mapping.get(raw_value, "unknown")


# ── Auth helper ───────────────────────────────────────────────────────────────


def _verify_ingest_token(authorization: str | None) -> None:
    """Raise 401 if the Authorization header does not carry the expected static token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        token.strip(), settings.edge_ingest_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ingest token",
        )


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.post(
    "/telemetry",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_telemetry(
    batch: TelemetryBatch,
    authorization: Annotated[str | None, Header()] = None,
) -> IngestResponse:
    """Accept a batch of Modbus readings from the edge gateway.

    Only samples whose ``asset_id`` exists in ``assets.breaker`` are
    accepted; unknown asset_ids are silently counted as rejected.
    """
    _verify_ingest_token(authorization)

    accepted = 0
    rejected = 0

    # Filter to "state register" samples only (breaker state channel).
    # The spec uses the register name to distinguish state from PQ/energy.
    # We accept any register for now and map to breaker_state — the
    # gateway is responsible for only POSTing state registers here.

    async with AsyncSessionLocal() as db:
        # ── 1. Resolve valid breaker ids in one query ─────────────────
        asset_ids = list({str(s.asset_id) for s in batch.samples})
        result = await db.execute(
            text(
                "SELECT id::text, label, "
                "       (SELECT mb.code FROM assets.main_board mb "
                "        WHERE mb.id = b.main_board_id) AS main_board_ref "
                "FROM assets.breaker b "
                "WHERE id::text = ANY(:ids) AND deleted_at IS NULL"
            ),
            {"ids": asset_ids},
        )
        valid_breakers: dict[str, dict] = {  # type: ignore[type-arg]
            row["id"]: {"label": row["label"], "main_board_ref": row["main_board_ref"]}
            for row in result.mappings().all()
        }

        # ── 2. Fetch previous latest state for change detection ───────
        if valid_breakers:
            prev_result = await db.execute(
                text(
                    """
                    SELECT DISTINCT ON (breaker_id)
                        breaker_id::text,
                        state
                    FROM telemetry.breaker_state
                    WHERE breaker_id::text = ANY(:ids)
                    ORDER BY breaker_id, ts DESC
                    """
                ),
                {"ids": list(valid_breakers.keys())},
            )
            prev_states: dict[str, str] = {
                row["breaker_id"]: row["state"]
                for row in prev_result.mappings().all()
            }
        else:
            prev_states = {}

        # ── 3. Build bulk insert values ────────────────────────────────
        # telemetry.breaker_state(ts, breaker_id, state, trip_cause, contact_source)
        valid_samples: list[dict] = []  # type: ignore[type-arg]
        comms_loss_detected = False

        for sample in batch.samples:
            sid = str(sample.asset_id)
            if sid not in valid_breakers:
                rejected += 1
                continue

            state = _map_state(sample.raw_value, sample.comms_loss)
            if sample.comms_loss:
                comms_loss_detected = True

            valid_samples.append(
                {
                    "ts": sample.timestamp,
                    "breaker_id": sid,
                    "state": state if state != "unknown" else None,
                    "raw_state": state,
                }
            )
            accepted += 1

        # ── 4. Bulk insert ─────────────────────────────────────────────
        if valid_samples:
            # breaker_state.state has CHECK (state IN ('open','closed','tripped'))
            # so we only insert rows where state is a known value.
            insertable = [
                s for s in valid_samples if s["raw_state"] in ("open", "closed", "tripped")
            ]
            # Rows with comms_loss (state='unknown') are NOT inserted into
            # breaker_state because the table constraint forbids 'unknown'.
            # The comms_loss event is broadcast via WebSocket instead.
            if insertable:
                await db.execute(
                    text(
                        """
                        INSERT INTO telemetry.breaker_state (ts, breaker_id, state)
                        SELECT
                            (value->>'ts')::timestamptz,
                            (value->>'breaker_id')::uuid,
                            (value->>'state')::text
                        FROM jsonb_array_elements(:rows::jsonb) AS value
                        ON CONFLICT (breaker_id, ts) DO NOTHING
                        """
                    ),
                    {
                        "rows": __import__("json").dumps(
                            [
                                {
                                    "ts": s["ts"].isoformat(),
                                    "breaker_id": s["breaker_id"],
                                    "state": s["raw_state"],
                                }
                                for s in insertable
                            ]
                        )
                    },
                )
                await db.commit()

        # ── 5. Detect state changes and broadcast ─────────────────────
        now_iso = datetime.now(UTC).isoformat()

        for sample in valid_samples:
            sid = sample["breaker_id"]
            new_state = sample["raw_state"]
            old_state = prev_states.get(sid)
            meta = valid_breakers[sid]

            if new_state != old_state:
                await ws_manager.broadcast(
                    {
                        "type": "breaker_update",
                        "asset_id": sid,
                        "label": meta["label"],
                        "main_board_ref": meta["main_board_ref"],
                        "state": new_state,
                        "comms_loss": new_state == "unknown",
                        "timestamp": now_iso,
                    }
                )
                logger.info(
                    "breaker.state_change",
                    asset_id=sid,
                    old=old_state,
                    new=new_state,
                )

        # ── 6. Broadcast gateway-level comms loss if needed ───────────
        if comms_loss_detected:
            await ws_manager.broadcast(
                {
                    "type": "comms_loss",
                    "gateway_id": batch.gateway_id,
                    "timestamp": now_iso,
                }
            )

    logger.info(
        "ingest.complete",
        gateway_id=batch.gateway_id,
        accepted=accepted,
        rejected=rejected,
    )
    return IngestResponse(accepted=accepted, rejected=rejected)
