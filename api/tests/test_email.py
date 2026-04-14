# api/tests/test_email.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import email as email_module
from app.core.config import settings


async def test_send_invite_email_skipped_when_no_api_key(monkeypatch):
    """When resend_api_key is empty, no HTTP call is made."""
    monkeypatch.setattr(settings, "resend_api_key", "")
    with patch("httpx.AsyncClient") as mock_client_cls:
        await email_module.send_invite_email("user@example.com", "raw_token_123")
        mock_client_cls.assert_not_called()


async def test_send_invite_email_calls_resend_api(monkeypatch):
    """When resend_api_key is set, POST to Resend API with correct headers."""
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "app_url", "https://app.example.com")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=mock_response)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        await email_module.send_invite_email("user@example.com", "raw_token_123")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    body = call_kwargs.kwargs["json"]
    assert body["to"] == ["user@example.com"]
    assert "raw_token_123" in body["html"]


async def test_send_password_reset_email_calls_resend_api(monkeypatch):
    """Password reset email includes token in the HTML body."""
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "app_url", "https://app.example.com")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=mock_response)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        await email_module.send_password_reset_email("user@example.com", "reset_token_abc")

    body = mock_post.call_args.kwargs["json"]
    assert body["to"] == ["user@example.com"]
    assert "reset_token_abc" in body["html"]
