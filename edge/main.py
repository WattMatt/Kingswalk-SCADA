# edge/main.py
"""Entry point for the Kingswalk SCADA edge gateway service.

Wires up:
  - 9 MbPoller instances (one per VLAN)
  - CloudSync worker
  - Health HTTP endpoint (GET /health → JSON)
  - systemd sd_notify watchdog (if available)

Configuration via environment variables — see edge.env.example.
"""
from __future__ import annotations

import asyncio
import os

import structlog
from aiohttp import web

from edge.buffer import LocalBuffer
from edge.poller import MbConfig, MbPoller
from edge.sync import CloudSync

log = structlog.get_logger()

# 9 main boards — IPs are VLAN-specific; configure via environment variables.
# Defaults are illustrative only and must be updated for the site network.
_MB_CONFIGS: list[MbConfig] = [
    MbConfig(mb_id="MB_1_1", host=os.getenv("MB_1_1_HOST", "10.10.11.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_2_1", host=os.getenv("MB_2_1_HOST", "10.10.21.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_2_2", host=os.getenv("MB_2_2_HOST", "10.10.22.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_2_3", host=os.getenv("MB_2_3_HOST", "10.10.23.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_3_1", host=os.getenv("MB_3_1_HOST", "10.10.31.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_4_1", host=os.getenv("MB_4_1_HOST", "10.10.41.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_5_1", host=os.getenv("MB_5_1_HOST", "10.10.51.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_5_2", host=os.getenv("MB_5_2_HOST", "10.10.52.10")),   # TODO: VERIFY_REGISTER host
    MbConfig(mb_id="MB_5_3", host=os.getenv("MB_5_3_HOST", "10.10.53.10")),   # TODO: VERIFY_REGISTER host
]


async def _health_handler(request: web.Request) -> web.Response:
    pollers: list[MbPoller] = request.app["pollers"]
    buffer: LocalBuffer = request.app["buffer"]
    return web.json_response(
        {
            "status": "ok",
            "pollers": [
                {
                    "mb_id": p.mb_id,
                    "last_poll": p.last_poll.isoformat() if p.last_poll else None,
                    "comms_loss": p.comms_loss,
                }
                for p in pollers
            ],
            "buffer_depth": await buffer.pending_count(),
        }
    )


async def _run_health_server(app: web.Application, port: int) -> None:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("health_server_started", port=port)
    # Keep alive — this task runs until cancelled
    while True:
        await asyncio.sleep(3600)


async def _watchdog() -> None:
    """Send sd_notify watchdog keepalive every 10s."""
    try:
        import sdnotify  # type: ignore[import]

        n = sdnotify.SystemdNotifier()
        n.notify("READY=1")
        log.info("systemd_ready_notified")
        while True:
            n.notify("WATCHDOG=1")
            await asyncio.sleep(10)
    except ImportError:
        log.info("sdnotify_not_available_skipping_watchdog")
        while True:
            await asyncio.sleep(3600)


async def main() -> None:
    buffer_path = os.getenv("EDGE_BUFFER_PATH", "edge_buffer.db")
    cloud_url = os.environ["CLOUD_URL"]       # required — no default
    edge_token = os.environ["EDGE_TOKEN"]     # required — no default
    health_port = int(os.getenv("HEALTH_PORT", "9090"))

    buffer = LocalBuffer(db_path=buffer_path)
    await buffer.initialise()
    log.info("buffer_initialised", path=buffer_path)

    pollers = [MbPoller(cfg, buffer) for cfg in _MB_CONFIGS]
    cloud_sync = CloudSync(buffer=buffer, cloud_url=cloud_url, edge_token=edge_token)

    health_app = web.Application()
    health_app["pollers"] = pollers
    health_app["buffer"] = buffer
    health_app.router.add_get("/health", _health_handler)

    async with asyncio.TaskGroup() as tg:
        for poller in pollers:
            tg.create_task(poller.start())
        tg.create_task(cloud_sync.run_forever())
        tg.create_task(_run_health_server(health_app, health_port))
        tg.create_task(_watchdog())


if __name__ == "__main__":
    asyncio.run(main())
