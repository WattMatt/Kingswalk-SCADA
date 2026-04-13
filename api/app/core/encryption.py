# api/app/core/encryption.py
"""AES-256-GCM encryption for TOTP secrets stored in the database.

Key loaded from MFA_ENCRYPTION_KEY env var (base64-encoded 32 bytes).
Stored format: 'v1:<base64(12-byte-nonce || ciphertext || 16-byte-tag)>'
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_key() -> bytes:
    """Load and validate the AES-256-GCM key from environment."""
    raw = os.environ.get("MFA_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError("MFA_ENCRYPTION_KEY environment variable is not set")
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        raise RuntimeError("MFA_ENCRYPTION_KEY is not valid base64") from exc
    if len(key) != 32:
        raise RuntimeError(
            f"MFA_ENCRYPTION_KEY must decode to exactly 32 bytes, got {len(key)}"
        )
    return key


def encrypt_mfa_secret(plaintext: str) -> str:
    """Encrypt a TOTP secret with AES-256-GCM.

    Returns a string in the format: 'v1:<base64(nonce || ciphertext || tag)>'
    The 12-byte nonce is randomly generated per call.
    """
    key = _get_key()
    nonce = os.urandom(12)  # 96-bit nonce — GCM recommendation
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode(), None)
    payload = base64.b64encode(nonce + ciphertext_with_tag).decode()
    return f"v1:{payload}"


def decrypt_mfa_secret(encrypted: str) -> str:
    """Decrypt a TOTP secret produced by encrypt_mfa_secret.

    Raises ValueError for unsupported version prefix.
    Raises cryptography.exceptions.InvalidTag if ciphertext was tampered.
    """
    if not encrypted.startswith("v1:"):
        raise ValueError(f"Unsupported encryption version in: {encrypted[:10]!r}")
    payload = base64.b64decode(encrypted[3:])
    nonce = payload[:12]
    ciphertext_with_tag = payload[12:]
    key = _get_key()
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext_with_tag, None).decode()
