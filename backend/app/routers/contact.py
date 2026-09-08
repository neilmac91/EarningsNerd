import html
import logging
import hashlib
from app.utils.datetimes import utcnow
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ContactSubmission
from app.schemas.contact import ContactSubmissionCreate, ContactSubmissionResponse
from app.services.resend_service import ResendError, send_email
from app.services.turnstile import enforce_turnstile
from app.services.rate_limiter import RateLimiter, enforce_rate_limit, get_client_ip as _trusted_client_ip
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Pepper for one-way IP hashing. Prefer an explicit IP_HASH_SALT; otherwise fall back to the app
# SECRET_KEY (always set, and validated non-default in production) so there is never a weak,
# publicly-known default salt. This matches the SECRET_KEY-peppered hashing used elsewhere.
IP_HASH_SALT = settings.IP_HASH_SALT or settings.SECRET_KEY


def hash_ip_address(ip_address: str) -> str:
    """
    Hash an IP address using SHA256 with salt for privacy.

    This allows rate limiting while not storing actual IP addresses.
    The hash is one-way and cannot be reversed to get the original IP.

    Args:
        ip_address: The IP address to hash

    Returns:
        A hex string of the hashed IP address
    """
    # Combine IP with salt and hash using SHA256
    salted_ip = f"{ip_address}{IP_HASH_SALT}".encode('utf-8')
    hash_object = hashlib.sha256(salted_ip)
    return hash_object.hexdigest()

# Per-IP sliding window (3/hour). State lives ONLY in the shared RateLimiter (bounded key
# cardinality, lazy idle cleanup, Retry-After) — never in an ad-hoc module dict.
CONTACT_LIMITER = RateLimiter(limit=3, window_seconds=3600)
CONTACT_RATE_LIMIT_DETAIL = "Too many requests. Please try again in 1 hour(s)."


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request (trusted-proxy aware — see rate_limiter)."""
    return _trusted_client_ip(request)


@router.post("/", response_model=ContactSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_contact_form(
    submission: ContactSubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Submit a contact form message.

    This endpoint:
    - Validates the submission
    - Checks rate limiting (3 requests per hour per IP)
    - Stores the message in the database
    - Sends email notifications to admin and user
    """
    # Limiter first (cheap, local), then Turnstile (network) — same order as the waitlist route.
    enforce_rate_limit(request, CONTACT_LIMITER, "contact", error_detail=CONTACT_RATE_LIMIT_DETAIL)
    await enforce_turnstile(request)  # no-op unless Turnstile is configured

    # Hash the client IP for the persisted row (privacy) — never store the raw address.
    hashed_ip = hash_ip_address(get_client_ip(request))

    # Create database entry (store hashed IP for privacy)
    db_submission = ContactSubmission(
        name=submission.name,
        email=submission.email,
        subject=submission.subject,
        message=submission.message,
        status="new",
        ip_address=hashed_ip,  # Store hashed IP instead of plaintext
    )

    try:
        db.add(db_submission)
        db.commit()
        db.refresh(db_submission)
        logger.info(f"Contact submission created: ID={db_submission.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error creating contact submission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save contact form submission",
        ) from e

    # Send email notifications (async, don't block on failure)
    try:
        await send_contact_notifications(submission, db_submission.id)
    except Exception as e:
        # Log but don't fail the request - submission is already saved
        logger.exception(f"Failed to send contact notification emails: {str(e)}")

    return db_submission


async def send_contact_notifications(
    submission: ContactSubmissionCreate,
    submission_id: int,
):
    """Send email notifications for contact form submission"""
    # Escape all user-provided data to prevent HTML injection
    safe_name = html.escape(submission.name)
    safe_email = html.escape(submission.email)
    safe_subject = html.escape(submission.subject) if submission.subject else None
    safe_message = html.escape(submission.message)

    # Email to admin
    admin_subject = f"New Contact Form Submission from {safe_name}"
    admin_html = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
          .header {{ background-color: #10B981; color: white; padding: 20px; text-align: center; }}
          .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
          .field {{ margin-bottom: 15px; }}
          .label {{ font-weight: bold; color: #555; }}
          .value {{ margin-top: 5px; }}
          .message-box {{ background-color: white; padding: 15px; border-left: 4px solid #10B981; margin-top: 10px; white-space: pre-wrap; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h2>New Contact Form Submission</h2>
          </div>
          <div class="content">
            <div class="field">
              <div class="label">Submission ID:</div>
              <div class="value">#{submission_id}</div>
            </div>
            <div class="field">
              <div class="label">Name:</div>
              <div class="value">{safe_name}</div>
            </div>
            <div class="field">
              <div class="label">Email:</div>
              <div class="value"><a href="mailto:{safe_email}">{safe_email}</a></div>
            </div>
            {f'<div class="field"><div class="label">Subject:</div><div class="value">{safe_subject}</div></div>' if safe_subject else ''}
            <div class="field">
              <div class="label">Message:</div>
              <div class="message-box">{safe_message}</div>
            </div>
            <div class="field">
              <div class="label">Submitted:</div>
              <div class="value">{utcnow().strftime("%B %d, %Y at %I:%M %p UTC")}</div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    # Email to user (confirmation)
    user_subject = "We received your message - EarningsNerd"
    user_html = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
          .header {{ background-color: #10B981; color: white; padding: 20px; text-align: center; }}
          .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
          .message-box {{ background-color: white; padding: 15px; border-left: 4px solid #10B981; margin: 15px 0; white-space: pre-wrap; }}
          .footer {{ text-align: center; margin-top: 20px; font-size: 0.9em; color: #666; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h2>Thank You for Contacting EarningsNerd</h2>
          </div>
          <div class="content">
            <p>Hi {safe_name},</p>
            <p>We&apos;ve received your message and will get back to you as soon as possible, typically within 1-2 business days.</p>
            <p><strong>Your message:</strong></p>
            <div class="message-box">{safe_message}</div>
            <p>If you need immediate assistance or have additional information to add, feel free to reply to this email.</p>
            <p>Best regards,<br>The EarningsNerd Team</p>
          </div>
          <div class="footer">
            <p>EarningsNerd - AI-Powered SEC Filing Analysis<br>
            <a href="{settings.FRONTEND_URL}">{settings.FRONTEND_URL}</a></p>
          </div>
        </div>
      </body>
    </html>
    """

    # Send both emails
    # Note: In a production environment with high volume, consider using a job queue
    try:
        # Send to admin (using environment variable or fallback)
        from_email = settings.RESEND_FROM_EMAIL
        if not from_email:
            logger.warning("RESEND_FROM_EMAIL is not set, skipping admin notification")
        else:
            try:
                # safe extraction of email
                if "<" in from_email and ">" in from_email:
                    admin_email = from_email.split("<")[-1].rstrip(">")
                else:
                    admin_email = from_email
                
                await send_email(
                    to=[admin_email],
                    subject=admin_subject,
                    html=admin_html,
                )
                logger.info(f"Admin notification email sent for submission #{submission_id}")
            except Exception as e:
                 logger.error(f"Failed to process admin email address or send: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to send admin notification email (outer): {str(e)}")
        # Don't raise - try to send user email anyway

    try:
        # Send confirmation to user
        await send_email(
            to=[submission.email],
            subject=user_subject,
            html=user_html,
        )
        logger.info(f"User confirmation email sent for submission #{submission_id}")
    except ResendError as e:
        logger.error(f"Failed to send user confirmation email: {str(e)}")
        # Don't raise - submission is already saved
