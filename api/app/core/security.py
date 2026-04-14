import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from app.core.config import settings

# argon2id: m=65536 KiB, t=3 iterations, p=4 parallelism (OWASP recommended, SPEC §C.1)
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id. Never store plaintext passwords."""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a plaintext password against an argon2id hash.

    Returns False on any failure — never raises. This prevents timing attacks
    where an exception path could be faster than a successful verify.
    """
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False
    except Exception:  # noqa: BLE001
        return False


def _make_token(payload: dict[str, object], ttl_seconds: int) -> str:
    """Sign a JWT with HS256 and standard claims. Internal use only."""
    now = datetime.now(UTC)
    payload = {
        **payload,
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_access_token(user_id: str, role: str) -> str:
    """Create a 15-minute access token (aud: access)."""
    return _make_token(
        {"sub": user_id, "role": role, "aud": "access"},
        settings.access_token_ttl_seconds,
    )


def create_refresh_token(user_id: str, session_id: str) -> str:
    """Create a 7-day refresh token (aud: refresh). Hash before storing in DB."""
    return _make_token(
        {"sub": user_id, "session_id": session_id, "aud": "refresh"},
        settings.refresh_token_ttl_seconds,
    )


def create_mfa_pending_token(user_id: str) -> str:
    """Create a 5-minute MFA-pending token (aud: mfa_pending).

    Issued after successful password check for MFA-enabled users.
    Client must exchange this for full tokens via POST /auth/mfa/verify.
    """
    return _make_token(
        {"sub": user_id, "aud": "mfa_pending"},
        ttl_seconds=300,  # 5 minutes
    )


def decode_mfa_pending_token(token: str) -> dict[str, object]:
    """Decode and validate an mfa_pending token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        audience="mfa_pending",
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iss", "aud", "iat"]},
    )


def decode_token(token: str, expected_aud: str) -> dict[str, object]:
    """
    Decode and fully validate a JWT.

    Validates: signature, exp, iss, aud. Rejects alg:none via explicit whitelist.
    Raises jwt.PyJWTError (or subclass) on any validation failure.
    """
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],  # Explicit whitelist — rejects alg:none
        audience=expected_aud,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iss", "aud", "iat"]},
    )


def create_invite_token(invite_id: str, email: str, role: str) -> str:
    """Create a 48-hour invite JWT (aud: invite).

    The raw JWT string is stored SHA-256 hashed in the DB (token_hash column)
    to allow revocation lookup without storing the plaintext token.
    """
    return _make_token(
        {"sub": invite_id, "email": email, "role": role, "aud": "invite"},
        ttl_seconds=172800,  # 48 hours
    )


def decode_invite_token(token: str) -> dict[str, object]:
    """Decode and validate an invite JWT. Raises jwt.PyJWTError on any failure."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        audience="invite",
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iss", "aud", "iat", "sub"]},
    )


def generate_csrf_token() -> str:
    """Generate a cryptographically secure 32-byte CSRF token (64 hex chars)."""
    return secrets.token_hex(32)
