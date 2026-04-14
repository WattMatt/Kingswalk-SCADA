# api/app/core/email.py
import httpx

from app.core.config import settings

_RESEND_API_URL = "https://api.resend.com/emails"
_FROM_ADDRESS = "Kingswalk SCADA <noreply@kingswalk.scada>"


async def send_invite_email(to_email: str, invite_token: str) -> None:
    """Send an onboarding invite link. No-ops when resend_api_key is empty."""
    invite_url = f"{settings.app_url}/onboard?token={invite_token}"
    await _send(
        to_email=to_email,
        subject="You're invited to Kingswalk SCADA",
        html=(
            f"<p>You have been invited to access the Kingswalk SCADA monitoring system.</p>"
            f'<p><a href="{invite_url}">Accept invitation</a></p>'
            f"<p>This link expires in 48 hours.</p>"
        ),
    )


async def send_password_reset_email(to_email: str, reset_token: str) -> None:
    """Send a password reset link. No-ops when resend_api_key is empty."""
    reset_url = f"{settings.app_url}/reset-password?token={reset_token}"
    await _send(
        to_email=to_email,
        subject="Kingswalk SCADA — Password Reset",
        html=(
            f"<p>A password reset was requested for your account.</p>"
            f'<p><a href="{reset_url}">Reset password</a></p>'
            f"<p>This link expires in 1 hour. If you did not request this, ignore this email.</p>"
        ),
    )


async def _send(to_email: str, subject: str, html: str) -> None:
    """Internal: POST to Resend API. Skipped if resend_api_key is empty."""
    if not settings.resend_api_key:
        return
    async with httpx.AsyncClient() as client:
        response = await client.post(
            _RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": _FROM_ADDRESS, "to": [to_email], "subject": subject, "html": html},
            timeout=10.0,
        )
        response.raise_for_status()
