# edge/sync.py
"""CloudSync — drains LocalBuffer to the cloud ingest API in 500-row batches."""
from __future__ import annotations

import asyncio

import httpx
import structlog

from edge.buffer import LocalBuffer

log = structlog.get_logger()

_BATCH_SIZE = 500
_BATCH_DELAY_S = 0.1   # 100ms between batches — avoids overwhelming TimescaleDB
_RETRY_DELAY_S = 5.0   # wait after a network error before retrying


class CloudSync:
    """POSTs pending buffer samples to `/api/ingest/batch` in rate-limited batches.

    Rows are marked synced AFTER a successful HTTP 2xx response. If the request
    fails, rows remain pending and are retried on the next flush cycle.
    """

    def __init__(self, buffer: LocalBuffer, cloud_url: str, edge_token: str) -> None:
        self._buffer = buffer
        self._endpoint = cloud_url.rstrip("/") + "/api/ingest/batch"
        self._edge_token = edge_token

    async def run_forever(self) -> None:
        """Continuously drain pending samples. Retries after errors."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            while True:
                try:
                    await self._flush_one_batch(client)
                except Exception:
                    log.exception("sync_error")
                    await asyncio.sleep(_RETRY_DELAY_S)

    async def _flush_one_batch(self, client: httpx.AsyncClient) -> None:
        batch = await self._buffer.take_batch(max_rows=_BATCH_SIZE)
        if not batch:
            await asyncio.sleep(1.0)
            return

        ids = [row[0] for row in batch]
        samples = [row[1].to_dict() for row in batch]

        response = await client.post(
            self._endpoint,
            json={"samples": samples},
            headers={"Authorization": f"Bearer {self._edge_token}"},
        )
        response.raise_for_status()  # raises HTTPStatusError on 4xx/5xx

        await self._buffer.mark_synced(ids)
        log.info("sync_batch_ok", count=len(ids), pending=await self._buffer.pending_count())
        await asyncio.sleep(_BATCH_DELAY_S)
