# api/app/core/email.py
from datetime import datetime

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


_SEVERITY_COLORS: dict[str, str] = {
    "warning": "#f6a600",
    "error": "#ff9400",
    "critical": "#f23645",
}


async def send_alarm_email(
    *,
    event_id: int,
    severity: str,
    kind: str,
    message: str,
    ts: datetime,
    recipients: list[str],
) -> None:
    """Send an alarm notification email to a list of recipients.

    Uses Resend for delivery. No-ops when resend_api_key is empty.

    Args:
        event_id: Primary key of the triggering event.
        severity: Alarm severity (warning | error | critical).
        kind: Machine-readable event kind string (e.g. breaker_tripped).
        message: Human-readable alarm description.
        ts: Event UTC timestamp.
        recipients: List of destination email addresses.
    """
    severity_label = severity.upper()
    kind_label = kind.replace("_", " ").upper()
    subject = f"[Kingswalk SCADA] {severity_label}: {kind_label}"
    accent = _SEVERITY_COLORS.get(severity, "#f6a600")
    ts_fmt = ts.strftime("%Y-%m-%d %H:%M:%S UTC")

    html = (
        f'<div style="font-family:\'Courier New\',monospace;max-width:520px;'
        f'background:#0d1218;color:#dde5ed;padding:24px;border-left:3px solid {accent}">'
        f'<p style="color:{accent};font-size:11px;letter-spacing:2px;'
        f'text-transform:uppercase;margin:0 0 8px 0">Kingswalk SCADA — {severity_label}</p>'
        f'<p style="font-size:15px;font-weight:700;color:#dde5ed;margin:0 0 4px 0">'
        f'{kind_label}</p>'
        f'<p style="font-size:13px;color:#8a9fb5;margin:0 0 20px 0">{message}</p>'
        f'<table style="width:100%;font-size:11px;color:#3d5166;border-collapse:collapse">'
        f'<tr><td style="padding:2px 8px 2px 0">Time</td>'
        f'<td style="color:#8a9fb5">{ts_fmt}</td></tr>'
        f'<tr><td style="padding:2px 8px 2px 0">Severity</td>'
        f'<td style="color:{accent}">{severity_label}</td></tr>'
        f'<tr><td style="padding:2px 8px 2px 0">Event #</td>'
        f'<td style="color:#8a9fb5">{event_id}</td></tr></table>'
        f'<p style="margin:20px 0 0 0;font-size:11px;color:#3d5166">'
        f'Log in to <a href="{settings.app_url}" style="color:{accent}">Kingswalk SCADA</a> '
        f'to acknowledge this alarm.</p>'
        f'</div>'
    )

    for to_email in recipients:
        await _send(to_email=to_email, subject=subject, html=html)


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
