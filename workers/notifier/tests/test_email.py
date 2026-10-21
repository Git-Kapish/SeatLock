"""Unit tests for the EmailAdapter SMTP dispatcher."""

from unittest.mock import AsyncMock, patch

import pytest

from app.email import EmailAdapter


@pytest.mark.asyncio
async def test_send_email_success() -> None:
    """Verifies that email is properly formatted and dispatched via aiosmtplib."""
    adapter = EmailAdapter(
        smtp_host="localhost",
        smtp_port=1025,
        default_sender="test@ticketrush.dev",
    )

    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        result = await adapter.send_email(
            to_email="attendee@example.com",
            subject="Order Receipt",
            body_text="Plain text body",
            body_html="<p>HTML body</p>",
        )

        assert result is True
        mock_send.assert_awaited_once()
        msg_arg = mock_send.await_args.args[0]
        assert msg_arg["To"] == "attendee@example.com"
        assert msg_arg["From"] == "test@ticketrush.dev"
        assert msg_arg["Subject"] == "Order Receipt"


@pytest.mark.asyncio
async def test_send_email_failure_raises() -> None:
    """Verifies that SMTP delivery exceptions are re-raised for caller error handling."""
    adapter = EmailAdapter()

    with (
        patch("aiosmtplib.send", side_effect=ConnectionRefusedError("SMTP down")),
        pytest.raises(ConnectionRefusedError),
    ):
        await adapter.send_email(
            to_email="attendee@example.com",
            subject="Order Receipt",
            body_text="Plain text body",
        )
