from fastapi import APIRouter, HTTPException, Depends, status, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import stripe
from app.database import get_db
from app.models import User, UserUsage
from app.routers.auth import get_current_user
from app.config import settings
from app.services.posthog_client import capture_event
from app.services.subscription_service import (
    get_current_month,
    get_user_usage_count,
    increment_user_usage,
    check_usage_limit,
    FREE_TIER_SUMMARY_LIMIT
)

router = APIRouter()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

class UsageResponse(BaseModel):
    summaries_used: int
    summaries_limit: Optional[int]
    is_pro: bool
    month: str

class SubscriptionStatus(BaseModel):
    is_pro: bool
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    subscription_status: Optional[str]

@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's usage for the month"""
    month = get_current_month()
    current_count = get_user_usage_count(current_user.id, month, db)
    
    return UsageResponse(
        summaries_used=current_count,
        summaries_limit=None if current_user.is_pro else FREE_TIER_SUMMARY_LIMIT,
        is_pro=current_user.is_pro,
        month=month
    )

@router.get("/subscription", response_model=SubscriptionStatus)
async def get_subscription_status(
    current_user: User = Depends(get_current_user)
):
    """Get current user's subscription status"""
    subscription_status = None
    if current_user.stripe_subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(current_user.stripe_subscription_id)
            subscription_status = subscription.status
        except:
            pass
    
    return SubscriptionStatus(
        is_pro=current_user.is_pro,
        stripe_customer_id=current_user.stripe_customer_id,
        stripe_subscription_id=current_user.stripe_subscription_id,
        subscription_status=subscription_status
    )

@router.post("/create-checkout-session")
async def create_checkout_session(
    price_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create Stripe Checkout session for subscription"""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Stripe is not configured. Please set STRIPE_SECRET_KEY."
        )
    allowed_prices = {settings.STRIPE_PRICE_MONTHLY_ID, settings.STRIPE_PRICE_YEARLY_ID}
    if price_id not in allowed_prices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid price_id. Please select a supported subscription plan.",
        )
    
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
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{frontend_url}/dashboard?success=true",
            cancel_url=f"{frontend_url}/pricing?canceled=true",
            metadata={
                "user_id": str(current_user.id),
                "plan": "pro",
                "price_id": price_id,
                "billing_cycle": billing_cycle,
            },
        )
        
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
        
        # Handle the event
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = int(session["metadata"]["user_id"])
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.stripe_subscription_id = session.get("subscription")
                user.is_pro = True
                db.commit()
                try:
                    metadata = session.get("metadata", {}) or {}
                    capture_event(
                        str(user.id),
                        "subscription_activated",
                        {
                            "plan": metadata.get("plan", "pro"),
                            "price_id": metadata.get("price_id"),
                            "billing_cycle": metadata.get("billing_cycle"),
                            "stripe_subscription_id": session.get("subscription"),
                            "email": user.email,
                        },
                    )
                except Exception:
                    pass
    
        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            user = db.query(User).filter(
                User.stripe_subscription_id == subscription["id"]
            ).first()
            if user:
                user.is_pro = subscription["status"] in ["active", "trialing"]
                db.commit()
        
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            user = db.query(User).filter(
                User.stripe_subscription_id == subscription["id"]
            ).first()
            if user:
                user.is_pro = False
                user.stripe_subscription_id = None
                db.commit()
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing webhook: {str(e)}")
    finally:
        db.close()
    
    return {"status": "success"}
