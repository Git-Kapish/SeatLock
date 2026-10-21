"""API routes for payment provider webhooks."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import get_payment_service
from app.schemas.webhook import PaymentWebhookPayload
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/booking/payments", tags=["Payment Webhooks"])


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Process payment provider webhook events with HMAC signature verification",
)
async def process_payment_webhook(
    request: Request,
    signature: str | None = Header(default=None, alias="X-Signature-256"),
    payment_service: PaymentService = Depends(get_payment_service),
) -> dict[str, Any]:
    """Receives payment provider webhook events (payment.succeeded, payment.failed).

    Verifies HMAC-SHA256 signature in X-Signature-256 header. Deduplicates via provider_event_id.
    On payment.succeeded: permanently marks seats booked, confirms booking, deletes Redis keys,
    and publishes event to SQS queue.
    """
    raw_body = await request.body()

    # 1. Verify HMAC SHA256 signature
    payment_service.verify_webhook_signature(raw_body=raw_body, signature_header=signature)

    # 2. Parse payload
    payload_dict = json.loads(raw_body)
    payload = PaymentWebhookPayload.model_validate(payload_dict)

    # 3. Process event idempotently
    return await payment_service.process_webhook(payload)
