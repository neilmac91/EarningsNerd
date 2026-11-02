import base64
import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.services import resend_webhook_service
from app.services.resend_webhook_service import signing_key
from app.utils.datetimes import utcnow
from app.utils.pii import mask_recipients

router = APIRouter()
logger = logging.getLogger(__name__)


# Svix's own libraries refuse a timestamp more than five minutes either side of the receiver's clock.
_TIMESTAMP_TOLERANCE_SECONDS = 5 * 60


def verify_webhook_signature(payload: bytes, signature_header: str, secret: str, svix_id: str, svix_timestamp: str) -> bool:
    """
    Verify a Resend webhook by the Svix scheme Resend signs with.

    Svix keys an HMAC-SHA256 with the base64-decoded text of the ``whsec_`` secret, signs
    ``{svix-id}.{svix-timestamp}.{raw body}``, and sends ``v1,<base64 digest>`` entries separated by
    spaces in ``svix-signature``. A timestamp more than five minutes from this server's clock is
    refused, as Svix's libraries refuse it, so a captured delivery cannot be replayed after that.
    """
    if not secret:
        # In non-production environments, we can allow verification to be skipped if the secret is not set.
        if settings.ENVIRONMENT != "production":
            logger.warning("RESEND_WEBHOOK_SECRET not configured - skipping signature verification in non-production environment.")
            return True
        else:
            logger.error("RESEND_WEBHOOK_SECRET is not set in production. Webhook verification failed.")
            return False

    key = signing_key(secret)
    if key is None:
        logger.error("RESEND_WEBHOOK_SECRET is not a Svix signing secret (whsec_ and base64). Webhook verification failed.")
        return False

    try:
        sent_at = int(svix_timestamp)
    except ValueError:
        return False
    # Compared, never subtracted: Python compares an int with a float exactly, so a long run of digits
    # is no OverflowError, and the fraction of the clock's second is kept, as Svix's libraries keep it.
    now = utcnow().timestamp()
    if not now - _TIMESTAMP_TOLERANCE_SECONDS <= sent_at <= now + _TIMESTAMP_TOLERANCE_SECONDS:
        logger.warning("Resend webhook timestamp is more than five minutes from the server clock")
        return False

    mac = hmac.new(key, f"{svix_id}.{svix_timestamp}.".encode() + payload, hashlib.sha256)
    for versioned_signature in signature_header.split(" "):
        version, _, signature = versioned_signature.partition(",")
        # Bytes, not str: compare_digest raises TypeError on a non-ASCII str, and headers decode as latin-1.
        if version == "v1" and hmac.compare_digest(signature.encode(), base64.b64encode(mac.digest())):
            return True
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
    - email.failed and email.suppressed: the provider did not send it (recorded, not logged by a handler)

    Webhook signature verification:
    Resend uses the Svix webhook standard with HMAC SHA256.

    Sent, delivered, delayed, bounced, complained, failed and suppressed events also update the invitation ledger
    and the suppression list (invite_delivery_service), once the signature verified.
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
    elif not isinstance(event_type, str) or event_type not in resend_webhook_service.FEEDBACK_EVENTS:
        logger.warning(f"Unhandled Resend webhook event type: {event_type}")

    # Durable feedback (EN-BETA PB-01): only from a delivery the signature check authenticated, so with no secret set
    # (outside production, where verification is skipped) nothing is recorded. A failed write answers 503, so the
    # provider retries the delivery; applying it twice changes nothing.
    event = resend_webhook_service.parse_event(event_type, data, svix_id)
    if event is not None:
        if not webhook_secret:
            logger.warning("Resend feedback not recorded: the delivery is unauthenticated (RESEND_WEBHOOK_SECRET unset)")
        else:
            await _record_feedback(event)

    # Acknowledge receipt
    return {"status": "ok", "event": event_type}


async def _record_feedback(event: "resend_webhook_service.ProviderEvent") -> None:
    """Apply one signed event to the invitation ledger and the suppression list, off the event loop in a session of
    its own (the route holds none), or answer 503 so the provider sends the delivery again."""
    from app.services.invite_delivery_service import apply_provider_event
    from app.services.job_sessions import run_in_own_session_sync

    try:
        await run_in_threadpool(run_in_own_session_sync, apply_provider_event, event)
    except Exception as exc:  # noqa: BLE001 — the class alone: a database error can carry the statement's values
        logger.error("Could not record Resend feedback %s: %s", event.event_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Feedback not recorded; send it again."
        ) from None


async def handle_email_sent(data: Dict[str, Any]):
    """Handle email.sent event"""
    email_id = data.get("email_id")
    masked_to = mask_recipients(data.get("to"))
    subject = data.get("subject")

    logger.info(f"Email sent: {email_id} to {masked_to} - Subject: {subject}")
    # Future: Update database record to mark contact submission as "email_sent"


async def handle_email_delivered(data: Dict[str, Any]):
    """Handle email.delivered event"""
    email_id = data.get("email_id")
    masked_to = mask_recipients(data.get("to"))

    logger.info(f"Email delivered: {email_id} to {masked_to}")
    # Future: Update database record to mark email as delivered


async def handle_email_delayed(data: Dict[str, Any]):
    """Handle email.delivery_delayed event"""
    email_id = data.get("email_id")
    masked_to = mask_recipients(data.get("to"))

    logger.warning(f"Email delivery delayed: {email_id} to {masked_to}")


async def handle_email_bounced(data: Dict[str, Any]):
    """Handle email.bounced event. Resend sends the bounce as ``data.bounce`` (``type``: "Permanent" or
    "Temporary"); a permanent one suppresses the address (``_record_feedback``)."""
    email_id = data.get("email_id")
    masked_to = mask_recipients(data.get("to"))
    bounce = data.get("bounce") if isinstance(data.get("bounce"), dict) else {}
    bounce_type = bounce.get("type") if isinstance(bounce.get("type"), str) else None

    logger.error(f"Email bounced ({bounce_type}): {email_id} to {masked_to}")


async def handle_email_complained(data: Dict[str, Any]):
    """Handle email.complained event (spam complaint)"""
    email_id = data.get("email_id")
    masked_to = mask_recipients(data.get("to"))

    logger.error(f"Email marked as spam: {email_id} to {masked_to}")


async def handle_email_opened(data: Dict[str, Any]):
    """Handle email.opened event"""
    email_id = data.get("email_id")
    masked_to = mask_recipients(data.get("to"))

    logger.info(f"Email opened: {email_id} by {masked_to}")
    # Future: Track email open rates for analytics


async def handle_email_clicked(data: Dict[str, Any]):
    """Handle email.clicked event: the alert-to-return measurement's write (E11c).

    Resend nests the click under ``data.click`` (``link``, ``timestamp``, ``ipAddress``,
    ``userAgent``); only the link's path and the timestamp are used, never the address or agent.
    """
    email_id = data.get("email_id")
    masked_to = mask_recipients(data.get("to"))
    click = data.get("click") if isinstance(data.get("click"), dict) else {}
    link_path = _link_path(click.get("link"))

    logger.info(f"Email link clicked: {email_id} by {masked_to} - Path: {link_path}")
    if isinstance(email_id, str) and email_id.strip():
        # Best-effort and off the event loop: the provider expects a 200 whatever happens here.
        await run_in_threadpool(_record_alert_return, email_id.strip(), link_path, click.get("timestamp"))


def _link_path(link: Any) -> Optional[str]:
    """The clicked link's path only (which page brought the reader back); never the query string."""
    if not isinstance(link, str) or not link:
        return None
    try:
        return urlsplit(link).path or None
    except ValueError:
        return None


def _record_alert_return(provider_email_id: str, link_path: Optional[str], clicked_at: Any) -> None:
    """Stamp the batch's first click and report it, so alert-to-return is measurable per kind."""
    from app.services.job_sessions import run_in_own_session_sync
    from app.services.notification_delivery_service import record_first_click
    from app.services.posthog_client import capture_event
    from app.utils.datetimes import ensure_utc, utcnow

    # The provider's click instant when it parses (a webhook retry arrives later than the click);
    # receipt time otherwise.
    now = utcnow()
    try:
        clicked = ensure_utc(datetime.fromisoformat(clicked_at.replace("Z", "+00:00"))) if isinstance(clicked_at, str) else now
    except ValueError:
        clicked = now
    try:
        hit = run_in_own_session_sync(record_first_click, provider_email_id, clicked)
        if hit is None:
            return  # transactional mail, a repeat click, or a send that predates the batch ledger
        # SQLite hands back naive stamps for timezone-aware columns; PostgreSQL returns aware ones.
        dispatched = ensure_utc(hit.first_dispatch_at) if hit.first_dispatch_at is not None else None
        hours = round((clicked - dispatched).total_seconds() / 3600, 2) if dispatched is not None else None
        capture_event(str(hit.user_id), "alert_email_clicked", {
            "kind": hit.kind,
            "batch_id": hit.batch_id,
            "hours_to_first_click": hours,
            "link_path": link_path,
        })
    except Exception:  # noqa: BLE001 — measurement must never fail the provider's webhook
        logger.warning("Could not record the alert click for %s", provider_email_id, exc_info=True)
