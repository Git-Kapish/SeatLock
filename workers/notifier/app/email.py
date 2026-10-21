"""Email delivery adapter for SMTP (MailHog) and async notifications."""

from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from app.config import config
from ticketrush_common.logging import get_logger

logger = get_logger("ticketrush.worker.email")


class EmailAdapter:
    """Async email dispatcher via SMTP (MailHog / local or remote relay)."""

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        default_sender: str | None = None,
    ) -> None:
        self.smtp_host = smtp_host or config.smtp_host
        self.smtp_port = smtp_port or config.smtp_port
        self.default_sender = default_sender or config.smtp_sender

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> bool:
        """Constructs and sends an email via SMTP."""
        message = EmailMessage()
        message["From"] = self.default_sender
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body_text)

        if body_html:
            message.add_alternative(body_html, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                timeout=10,
            )
            logger.info(
                "email_dispatched_successfully",
                to=to_email,
                subject=subject,
                smtp_host=self.smtp_host,
                smtp_port=self.smtp_port,
            )
            return True
        except Exception as exc:
            logger.error(
                "email_dispatch_failed",
                to=to_email,
                subject=subject,
                error=str(exc),
            )
            raise exc
