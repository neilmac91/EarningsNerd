import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Resend webhook signature.

    Resend uses HMAC SHA256 to sign webhook payloads.
    """
    if not secret:
        logger.warning("RESEND_WEBHOOK_SECRET not configured - skipping signature verification")
        return True  # In development, allow webhooks without verification

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Compare signatures in constant time to prevent timing attacks
    return hmac.compare_digest(signature, expected_signature)


@router.post("/webhooks/resend")
async def handle_resend_webhook(request: Request):
    """
    Handle incoming webhooks from Resend.

    Supported events:
    - email.sent: Email was successfully sent
    - email.delivered: Email was delivered to recipient's inbox
    - email.delivery_delayed: Delivery was delayed
    - email.complained: Recipient marked email as spam
    - email.bounced: Email bounced (hard or soft)
    - email.opened: Recipient opened the email
    - email.clicked: Recipient clicked a link in the email

    Webhook signature verification:
    Resend signs webhooks with HMAC SHA256 using your webhook secret.
    """
    # Get the raw body for signature verification
    body = await request.body()

    # Get the signature from headers
    signature = request.headers.get("svix-signature") or request.headers.get("x-resend-signature")

    if not signature:
        logger.warning("Received Resend webhook without signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing webhook signature"
        )

    # Extract the actual signature (Svix format: v1,signature)
    if "," in signature:
        signature = signature.split(",")[1] if "," in signature else signature

    # Verify signature (if webhook secret is configured)
    webhook_secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "")
    if webhook_secret and not verify_webhook_signature(body, signature, webhook_secret):
        logger.error("Invalid Resend webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # Parse the webhook payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Resend webhook payload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    # Get event type
    event_type = payload.get("type")
    data = payload.get("data", {})

    logger.info(f"Received Resend webhook: {event_type}")

    # Handle different event types
    if event_type == "email.sent":
        await handle_email_sent(data)
    elif event_type == "email.delivered":
        await handle_email_delivered(data)
    elif event_type == "email.delivery_delayed":
        await handle_email_delayed(data)
    elif event_type == "email.bounced":
        await handle_email_bounced(data)
    elif event_type == "email.complained":
        await handle_email_complained(data)
    elif event_type == "email.opened":
        await handle_email_opened(data)
    elif event_type == "email.clicked":
        await handle_email_clicked(data)
    else:
        logger.warning(f"Unhandled Resend webhook event type: {event_type}")

    # Always return 200 OK to acknowledge receipt
    return {"status": "ok", "event": event_type}


async def handle_email_sent(data: Dict[str, Any]):
    """Handle email.sent event"""
    email_id = data.get("email_id")
    to = data.get("to")
    subject = data.get("subject")

    logger.info(f"Email sent: {email_id} to {to} - Subject: {subject}")

    # TODO: Update database record if needed
    # For example, mark contact submission as "email_sent"


async def handle_email_delivered(data: Dict[str, Any]):
    """Handle email.delivered event"""
    email_id = data.get("email_id")
    to = data.get("to")

    logger.info(f"Email delivered: {email_id} to {to}")

    # TODO: Update database record if needed


async def handle_email_delayed(data: Dict[str, Any]):
    """Handle email.delivery_delayed event"""
    email_id = data.get("email_id")
    to = data.get("to")

    logger.warning(f"Email delivery delayed: {email_id} to {to}")


async def handle_email_bounced(data: Dict[str, Any]):
    """Handle email.bounced event"""
    email_id = data.get("email_id")
    to = data.get("to")
    bounce_type = data.get("bounce_type")  # "hard" or "soft"

    logger.error(f"Email bounced ({bounce_type}): {email_id} to {to}")

    # TODO: For hard bounces, consider marking email as invalid in database
    # TODO: For contact submissions, update status to "bounce"


async def handle_email_complained(data: Dict[str, Any]):
    """Handle email.complained event (spam complaint)"""
    email_id = data.get("email_id")
    to = data.get("to")

    logger.error(f"Email marked as spam: {email_id} to {to}")

    # TODO: Consider unsubscribing this email address
    # TODO: Update contact submission status if applicable


async def handle_email_opened(data: Dict[str, Any]):
    """Handle email.opened event"""
    email_id = data.get("email_id")
    to = data.get("to")

    logger.info(f"Email opened: {email_id} by {to}")

    # TODO: Track email open rates


async def handle_email_clicked(data: Dict[str, Any]):
    """Handle email.clicked event"""
    email_id = data.get("email_id")
    to = data.get("to")
    link = data.get("link")

    logger.info(f"Email link clicked: {email_id} by {to} - Link: {link}")

    # TODO: Track click-through rates
