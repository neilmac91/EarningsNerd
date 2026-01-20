from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator
from jose import JWTError, jwt
from app.database import get_db
from app.models import Watchlist, Company, User, Filing, Summary, WaitlistSignup
from app.routers.auth import get_current_user
from app.routers.summaries import get_generation_progress_snapshot
from app.config import settings
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.waitlist_service import (
    REFERRAL_BONUS,
    build_referral_link,
    build_verification_link,
    calculate_waitlist_position,
    create_verification_token,
    generate_unique_referral_code,
)
from app.services.email_service import (
    send_referral_success_email,
    send_waitlist_welcome_email,
)

router = APIRouter()
waitlist_router = APIRouter()

WAITLIST_JOIN_LIMITER = RateLimiter(limit=5, window_seconds=60 * 60)

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
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if already in watchlist
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.company_id == company.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Company already in watchlist")
    
    watchlist_item = Watchlist(
        user_id=current_user.id,
        company_id=company.id
    )
    db.add(watchlist_item)
    db.commit()
    db.refresh(watchlist_item)
    
    return {
        "id": watchlist_item.id,
        "company_id": watchlist_item.company_id,
        "created_at": watchlist_item.created_at.isoformat() if watchlist_item.created_at else None,
        "company": {
            "id": company.id,
            "ticker": company.ticker,
            "name": company.name,
        }
    }

@router.get("/", response_model=List[WatchlistResponse])
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's watchlist"""
    watchlist_items = (
        db.query(Watchlist)
        .options(joinedload(Watchlist.company))
        .filter(Watchlist.user_id == current_user.id)
        .order_by(desc(Watchlist.created_at))
        .all()
    )
    
    result = []
    for item in watchlist_items:
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

@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove company from watchlist"""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    watchlist_item = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.company_id == company.id
    ).first()
    
    if not watchlist_item:
        raise HTTPException(status_code=404, detail="Company not in watchlist")
    
    db.delete(watchlist_item)
    db.commit()
    
    return {"status": "success"}


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
    watchlist_items = (
        db.query(Watchlist)
        .options(joinedload(Watchlist.company))
        .filter(Watchlist.user_id == current_user.id)
        .order_by(desc(Watchlist.created_at))
        .all()
    )

    insights: List[WatchlistInsightResponse] = []
    company_ids = [item.company_id for item in watchlist_items if item.company_id]
    if not company_ids:
        return insights

    latest_dates_subq = (
        db.query(
            Filing.company_id,
            func.max(Filing.filing_date).label("latest_date"),
        )
        .filter(Filing.company_id.in_(company_ids))
        .group_by(Filing.company_id)
        .subquery()
    )

    latest_filings = (
        db.query(Filing)
        .join(
            latest_dates_subq,
            (Filing.company_id == latest_dates_subq.c.company_id)
            & (Filing.filing_date == latest_dates_subq.c.latest_date),
        )
        .all()
    )
    latest_filing_by_company = {filing.company_id: filing for filing in latest_filings}

    filing_counts = dict(
        db.query(Filing.company_id, func.count(Filing.id))
        .filter(Filing.company_id.in_(company_ids))
        .group_by(Filing.company_id)
        .all()
    )

    latest_filing_ids = [filing.id for filing in latest_filings]
    summary_by_filing: Dict[int, Summary] = {}
    if latest_filing_ids:
        summaries = (
            db.query(Summary)
            .filter(Summary.filing_id.in_(latest_filing_ids))
            .order_by(desc(Summary.updated_at), desc(Summary.created_at))
            .all()
        )
        for summary in summaries:
            if summary.filing_id not in summary_by_filing:
                summary_by_filing[summary.filing_id] = summary

    for item in watchlist_items:
        company = item.company
        if not company:
            continue

        latest_filing: Optional[Filing] = latest_filing_by_company.get(company.id)
        total_filings = int(filing_counts.get(company.id, 0))

        filing_snapshot: Optional[WatchlistFilingSnapshot] = None

        if latest_filing:
            summary: Optional[Summary] = summary_by_filing.get(latest_filing.id)

            progress_snapshot = get_generation_progress_snapshot(latest_filing.id)

            summary_status = "missing"
            needs_regeneration = True
            summary_id: Optional[int] = None
            summary_created_at: Optional[str] = None
            summary_updated_at: Optional[str] = None

            if summary:
                summary_id = summary.id
                summary_created_at = summary.created_at.isoformat() if summary.created_at else None
                summary_updated_at = summary.updated_at.isoformat() if summary.updated_at else None

                overview = (summary.business_overview or "").lower()
                placeholder_tokens = [
                    "generating summary",
                    "summary temporarily unavailable",
                    "requires openai api key"
                ]
                has_placeholder = any(token in overview for token in placeholder_tokens)

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


class WaitlistJoinRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    referral_code: Optional[str] = None
    source: Optional[str] = None
    honeypot: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = value.strip()
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
    position: int
    referral_code: str
    referral_link: str
    referrals_count: int
    positions_gained: int
    email_verified: bool


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

    if payload.honeypot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid submission.",
        )

    existing = db.query(WaitlistSignup).filter(WaitlistSignup.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": "already_registered",
                "message": "This email is already on the waitlist!",
                "position": calculate_waitlist_position(existing.position, existing.priority_score),
                "referral_code": existing.referral_code,
                "referral_link": build_referral_link(existing.referral_code),
            },
        )

    referrer: Optional[WaitlistSignup] = None
    if payload.referral_code:
        referrer = (
            db.query(WaitlistSignup)
            .filter(WaitlistSignup.referral_code == payload.referral_code)
            .first()
        )
        if not referrer:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "success": False,
                    "error": "invalid_referral",
                    "message": "Referral code not recognized.",
                },
            )
        referrer.priority_score += 1

    total_signups = db.query(func.count(WaitlistSignup.id)).scalar() or 0
    base_position = total_signups + 1
    referral_code = generate_unique_referral_code(db)

    signup = WaitlistSignup(
        email=payload.email,
        name=payload.name,
        referral_code=referral_code,
        referred_by=payload.referral_code,
        source=payload.source,
        position=base_position,
        priority_score=0,
    )
    db.add(signup)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(WaitlistSignup).filter(WaitlistSignup.email == payload.email).first()
        if existing:
            referral_link = build_referral_link(existing.referral_code)
            position = calculate_waitlist_position(existing.position, existing.priority_score)
            return {
                "success": False,
                "error": "already_registered",
                "message": "This email is already on the waitlist!",
                "position": position,
                "referral_code": existing.referral_code,
                "referral_link": referral_link,
            }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create waitlist signup.",
        )

    db.refresh(signup)
    if referrer:
        db.refresh(referrer)

    position = calculate_waitlist_position(signup.position, signup.priority_score)
    referral_link = build_referral_link(signup.referral_code)
    verification_token = create_verification_token(signup.email, signup.referral_code)
    verification_link = build_verification_link(verification_token)

    try:
        await send_waitlist_welcome_email(
            to_email=signup.email,
            name=signup.name,
            position=position,
            referral_link=referral_link,
            verification_link=verification_link,
        )
        signup.welcome_email_sent = True
        db.commit()
    except Exception:
        db.rollback()

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
            pass

    return {
        "success": True,
        "message": "You're on the list!",
        "position": position,
        "referral_code": signup.referral_code,
        "referral_link": referral_link,
        "total_signups": total_signups,
    }


@waitlist_router.get("/status/{email}", response_model=WaitlistStatusResponse)
async def get_waitlist_status(email: EmailStr, db: Session = Depends(get_db)):
    normalized_email = email.strip().lower()
    signup = db.query(WaitlistSignup).filter(WaitlistSignup.email == normalized_email).first()
    if not signup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found on the waitlist.",
        )

    referrals_count = (
        db.query(func.count(WaitlistSignup.id))
        .filter(WaitlistSignup.referred_by == signup.referral_code)
        .scalar()
        or 0
    )
    position = calculate_waitlist_position(signup.position, signup.priority_score)
    return WaitlistStatusResponse(
        position=position,
        referral_code=signup.referral_code,
        referral_link=build_referral_link(signup.referral_code),
        referrals_count=int(referrals_count),
        positions_gained=signup.priority_score * REFERRAL_BONUS,
        email_verified=signup.email_verified,
    )


@waitlist_router.get("/stats")
async def get_waitlist_stats(db: Session = Depends(get_db)):
    total_signups = db.query(func.count(WaitlistSignup.id)).scalar() or 0
    return {"total_signups": int(total_signups)}


@waitlist_router.post("/verify/{token}")
async def verify_waitlist_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
    except JWTError as exc:
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

    signup = db.query(WaitlistSignup).filter(WaitlistSignup.email == email).first()
    if not signup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waitlist entry not found.",
        )

    signup.email_verified = True
    db.commit()

    return {"success": True, "message": "Email verified."}

