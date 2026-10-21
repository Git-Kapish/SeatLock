"""Handler for booking.confirmed domain events."""

from __future__ import annotations

from typing import Any

from app.email import EmailAdapter
from ticketrush_common.logging import get_logger

logger = get_logger("ticketrush.worker.handlers.booking_confirmed")


class BookingConfirmedHandler:
    """Processes booking.confirmed events and sends confirmation emails."""

    def __init__(self, email_adapter: EmailAdapter | None = None) -> None:
        self.email_adapter = email_adapter or EmailAdapter()

    def format_email_content(
        self,
        payload: dict[str, Any],
    ) -> tuple[str, str, str]:
        """Renders the subject, plain text body, and HTML body."""
        booking_id = payload.get("booking_id", "Unknown")
        total_cents = payload.get("total_cents", 0)
        formatted_total = f"${total_cents / 100:.2f}"
        seat_ids = payload.get("seat_ids", [])
        seat_count = len(seat_ids)
        event_id = payload.get("event_id", "Unknown")

        subject = f"Your TicketRush Order Confirmation: {booking_id[:8]}"

        body_text = (
            f"Thank you for your order!\n\n"
            f"Booking Reference: {booking_id}\n"
            f"Event ID: {event_id}\n"
            f"Reserved Seats ({seat_count}): {', '.join(str(s) for s in seat_ids)}\n"
            f"Total Paid: {formatted_total}\n\n"
            f"Present this confirmation upon event entry."
        )

        body_html = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; color: #333; }}
    .card {{ max-width: 600px; margin: 20px auto; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    .header {{ border-bottom: 2px solid #3b82f6; padding-bottom: 12px; margin-bottom: 16px; }}
    .title {{ font-size: 20px; font-weight: bold; color: #1e293b; margin: 0; }}
    .row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
    .label {{ color: #64748b; font-weight: 500; }}
    .value {{ font-weight: 600; color: #0f172a; }}
    .total {{ font-size: 18px; color: #16a34a; font-weight: bold; margin-top: 16px; border-top: 1px dashed #cbd5e1; padding-top: 12px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1 class="title">Booking Confirmation</h1>
    </div>
    <p>Thank you for booking with TicketRush!</p>
    <div class="row"><span class="label">Booking ID:</span> <span class="value">{booking_id}</span></div>
    <div class="row"><span class="label">Event ID:</span> <span class="value">{event_id}</span></div>
    <div class="row"><span class="label">Seats ({seat_count}):</span> <span class="value">{", ".join(str(s) for s in seat_ids)}</span></div>
    <div class="total">Total Paid: {formatted_total}</div>
  </div>
</body>
</html>"""

        return subject, body_text, body_html

    async def handle(self, payload: dict[str, Any]) -> None:
        """Parses event payload and dispatches confirmation receipt email."""
        recipient_email = payload.get("user_email")
        if not recipient_email:
            user_id = payload.get("user_id", "guest")
            recipient_email = f"user-{str(user_id)[:8]}@example.com"

        subject, body_text, body_html = self.format_email_content(payload)

        await self.email_adapter.send_email(
            to_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        logger.info(
            "booking_confirmed_email_sent",
            booking_id=payload.get("booking_id"),
            recipient=recipient_email,
        )
