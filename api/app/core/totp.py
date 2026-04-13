# api/app/core/totp.py
"""TOTP (Time-based One-Time Password) operations using pyotp.

RFC 6238 — SHA1, 6 digits, 30-second window.
Issuer: "Kingswalk SCADA" (shown in authenticator app).
Window: ±1 period (allows for ~30s clock skew).
"""
import pyotp

_ISSUER = "Kingswalk SCADA"
_VALID_WINDOW = 1  # ±1 period tolerance for clock skew


def generate_totp_secret() -> str:
    """Generate a new cryptographically random TOTP secret (base32, 32 chars / 20 bytes)."""
    return pyotp.random_base32(length=32)


def get_provisioning_uri(secret: str, email: str) -> str:
    """Return the otpauth:// URI for QR code rendering.

    The frontend renders this as a QR code using a JS library.
    Format: otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}
    """
    return pyotp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name=_ISSUER,
    )


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against a base32 secret.

    Returns False for any invalid input (wrong code, non-digit code, empty string).
    Never raises.
    """
    if not code or not code.isdigit() or len(code) != 6:
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(code, valid_window=_VALID_WINDOW))
    except Exception:
        return False
