from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, EmailStr, Field, field_validator
import jwt
from app.database import get_db
from app.models import User, Filing, Summary
from app.routers.auth import get_current_user
from app.services.summary_generation_service import progress_as_dict
from app.services.summary_placeholders import is_summary_placeholder
from app.config import settings
from app.services import filing_list_service, watchlist_service
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.turnstile import enforce_turnstile
from app.utils.text import has_control_characters
from app.services.waitlist_service import (
    REFERRAL_BONUS,
    WaitlistAlreadyJoined,
    WaitlistReferralNotFound,
    WaitlistSignupFailed,
    build_referral_link,
    build_verification_link,
    calculate_waitlist_position,
    count_referrals,
    count_signups,
    create_signup,
    create_verification_token,
    find_signup_by_email,
    mark_email_verified,
    mark_welcome_email_sent,
    SignupView,
)
from app.services.email_service import (
    send_referral_success_email,
    send_waitlist_welcome_email,
)

import logging

router = APIRouter()
waitlist_router = APIRouter()

WAITLIST_JOIN_LIMITER = RateLimiter(limit=5, window_seconds=60 * 60)
WAITLIST_STATUS_LIMITER = RateLimiter(limit=10, window_seconds=60)
logger = logging.getLogger(__name__)

class WatchlistResponse(BaseModel):
    id: int
    company_id: int
    created_at: str
    company: dict
    
    class Config:
        from_attributes = True

@router.post("/{ticker}")
async def add_to_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add company to watchlist"""
    user_id = current_user.id

    def add() -> Dict[str, Any]:
        # Each watchlist route's session work is one unit in the thread pool: the reads and writes,
        # the payload and the release, so no checkout waits on the event loop
        # (lessons/ops-release-cached-filing-reads-before-yield.md).
        try:
            added = watchlist_service.add_company(db, user_id, ticker)
            return {
                "id": added.id,
                "company_id": added.company_id,
                "created_at": added.created_at.isoformat() if added.created_at else None,
                "company": {
                    "id": added.company_id,
                    "ticker": added.company_ticker,
                    "name": added.company_name,
                }
            }
        finally:
            filing_list_service.release_request_session(db)

    try:
        return await run_in_threadpool(add)
    except watchlist_service.WatchlistCompanyNotFound:
        raise HTTPException(status_code=404, detail="Company not found")
    except watchlist_service.AlreadyOnWatchlist:
        raise HTTPException(status_code=400, detail="Company already in watchlist")

@router.get("/", response_model=List[WatchlistResponse])
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's watchlist"""
    user_id = current_user.id

    def list_for_reader() -> List[Dict[str, Any]]:
        try:
            result = []
            for item in watchlist_service.list_items(db, user_id):
                company = item.company
                if company:
                    result.append({
                        "id": item.id,
                        "company_id": item.company_id,
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                        "company": {
                            "id": company.id,
                            "ticker": company.ticker,
                            "name": company.name,
                        }
                    })
            return result
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(list_for_reader)

@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove company from watchlist"""
    user_id = current_user.id

    def remove() -> None:
        try:
            watchlist_service.remove_company(db, user_id, ticker)
        finally:
            filing_list_service.release_request_session(db)

    try:
        await run_in_threadpool(remove)
    except watchlist_service.WatchlistCompanyNotFound:
        raise HTTPException(status_code=404, detail="Company not found")
    except watchlist_service.NotOnWatchlist:
        raise HTTPException(status_code=404, detail="Company not in watchlist")

    return {"status": "success"}


# --------------------------------------------------------------------------- earnings-day alerts

@router.get("/earnings-alerts")
async def get_earnings_alert_tickers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tickers the user has earnings-day alerts enabled for (feeds the calendar's bell state)."""
    from app.services.earnings_alert_service import enabled_tickers
    user_id = current_user.id

    def tickers_for_reader() -> List[str]:
        try:
            return enabled_tickers(db, user_id)
        finally:
            filing_list_service.release_request_session(db)

    return {"tickers": await run_in_threadpool(tickers_for_reader)}


@router.post("/{ticker}/earnings-alert")
async def enable_earnings_alert(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable the earnings-day alert for a company (per-plan cap enforced here).

    On the cap, returns 403 with a tier-appropriate body: Free carries the machine-readable
    ``code='earnings_alert_limit'`` (a visible upsell surface); Pro gets a terse, code-less message
    (the 100 cap is an invisible guardrail — the frontend renders whatever we return, verbatim)."""
    from app.services.earnings_alert_service import (
        CompanyNotResolvable,
        EarningsAlertLimitError,
        set_earnings_alert,
    )

    def enable() -> None:
        # The user row is the request session's own (the auth dependency loaded it there), and the
        # cap check reads its plan inside this unit.
        try:
            set_earnings_alert(db, current_user, ticker, enabled=True)
        finally:
            filing_list_service.release_request_session(db)

    try:
        await run_in_threadpool(enable)
    except EarningsAlertLimitError as exc:
        if exc.plan_is_pro:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "You've reached the maximum number of earnings alerts."},
            )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": f"Free includes earnings alerts for {exc.limit} companies. Upgrade to Pro for more.",
                "code": "earnings_alert_limit",
            },
        )
    except CompanyNotResolvable:
        raise HTTPException(status_code=404, detail=f"We can't set an alert for {ticker.upper()} yet.")
    return {"status": "enabled", "ticker": ticker.upper()}


@router.delete("/{ticker}/earnings-alert")
async def disable_earnings_alert(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable the earnings-day alert for a company. Always allowed."""
    from app.services.earnings_alert_service import set_earnings_alert

    def disable() -> None:
        try:
            set_earnings_alert(db, current_user, ticker, enabled=False)
        finally:
            filing_list_service.release_request_session(db)

    await run_in_threadpool(disable)
    return {"status": "disabled", "ticker": ticker.upper()}


class WatchlistCompany(BaseModel):
    id: int
    ticker: str
    name: str


class WatchlistFilingSnapshot(BaseModel):
    id: int
    filing_type: str
    filing_date: Optional[str]
    period_end_date: Optional[str]
    summary_id: Optional[int]
    summary_status: str
    summary_created_at: Optional[str]
    summary_updated_at: Optional[str]
    needs_regeneration: bool
    progress: Optional[Dict[str, Any]] = None


class WatchlistInsightResponse(BaseModel):
    company: WatchlistCompany
    latest_filing: Optional[WatchlistFilingSnapshot]
    total_filings: int


@router.get("/insights", response_model=List[WatchlistInsightResponse])
async def get_watchlist_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return enriched status information for the user's watchlist."""
    user_id = current_user.id

    def insights_for_reader() -> List[WatchlistInsightResponse]:
        # The rows, the payload built from them and the release, in one unit; the progress rows come
        # with the insight rows, so the unit needs no second connection
        # (lessons/ops-one-connection-per-request-unit.md).
        try:
            rows = watchlist_service.load_insight_rows(db, user_id)

            insights: List[WatchlistInsightResponse] = []
            if rows is None:
                return insights
            latest_filing_by_company = rows.latest_filing_by_company
            filing_counts = rows.filing_counts
            summary_by_filing = rows.summary_by_filing
            progress_by_filing = rows.progress_by_filing

            for item in rows.watchlist_items:
                company = item.company
                if not company:
                    continue

                latest_filing: Optional[Filing] = latest_filing_by_company.get(company.id)
                total_filings = int(filing_counts.get(company.id, 0))

                filing_snapshot: Optional[WatchlistFilingSnapshot] = None

                if latest_filing:
                    summary: Optional[Summary] = summary_by_filing.get(latest_filing.id)

                    progress_row = progress_by_filing.get(latest_filing.id)
                    progress_snapshot = progress_as_dict(progress_row) if progress_row else None

                    summary_status = "missing"
                    needs_regeneration = True
                    summary_id: Optional[int] = None
                    summary_created_at: Optional[str] = None
                    summary_updated_at: Optional[str] = None

                    if summary:
                        summary_id = summary.id
                        summary_created_at = summary.created_at.isoformat() if summary.created_at else None
                        summary_updated_at = summary.updated_at.isoformat() if summary.updated_at else None

                        has_placeholder = is_summary_placeholder(summary.business_overview)

                        if has_placeholder:
                            summary_status = "placeholder"
                            needs_regeneration = True
                        else:
                            summary_status = "ready"
                            needs_regeneration = False
                    elif progress_snapshot:
                        stage = progress_snapshot.get("stage", "generating")
                        if stage == "error":
                            summary_status = "error"
                            needs_regeneration = True
                        else:
                            summary_status = f"generating:{stage}"
                            needs_regeneration = False
                    else:
                        summary_status = "missing"
                        needs_regeneration = True

                    filing_snapshot = WatchlistFilingSnapshot(
                        id=latest_filing.id,
                        filing_type=latest_filing.filing_type,
                        filing_date=latest_filing.filing_date.isoformat() if latest_filing.filing_date else None,
                        period_end_date=latest_filing.period_end_date.isoformat() if latest_filing.period_end_date else None,
                        summary_id=summary_id,
                        summary_status=summary_status,
                        summary_created_at=summary_created_at,
                        summary_updated_at=summary_updated_at,
                        needs_regeneration=needs_regeneration,
                        progress=progress_snapshot,
                    )

                insights.append(
                    WatchlistInsightResponse(
                        company=WatchlistCompany(
                            id=company.id,
                            ticker=company.ticker,
                            name=company.name,
                        ),
                        latest_filing=filing_snapshot,
                        total_filings=total_filings,
                    )
                )

            return insights
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(insights_for_reader)


class WaitlistJoinRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(None, max_length=100)
    referral_code: Optional[str] = None
    source: Optional[str] = Field(None, max_length=100)
    honeypot: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name", "source")
    @classmethod
    def normalize_free_text(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = value.strip()
        if has_control_characters(cleaned):
            raise ValueError("Must not contain control characters.")
        return cleaned or None

    @field_validator("referral_code")
    @classmethod
    def normalize_referral_code(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = value.strip().lower()
        return cleaned or None

    @field_validator("honeypot")
    @classmethod
    def normalize_honeypot(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = value.strip()
        return cleaned or None


class WaitlistStatusResponse(BaseModel):
    """Public, unauthenticated status: position and referral progress only."""
    position: int
    referrals_count: int
    positions_gained: int


@waitlist_router.post("/join")
async def join_waitlist(
    payload: WaitlistJoinRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    enforce_rate_limit(
        request,
        WAITLIST_JOIN_LIMITER,
        "waitlist_join",
        error_detail="Too many waitlist requests. Please try again later.",
    )
    await enforce_turnstile(request)  # no-op unless Turnstile is configured

    if payload.honeypot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid submission.",
        )

    def create() -> Tuple[str, SignupView, Optional[SignupView], Optional[int]]:
        # One unit in the thread pool: the insert and every value the rest of the route reads,
        # released before the welcome and referral mails go out, so neither send holds a connection
        # (lessons/ops-release-cached-filing-reads-before-yield.md).
        try:
            try:
                joined = create_signup(
                    db,
                    email=payload.email,
                    name=payload.name,
                    referral_code=payload.referral_code,
                    source=payload.source,
                )
            except WaitlistAlreadyJoined as exc:
                return "already_registered", SignupView.of(exc.signup), None, None
            referrer = SignupView.of(joined.referrer) if joined.referrer else None
            return "joined", SignupView.of(joined.signup), referrer, joined.total_signups
        finally:
            filing_list_service.release_request_session(db)

    try:
        outcome, signup, referrer, total_signups = await run_in_threadpool(create)
    except WaitlistReferralNotFound:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "invalid_referral",
                "message": "Referral code not recognized.",
            },
        )
    except WaitlistSignupFailed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create waitlist signup.",
        )

    if outcome == "already_registered":
        return {
            "success": False,
            "error": "already_registered",
            "message": "This email is already on the waitlist.",
            "position": calculate_waitlist_position(signup.position, signup.priority_score),
            "referral_code": signup.referral_code,
            "referral_link": build_referral_link(signup.referral_code),
        }

    position = calculate_waitlist_position(signup.position, signup.priority_score)
    referral_link = build_referral_link(signup.referral_code)
    verification_token = create_verification_token(signup.email, signup.referral_code)
    verification_link = build_verification_link(verification_token)

    def mark_sent() -> None:
        # Its own unit after the send; the release rolls back a flag commit that fails.
        try:
            mark_welcome_email_sent(db, signup.id)
        finally:
            filing_list_service.release_request_session(db)

    email_sent = False
    try:
        await send_waitlist_welcome_email(
            to_email=signup.email,
            name=signup.name,
            position=position,
            referral_link=referral_link,
            verification_link=verification_link,
        )
        await run_in_threadpool(mark_sent)
        email_sent = True
    except Exception:
        logger.exception("Waitlist welcome email failed for signup %s", signup.id)

    if referrer:
        referrer_position = calculate_waitlist_position(referrer.position, referrer.priority_score)
        referrer_link = build_referral_link(referrer.referral_code)
        try:
            await send_referral_success_email(
                to_email=referrer.email,
                name=referrer.name,
                new_position=referrer_position,
                referral_link=referrer_link,
            )
        except Exception:
            logger.exception("Referral email failed for referrer signup %s", referrer.id)

    return {
        "success": True,
        "message": "You're on the waitlist.",
        "position": position,
        "referral_code": signup.referral_code,
        "referral_link": referral_link,
        "email_sent": email_sent,
        "total_signups": total_signups,
    }


@waitlist_router.get("/status/{email}", response_model=WaitlistStatusResponse)
async def get_waitlist_status(email: EmailStr, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(
        request,
        WAITLIST_STATUS_LIMITER,
        "waitlist_status",
        error_detail="Too many status checks. Please try again later.",
    )
    normalized_email = email.strip().lower()

    # The lookups, the response and the session release are one unit off the event loop, so the
    # pooled connection is back before the route yields to the dependency's finalizer
    # (``lessons/ops-release-cached-filing-reads-before-yield.md``).
    def status_for_reader() -> WaitlistStatusResponse:
        try:
            signup = find_signup_by_email(db, normalized_email)
            if not signup:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email not found on the waitlist.",
                )

            referrals_count = count_referrals(db, signup.referral_code)
            position = calculate_waitlist_position(signup.position, signup.priority_score)
            return WaitlistStatusResponse(
                position=position,
                referrals_count=int(referrals_count),
                positions_gained=signup.priority_score * REFERRAL_BONUS,
            )
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(status_for_reader)


@waitlist_router.get("/stats")
async def get_waitlist_stats(db: Session = Depends(get_db)):
    # The count and the session release are one unit off the event loop, as for the status read.
    def stats_for_reader() -> dict[str, int]:
        try:
            return {"total_signups": int(count_signups(db))}
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(stats_for_reader)


@waitlist_router.post("/verify/{token}")
async def verify_waitlist_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
            leeway=settings.JWT_LEEWAY_SECONDS,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token.",
        ) from exc

    if payload.get("type") != "waitlist_verify":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token.",
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token.",
        )

    def verify() -> bool:
        try:
            return mark_email_verified(db, email)
        finally:
            filing_list_service.release_request_session(db)

    if not await run_in_threadpool(verify):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waitlist entry not found.",
        )

    return {"success": True, "message": "Email verified."}

