from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok", "version": settings.version}
