# api/tests/test_mfa.py
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_enroll_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/auth/mfa/enroll")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_enroll_returns_provisioning_uri(client: AsyncClient, operator_user: dict) -> None:
    await client.post("/auth/login", json={
        "email": operator_user["email"],
        "password": operator_user["password"],
    })
    response = await client.post("/auth/mfa/enroll")
    assert response.status_code == 200
    body = response.json()
    assert "provisioning_uri" in body
    assert body["provisioning_uri"].startswith("otpauth://totp/")


@pytest.mark.asyncio
async def test_confirm_enrollment_wrong_code_returns_401(
    client: AsyncClient, operator_user: dict
) -> None:
    await client.post("/auth/login", json={
        "email": operator_user["email"],
        "password": operator_user["password"],
    })
    await client.post("/auth/mfa/enroll")
    response = await client.post("/auth/mfa/confirm-enrollment", json={"code": "000000"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_confirm_enrollment_correct_code_returns_recovery_codes(
    client: AsyncClient, operator_user: dict
) -> None:
    await client.post("/auth/login", json={
        "email": operator_user["email"],
        "password": operator_user["password"],
    })
    enroll_resp = await client.post("/auth/mfa/enroll")
    uri = enroll_resp.json()["provisioning_uri"]
    parsed = urlparse(uri)
    secret = parse_qs(parsed.query)["secret"][0]
    code = pyotp.TOTP(secret).now()

    response = await client.post("/auth/mfa/confirm-enrollment", json={"code": code})
    assert response.status_code == 200
    body = response.json()
    assert "recovery_codes" in body
    codes = body["recovery_codes"]
    assert len(codes) == 10
    for c in codes:
        parts = c.split("-")
        assert len(parts) == 8


@pytest.mark.asyncio
async def test_mfa_login_returns_mfa_required(client: AsyncClient, mfa_operator: dict) -> None:
    response = await client.post("/auth/login", json={
        "email": mfa_operator["email"],
        "password": mfa_operator["password"],
    })
    assert response.status_code == 200
    body = response.json()
    assert body.get("mfa_required") is True
    assert "access_token" not in response.cookies
    assert "mfa_pending" in response.cookies


@pytest.mark.asyncio
async def test_mfa_verify_with_correct_totp_issues_tokens(
    client: AsyncClient, mfa_operator: dict
) -> None:
    await client.post("/auth/login", json={
        "email": mfa_operator["email"],
        "password": mfa_operator["password"],
    })
    code = pyotp.TOTP(mfa_operator["totp_secret"]).now()
    response = await client.post("/auth/mfa/verify", json={"code": code})
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "mfa_pending" not in response.cookies


@pytest.mark.asyncio
async def test_mfa_verify_wrong_code_returns_401(
    client: AsyncClient, mfa_operator: dict
) -> None:
    await client.post("/auth/login", json={
        "email": mfa_operator["email"],
        "password": mfa_operator["password"],
    })
    response = await client.post("/auth/mfa/verify", json={"code": "000000"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mfa_recovery_code_issues_tokens(
    client: AsyncClient, mfa_operator: dict
) -> None:
    await client.post("/auth/login", json={
        "email": mfa_operator["email"],
        "password": mfa_operator["password"],
    })
    code = mfa_operator["recovery_codes"][0]
    response = await client.post("/auth/mfa/recovery", json={"code": code})
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "mfa_pending" not in response.cookies


@pytest.mark.asyncio
async def test_mfa_recovery_code_single_use(
    client: AsyncClient, mfa_operator: dict
) -> None:
    code = mfa_operator["recovery_codes"][1]
    await client.post("/auth/login", json={
        "email": mfa_operator["email"],
        "password": mfa_operator["password"],
    })
    resp1 = await client.post("/auth/mfa/recovery", json={"code": code})
    assert resp1.status_code == 200
    await client.post("/auth/logout")
    await client.post("/auth/login", json={
        "email": mfa_operator["email"],
        "password": mfa_operator["password"],
    })
    resp2 = await client.post("/auth/mfa/recovery", json={"code": code})
    assert resp2.status_code == 401
