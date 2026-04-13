# api/app/core/cookies.py
"""Cookie helpers shared by auth and MFA route handlers."""
from fastapi import Response


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    *,
    csrf_token: str,
) -> None:
    """Set HttpOnly auth cookies on the response.

    access_token  — HttpOnly, Secure, SameSite=Strict, path=/
    refresh_token — HttpOnly, Secure, SameSite=Strict, path=/auth/refresh
    csrf_token    — NOT HttpOnly (must be readable by JS for double-submit), Secure, SameSite=Strict
    """
    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=True, samesite="strict", max_age=900,
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=True, samesite="strict",
        path="/auth/refresh", max_age=604800,
    )
    response.set_cookie(
        "csrf_token", csrf_token,
        httponly=False, secure=True, samesite="strict", max_age=900,
    )
