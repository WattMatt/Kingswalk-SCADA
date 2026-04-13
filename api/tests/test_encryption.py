# api/tests/test_encryption.py
import base64

import pytest


@pytest.fixture(autouse=True)
def set_mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a valid 32-byte base64 MFA key for every test in this module."""
    key = base64.b64encode(b"\x00" * 32).decode()
    monkeypatch.setenv("MFA_ENCRYPTION_KEY", key)


def test_encrypt_returns_v1_prefix() -> None:
    from app.core.encryption import encrypt_mfa_secret
    result = encrypt_mfa_secret("JBSWY3DPEHPK3PXP")
    assert result.startswith("v1:")


def test_encrypt_decrypt_roundtrip() -> None:
    from app.core.encryption import decrypt_mfa_secret, encrypt_mfa_secret
    plaintext = "JBSWY3DPEHPK3PXP"
    encrypted = encrypt_mfa_secret(plaintext)
    assert decrypt_mfa_secret(encrypted) == plaintext


def test_two_encryptions_differ() -> None:
    """AES-256-GCM uses a random nonce — two encryptions of the same plaintext differ."""
    from app.core.encryption import encrypt_mfa_secret
    plaintext = "JBSWY3DPEHPK3PXP"
    assert encrypt_mfa_secret(plaintext) != encrypt_mfa_secret(plaintext)


def test_tampered_ciphertext_raises() -> None:
    """GCM tag validation must reject tampered ciphertext."""
    from app.core.encryption import decrypt_mfa_secret, encrypt_mfa_secret
    encrypted = encrypt_mfa_secret("secret")
    prefix, payload_b64 = encrypted.split(":", 1)
    payload = bytearray(base64.b64decode(payload_b64))
    payload[-1] ^= 0xFF  # flip last byte of the GCM tag
    tampered = f"{prefix}:{base64.b64encode(bytes(payload)).decode()}"
    with pytest.raises(Exception):
        decrypt_mfa_secret(tampered)


def test_wrong_version_prefix_raises() -> None:
    from app.core.encryption import decrypt_mfa_secret
    with pytest.raises(ValueError, match="Unsupported"):
        decrypt_mfa_secret("v2:somedata")
