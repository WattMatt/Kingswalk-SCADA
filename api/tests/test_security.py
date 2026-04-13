import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    hash_password,
    verify_password,
)


def test_hash_password_uses_argon2id() -> None:
    hashed = hash_password("mysecretpassword")
    assert hashed.startswith("$argon2id$")
    assert hashed != "mysecretpassword"


def test_verify_password_correct() -> None:
    hashed = hash_password("correct_password")
    assert verify_password("correct_password", hashed) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_returns_false_not_raises_on_wrong() -> None:
    """verify_password must never raise — return False on any failure."""
    assert verify_password("wrong", "$argon2id$invalid_hash") is False


def test_access_token_claims() -> None:
    token = create_access_token(user_id="user-abc", role="admin")
    payload = decode_token(token, expected_aud="access")
    assert payload["sub"] == "user-abc"
    assert payload["role"] == "admin"
    assert payload["aud"] == "access"
    assert payload["iss"] == "kingswalk-scada"
    assert "exp" in payload
    assert "iat" in payload


def test_refresh_token_claims() -> None:
    token = create_refresh_token(user_id="user-abc", session_id="sess-xyz")
    payload = decode_token(token, expected_aud="refresh")
    assert payload["sub"] == "user-abc"
    assert payload["session_id"] == "sess-xyz"
    assert payload["aud"] == "refresh"
    assert payload["iss"] == "kingswalk-scada"


def test_wrong_audience_raises() -> None:
    """An access token presented as a refresh token must be rejected."""
    token = create_access_token(user_id="user-abc", role="operator")
    with pytest.raises(Exception):
        decode_token(token, expected_aud="refresh")


def test_alg_none_rejected() -> None:
    """Tokens with alg:none must be rejected."""
    import jwt as pyjwt

    # Craft a token with alg=none (no signature)
    payload = {"sub": "attacker", "aud": "access", "iss": "kingswalk-scada"}
    none_token = pyjwt.encode(payload, "", algorithm="none")
    with pytest.raises(Exception):
        decode_token(none_token, expected_aud="access")


def test_csrf_token_length() -> None:
    token = generate_csrf_token()
    assert len(token) == 64  # 32 bytes = 64 hex chars


def test_csrf_tokens_are_unique() -> None:
    tokens = {generate_csrf_token() for _ in range(10)}
    assert len(tokens) == 10  # all unique


def test_mfa_pending_token_contains_correct_claims() -> None:
    from app.core.security import create_mfa_pending_token, decode_mfa_pending_token
    token = create_mfa_pending_token(user_id="user-123")
    payload = decode_mfa_pending_token(token)
    assert payload["sub"] == "user-123"
    assert payload["aud"] == "mfa_pending"
    assert payload["iss"] == "kingswalk-scada"


def test_access_token_cannot_be_used_as_mfa_pending() -> None:
    from app.core.security import create_access_token, decode_mfa_pending_token
    token = create_access_token(user_id="user-123", role="operator")
    with pytest.raises(Exception):
        decode_mfa_pending_token(token)
