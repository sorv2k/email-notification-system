"""Tests for the Resend email service."""
from unittest.mock import patch

import pytest

from app.services.email import send_email


@pytest.mark.asyncio
async def test_send_email_success(mock_sendgrid):
    """send_email should call Resend client and not raise on success."""
    await send_email("user@example.com", "Hello", "World")
    mock_sendgrid.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_failure_raises(mock_sendgrid):
    """send_email should propagate exceptions from the Resend client."""
    mock_sendgrid.send.side_effect = Exception("Network error")

    with pytest.raises(Exception, match="Network error"):
        await send_email("user@example.com", "Hello", "World")


@pytest.mark.asyncio
async def test_send_email_correct_payload(mock_sendgrid):
    """send_email passes recipient, subject, body to Resend."""
    await send_email("recipient@example.com", "My Subject", "My Body")

    call_args = mock_sendgrid.send.call_args
    params = call_args[0][0]
    assert params["to"] == ["recipient@example.com"]
    assert params["subject"] == "My Subject"
    assert params["text"] == "My Body"
