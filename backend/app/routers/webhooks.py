import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, signature_header: str, secret: str, svix_id: str, svix_timestamp: str) -> bool:
    """
    Verify Resend webhook signature, which uses the Svix standard.

    The signed content is the `svix-id`, `svix-timestamp`, and request body,
    concatenated with a `.` as a separator.
    """
    if not secret:
        # In non-production environments, we can allow verification to be skipped if the secret is not set.
        if settings.ENVIRONMENT != "production":
            logger.warning("RESEND_WEBHOOK_SECRET not configured - skipping signature verification in non-production environment.")
            return True
        else:
            logger.error("RESEND_WEBHOOK_SECRET is not set in production. Webhook verification failed.")
            return False

    # Construct the signed payload according to Svix standard: svix-id.svix-timestamp.body
    signed_payload = f"{svix_id}.{svix_timestamp}.".encode() + payload
    expected_signature = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256
    ).hexdigest()

    # The svix-signature header can contain multiple signatures, space-separated.
    # e.g., "v1,sig1 v1,sig2"
    for versioned_signature in signature_header.split(" "):
        try:
            version, signature = versioned_signature.split(",", 1)
            if version != "v1":
                continue
            # Compare signatures in constant time to prevent timing attacks
            if hmac.compare_digest(signature, expected_signature):
                return True
        except ValueError:
            continue  # Ignore malformed signature parts

    return False


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
    Resend uses the Svix webhook standard with HMAC SHA256.
    """
    # Get the raw body for signature verification
    body = await request.body()

    # Get the required Svix headers
    signature_header = request.headers.get("svix-signature")
    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")

    if not signature_header:
        logger.warning("Received Resend webhook without svix-signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing webhook signature"
        )

    if not svix_id or not svix_timestamp:
        logger.warning("Received Resend webhook without required Svix headers")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required Svix headers (svix-id, svix-timestamp)"
        )

    # Verify signature
    webhook_secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "")
    if not verify_webhook_signature(body, signature_header, webhook_secret, svix_id, svix_timestamp):
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
    # Future: Update database record to mark contact submission as "email_sent"


async def handle_email_delivered(data: Dict[str, Any]):
    """Handle email.delivered event"""
    email_id = data.get("email_id")
    to = data.get("to")

    logger.info(f"Email delivered: {email_id} to {to}")
    # Future: Update database record to mark email as delivered


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
    # Future: For hard bounces, mark email as invalid; update contact submission status


async def handle_email_complained(data: Dict[str, Any]):
    """Handle email.complained event (spam complaint)"""
    email_id = data.get("email_id")
    to = data.get("to")

    logger.error(f"Email marked as spam: {email_id} to {to}")
    # Future: Auto-unsubscribe this email address to comply with anti-spam regulations


async def handle_email_opened(data: Dict[str, Any]):
    """Handle email.opened event"""
    email_id = data.get("email_id")
    to = data.get("to")

    logger.info(f"Email opened: {email_id} by {to}")
    # Future: Track email open rates for analytics


async def handle_email_clicked(data: Dict[str, Any]):
    """Handle email.clicked event"""
    email_id = data.get("email_id")
    to = data.get("to")
    link = data.get("link")

    logger.info(f"Email link clicked: {email_id} by {to} - Link: {link}")
    # Future: Track click-through rates for analytics
