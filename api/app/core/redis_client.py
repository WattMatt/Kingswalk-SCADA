# api/app/core/redis_client.py
from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    """Return the shared async Redis connection. Call close_redis() on shutdown."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Close the shared Redis connection. Called from application shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
