from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthError(AppError):
    """Authentication or authorisation failure."""

    def __init__(self, message: str = "Unauthorised") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status_code=404)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError into a consistent JSON error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )
