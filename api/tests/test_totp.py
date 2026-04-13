# api/tests/test_totp.py
import pyotp

from app.core.totp import generate_totp_secret, get_provisioning_uri, verify_totp


def test_generate_secret_is_valid_base32() -> None:
    secret = generate_totp_secret()
    assert len(secret) == 32
    # Must be valid base32 — pyotp.TOTP should not raise
    pyotp.TOTP(secret).now()  # no exception = valid


def test_provisioning_uri_format() -> None:
    secret = generate_totp_secret()
    uri = get_provisioning_uri(secret, "operator@test.scada")
    assert uri.startswith("otpauth://totp/")
    assert "Kingswalk" in uri


def test_verify_totp_correct_code() -> None:
    secret = generate_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, code) is True


def test_verify_totp_rejects_clearly_invalid_code() -> None:
    secret = generate_totp_secret()
    assert verify_totp(secret, "abcdef") is False  # non-digit


def test_verify_totp_rejects_empty_code() -> None:
    secret = generate_totp_secret()
    assert verify_totp(secret, "") is False
