import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import AppError, app_error_handler
from app.core.logging import configure_logging
from app.core.redis_client import close_redis, get_redis
from app.routes.admin import admin_router
from app.routes.assets import assets_router
from app.routes.auth import router as auth_router
from app.routes.events import events_router
from app.routes.health import router as health_router
from app.routes.ingest import router as ingest_router
from app.routes.mfa import router as mfa_router
from app.routes.telemetry import telemetry_router
from app.routes.ws import router as ws_router
from app.services import watchdog_service
from app.services.notification_service import escalation_loop
from app.ws.router import ws_router as ws_live_router

configure_logging(settings.log_level)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle."""
    logger.info("startup", environment=settings.environment, version=settings.version)
    await get_redis()  # Warm the singleton; prevents race at first concurrent ingest request
    watchdog_task = asyncio.create_task(watchdog_service.watchdog_loop())
    escalation_task = asyncio.create_task(escalation_loop())
    yield
    watchdog_task.cancel()
    escalation_task.cancel()
    for task in (watchdog_task, escalation_task):
        try:
            await task
        except asyncio.CancelledError:
            pass
    await close_redis()
    logger.info("shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Kingswalk SCADA API",
        version=settings.version,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment == "development" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response: Response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response

    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(mfa_router)
    app.include_router(admin_router)
    app.include_router(ingest_router, prefix="/api/ingest")
    app.include_router(assets_router)
    app.include_router(events_router)
    app.include_router(telemetry_router)
    app.include_router(ws_router, prefix="/api")   # /api/ws — simple breaker snapshot
    app.include_router(ws_live_router)              # /ws/live — Redis pub/sub full-sync

    return app


app = create_app()
