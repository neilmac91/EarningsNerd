from fastapi import APIRouter, HTTPException, Depends, status, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
import logging
import stripe
from app.database import get_db
from app.models import User, Subscription
from app.routers.auth import get_current_user
from app.config import settings
from app.services.posthog_client import EVENT_TRIAL_STARTED, capture_event
from app.services import subscription_sync
from app.services.entitlements import get_entitlements, get_plan, is_pro_user
from app.services.subscription_service import (
    get_current_month,
    get_user_usage_count,
    get_user_qa_count,
    get_user_analysis_count,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Logical plan tokens the frontend may send, mapped to the configured Stripe price IDs. Lets the
# UI reference stable names instead of hard-coding live price ids (which it previously did,
# guaranteeing an "Invalid price_id" 400 in production).
def _resolve_price_id(price_id: str) -> Optional[str]:
    aliases = {
        "monthly": settings.STRIPE_PRICE_MONTHLY_ID,
        "price_pro_monthly": settings.STRIPE_PRICE_MONTHLY_ID,
        "yearly": settings.STRIPE_PRICE_YEARLY_ID,
        "price_pro_yearly": settings.STRIPE_PRICE_YEARLY_ID,
    }
    resolved = aliases.get(price_id, price_id)
    allowed = {settings.STRIPE_PRICE_MONTHLY_ID, settings.STRIPE_PRICE_YEARLY_ID} - {""}
    return resolved if resolved in allowed else None

class UsageResponse(BaseModel):
    summaries_used: int
    summaries_limit: Optional[int]
    is_pro: bool
    month: str
    # Copilot ("Ask this Filing") Q&A usage this month. qa_limit is the PRO fair-use soft cap
    # (COPILOT_MONTHLY_QUESTION_CAP); surfaced so the UI can show an honest "N of M" instead of
    # only revealing the cap at a 429. FREE users have no monthly Copilot access, so qa_used stays 0.
    qa_used: int
    qa_limit: int
    # Free "taste" of Copilot (roadmap 2.2): lifetime grounded questions a FREE user has spent and
    # the plan's total allowance, so the UI can show "N of M free questions" and switch to the upsell
    # at exhaustion. For Pro these are 0 (Pro is unlimited via qa_limit).
    copilot_free_taste_used: int
    copilot_free_taste_total: int
    # Multi-Period Analysis generations this month vs the Pro fair-use cap (fresh AI narratives
    # only; cached re-serves are unmetered). Free users have no access, so analysis_used stays 0.
    analysis_used: int
    analysis_limit: int

class SubscriptionStatus(BaseModel):
    is_pro: bool
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    subscription_status: Optional[str]
    plan: str
    status: Optional[str]
    trial_end: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool

@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's usage for the month"""
    month = get_current_month()
    current_count = get_user_usage_count(current_user.id, month, db)
    
    # Resolve via the entitlements SSoT (subscription row first, is_pro mirror as fallback) so an
    # active subscriber with a momentarily-stale is_pro mirror still gets the right limits/status.
    ent = get_entitlements(current_user)
    return UsageResponse(
        summaries_used=current_count,
        summaries_limit=ent.monthly_summary_limit,
        is_pro=is_pro_user(current_user),
        month=month,
        qa_used=get_user_qa_count(current_user.id, month, db),
        qa_limit=settings.COPILOT_MONTHLY_QUESTION_CAP,
        copilot_free_taste_used=getattr(current_user, "copilot_free_taste_used", 0) or 0,
        copilot_free_taste_total=ent.copilot_free_taste,
        analysis_used=get_user_analysis_count(current_user.id, month, db),
        analysis_limit=settings.ANALYSIS_MONTHLY_CAP,
    )

@router.get("/subscription", response_model=SubscriptionStatus)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's subscription status.

    Reads the local `subscriptions` row (kept authoritative by the webhook) so the common case
    needs no live Stripe round-trip. Falls back to the `is_pro` mirror when no row exists yet.
    """
    sub = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    plan = get_plan(current_user).value

    return SubscriptionStatus(
        is_pro=plan == "pro",
        stripe_customer_id=(sub.stripe_customer_id if sub else None) or current_user.stripe_customer_id,
        stripe_subscription_id=(sub.stripe_subscription_id if sub else None) or current_user.stripe_subscription_id,
        subscription_status=sub.status if sub else None,
        plan=plan,
        status=sub.status if sub else None,
        trial_end=sub.trial_end if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        cancel_at_period_end=bool(sub.cancel_at_period_end) if sub else False,
    )

@router.post("/create-checkout-session")
async def create_checkout_session(
    price_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create Stripe Checkout session for subscription.

    Three cohorts, resolved server-side (never from a request parameter):
    - Beta ($0 forever coupon): ``discounts`` pre-applied + ``payment_method_collection=
      "if_required"`` so no card is collected on a $0 total. No trial — the coupon never expires.
    - Monthly first-time subscriber with ``PRO_TRIAL_DAYS > 0``: a card-required 7-day trial —
      ``subscription_data.trial_period_days`` + ``payment_method_collection="always"`` (with a
      trial the amount due today is $0, so ``if_required`` would skip the card and Stripe could
      never auto-charge on day 8). ``missing_payment_method: cancel`` backstops a card-less trial.
      One trial per account: ANY prior Subscription row (canceled, expired reverse-trial, …) skips
      the trial, so cancel→resubscribe can't re-farm free weeks on the same account.
    - Everyone else (yearly, or repeat subscriber): plain paid checkout, ``if_required`` (Stripe
      still collects a card whenever the amount due is non-zero, so paying users are unaffected).

    An already-entitled user (active OR live trialing — resolved via the entitlements SSoT, so an
    EXPIRED-trial remnant row never blocks a genuine resubscribe) gets 409, not a second checkout:
    a card-required trial is a real Stripe subscription that auto-charges at trial end, so letting
    it through would double-bill — and the per-user Subscription row upsert would orphan the first
    sub in-app while Stripe keeps charging it (staff review, PR #619).
    """
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before subscribing.",
        )
    if is_pro_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active subscription. Manage it from the billing portal.",
        )
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Stripe is not configured. Please set STRIPE_SECRET_KEY."
        )
    resolved_price_id = _resolve_price_id(price_id)
    if not resolved_price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid price_id. Please select a supported subscription plan.",
        )
    price_id = resolved_price_id

    try:
        # Create or retrieve Stripe customer
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": str(current_user.id)}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        else:
            customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
        
        # Create checkout session
        frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else 'http://localhost:3000'
        billing_cycle = "monthly" if price_id == settings.STRIPE_PRICE_MONTHLY_ID else "yearly"
        session_kwargs = {
            "customer": customer.id,
            "payment_method_types": ["card"],
            "line_items": [{
                "price": price_id,
                "quantity": 1,
            }],
            "mode": "subscription",
            # Skip card collection when the amount due is $0 (the 100%-off beta path). Stripe
            # still requires a card for any non-zero subscription, so paying customers are unaffected.
            # The trial cohort below overrides this to "always" — a trial's amount-due-today is $0,
            # so "if_required" there would mean no card on file and no day-8 auto-charge.
            "payment_method_collection": "if_required",
            "success_url": f"{frontend_url}/dashboard?success=true",
            "cancel_url": f"{frontend_url}/pricing?canceled=true",
            "metadata": {
                "user_id": str(current_user.id),
                "plan": "pro",
                "price_id": price_id,
                "billing_cycle": billing_cycle,
            },
        }
        # Closed-beta eligibility is set server-side at invite redemption (User.is_beta), never from a
        # request parameter — so no authenticated user can self-grant Pro. For a beta user, pre-apply
        # the 100%-off promo: the amount due is $0 and, with payment_method_collection="if_required"
        # above, no card is collected. Mutually exclusive with allow_promotion_codes (which we don't
        # set), so Stripe never 400s on conflicting discount params.
        is_beta_coupon = bool(getattr(current_user, "is_beta", False) and settings.STRIPE_BETA_PROMO_CODE_ID)
        if is_beta_coupon:
            session_kwargs["discounts"] = [{"promotion_code": settings.STRIPE_BETA_PROMO_CODE_ID}]
        elif (
            billing_cycle == "monthly"
            and settings.PRO_TRIAL_DAYS > 0
            and db.query(Subscription).filter(Subscription.user_id == current_user.id).first() is None
        ):
            # First-time monthly subscriber → 7-day card-required trial. A prior Subscription row of
            # ANY status (canceled, expired reverse-trial, …) means this account already had its
            # trial or a paid run — plain paid checkout instead, so cancel→resubscribe can't re-farm
            # free weeks. Card is collected up front ("always") and Stripe auto-charges at trial end;
            # a trial that somehow lacks a card cancels instead of going unpaid.
            session_kwargs["subscription_data"] = {
                "trial_period_days": settings.PRO_TRIAL_DAYS,
                "trial_settings": {"end_behavior": {"missing_payment_method": "cancel"}},
            }
            session_kwargs["payment_method_collection"] = "always"

        checkout_session = stripe.checkout.Session.create(**session_kwargs)

        return {"url": checkout_session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )

@router.post("/create-portal-session")
async def create_portal_session(
    current_user: User = Depends(get_current_user)
):
    """Create Stripe Customer Portal session for subscription management"""
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No subscription found"
        )
    
    try:
        frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else 'http://localhost:3000'
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{frontend_url}/dashboard",
        )
        
        return {"url": portal_session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {str(e)}"
        )

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """Handle Stripe webhooks for subscription events"""
    from app.database import SessionLocal
    db = SessionLocal()
    
    try:
        payload = await request.body()
        
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=500, detail="Stripe not configured")

        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        if not webhook_secret:
            raise HTTPException(
                status_code=500,
                detail="Stripe webhook secret not configured",
            )
        
        if not stripe_signature:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, webhook_secret
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

        # stripe-python v15's StripeObject is NOT dict-like — `.get()` raises AttributeError, which
        # broke every webhook (HTTP 500). construct_event has already verified the signature above;
        # process the verified raw payload as plain dicts so `.get()` works throughout.
        event = json.loads(payload)

        # Idempotency: Stripe delivers at-least-once and retries. If we've already processed this
        # event id, acknowledge without re-applying (prevents double-charge / wrong-entitlement).
        event_id = event.get("id")
        if subscription_sync.is_event_processed(db, event_id):
            return {"status": "success", "idempotent": True}

        event_type = event["type"]
        obj = event["data"]["object"]

        # The webhook is the SOLE source of entitlement truth — never the checkout success redirect.
        if event_type == "checkout.session.completed":
            user = subscription_sync.apply_checkout_completed(db, obj)
            if user:
                try:
                    metadata = obj.get("metadata", {}) or {}
                    # distinct_id is the user id; do NOT send email (PII) as an event property.
                    capture_event(
                        str(user.id),
                        "subscription_activated",
                        {
                            "plan": metadata.get("plan", "pro"),
                            "price_id": metadata.get("price_id"),
                            "billing_cycle": metadata.get("billing_cycle"),
                            "stripe_subscription_id": obj.get("subscription"),
                        },
                    )
                except Exception:
                    pass

        elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
            subscription_sync.apply_subscription_upsert(db, obj)
            # Stripe-native trial start (the reverse-trial path emits this from /register instead).
            # Only on `created` + `trialing` so an `updated` event never re-fires the funnel step.
            if event_type == "customer.subscription.created" and obj.get("status") == "trialing":
                try:
                    user = subscription_sync._find_user(db, obj.get("id"), obj.get("customer"))
                    if user:
                        capture_event(
                            str(user.id),
                            EVENT_TRIAL_STARTED,
                            {"source": "stripe", "trial_end": obj.get("trial_end")},
                        )
                except Exception:
                    pass

        elif event_type == "customer.subscription.deleted":
            subscription_sync.apply_subscription_deleted(db, obj)

        elif event_type == "invoice.payment_failed":
            # Dunning signal. We do NOT revoke entitlement here — the authoritative status
            # transition (active → past_due / canceled) arrives via customer.subscription.updated/
            # deleted, which we handle above. Recording the event id (below) is enough for now.
            logger.info("Stripe invoice.payment_failed for customer %s", obj.get("customer"))

        elif event_type == "customer.subscription.trial_will_end":
            # T-3 trial-ending notice. Email wiring lands with the Phase 2 notification system;
            # for now we record it (idempotently) and emit an analytics signal.
            try:
                user = subscription_sync._find_user(db, obj.get("id"), obj.get("customer"))
                if user:
                    capture_event(str(user.id), "trial_will_end", {"trial_end": obj.get("trial_end")})
            except Exception:
                pass

        # Record the event id (same transaction as the state change) so retries are no-ops.
        subscription_sync.mark_event_processed(db, event_id, event_type)
        db.commit()

    except HTTPException:
        # Preserve intended status codes (e.g. 400 for signature/payload errors).
        # Without this, the broad handler below would mask them as 500s, which
        # also makes Stripe retry on what are really client errors.
        db.rollback()
        raise
    except (KeyError, ValueError, TypeError) as e:
        # Malformed event payload (e.g. missing metadata.user_id, non-int id).
        # Return 400 so Stripe does not keep retrying an unprocessable event.
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Malformed webhook payload: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")
    finally:
        db.close()

    return {"status": "success"}
