# api/app/routes/ingest.py
"""POST /api/ingest/batch — receives raw telemetry batches from the edge gateway.

Auth: static edge API key via Authorization: Bearer header.
The key is set in settings.edge_api_key (from EDGE_API_KEY env var).
"""
from __future__ import annotations

import secrets
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.engine import get_db
from app.services import ingest_service

log = structlog.get_logger()

ingest_router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _verify_edge_key(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dependency: verify Authorization: Bearer {edge_api_key}."""
    if not settings.edge_api_key:
        # Edge API key not configured — reject all requests. Prevents accidentally
        # accepting ingest traffic on a node where the key was never set.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="edge_api_key not configured",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    token = authorization.removeprefix("Bearer ")
    # Constant-time comparison prevents timing-based token enumeration.
    if not secrets.compare_digest(token, settings.edge_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid edge token",
        )


class SampleIn(BaseModel):
    device_id: str
    register_address: int
    raw_value: int
    sampled_at: datetime


class BatchIn(BaseModel):
    # 500 rows/batch matches edge CloudSync batch size; cap prevents memory exhaustion
    # from malformed or compromised edge gateways.
    samples: list[SampleIn] = Field(default=[], max_length=500)


class BatchOut(BaseModel):
    accepted: int


@ingest_router.post("/batch", response_model=BatchOut, dependencies=[Depends(_verify_edge_key)])
async def ingest_batch(
    body: BatchIn,
    db: AsyncSession = Depends(get_db),
) -> BatchOut:
    """Receive a batch of raw telemetry samples from the edge gateway.

    Idempotent: duplicate (device_id, register_address, ts) rows are silently dropped.
    After storing, evaluates threshold rules and publishes live updates to Redis.
    """
    accepted = await ingest_service.handle_batch(db, body.samples)
    return BatchOut(accepted=accepted)
