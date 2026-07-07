import asyncio
import logging
from datetime import datetime, timedelta
from app.utils.datetimes import utcnow
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from app.config import settings
from app.database import get_db, SessionLocal
from app.models import Company, Filing
from app.schemas.fundamentals import FundamentalsResponse
# EdgarTools migration: Using new edgar module for SEC services
from app.services.company_resolution import resolve_or_create_company_by_cik
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.exceptions import EdgarError as SECEdgarServiceError
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Constants for filings endpoint configuration
SEC_REQUEST_TIMEOUT_SECONDS = 20.0  # Timeout for SEC EDGAR requests (within frontend's 30s limit)
CACHED_FILINGS_LIMIT = 20  # Maximum number of cached filings to return as fallback

# B2: stale-within-TTL cache for the company filings list. The hot path already persists every SEC
# fetch into the Filing table, so a recently-synced ticker can serve its list straight from the DB
# (~ms) instead of paying the 3-5s SEC round-trip on every load. In-memory by design — single Cloud
# Run instance, Redis off in prod (mirrors companies.py's _quote_cache). Staleness is bounded by the
# TTL; the new-filing ALERT path (filing-scan job) is independent, so users are still notified of new
# filings even if this list lags by up to the TTL.
FILINGS_LIST_TTL = timedelta(hours=3)
MAX_FILINGS_SYNC_ENTRIES = 2000  # bound memory; oldest (ticker,types) key is evicted past this
_filings_synced_at: Dict[Tuple[str, Tuple[str, ...]], datetime] = {}


def _filings_cache_fresh(ticker: str, types_list: List[str]) -> bool:
    """True when this (ticker, types) was synced from SEC within the TTL."""
    synced = _filings_synced_at.get((ticker, tuple(types_list)))
    return synced is not None and (utcnow() - synced) < FILINGS_LIST_TTL


def _mark_filings_synced(ticker: str, types_list: List[str]) -> None:
    """Record a successful live SEC sync for this (ticker, types), evicting the oldest if full."""
    if len(_filings_synced_at) >= MAX_FILINGS_SYNC_ENTRIES:
        _filings_synced_at.pop(next(iter(_filings_synced_at)), None)  # insertion-ordered → oldest
    _filings_synced_at[(ticker, tuple(types_list))] = utcnow()


# In-flight guard for the DB-first background refresh (below): collapses a burst of concurrent loads
# of the same stale (ticker, types) into a single SEC refresh instead of one per request. Per-process
# (mirrors _filings_synced_at); a duplicate on another Cloud Run instance is harmless (idempotent
# upsert). Cleared in the refresh's finally.
_refreshing_keys: set = set()


async def _refresh_company_filings(
    cik: str, ticker_upper: str, types_list: List[str], company_id: int
) -> None:
    """Best-effort background refresh of a company's filings from SEC (DB-first serving).

    Runs AFTER the response is sent (FastAPI BackgroundTasks). Opens its OWN short-lived session —
    never the request-scoped one (which is already closed) — does the now-bounded SEC fetch (QW2:
    one recent-window submissions download, not the full history), upserts via the shared
    ``upsert_filings`` twin, and marks the (ticker, types) synced so the next load takes the fast
    path. Any failure only logs: the user was already served the persisted rows, and the list is
    allowed to lag by ``FILINGS_LIST_TTL``.
    """
    key = (ticker_upper, tuple(types_list))
    if key in _refreshing_keys:
        return  # a refresh for this exact key is already in flight in this process
    _refreshing_keys.add(key)
    db = SessionLocal()
    try:
        sec_filings = await asyncio.wait_for(
            sec_edgar_service.get_filings(cik, types_list),
            timeout=SEC_REQUEST_TIMEOUT_SECONDS,
        )
        company = db.get(Company, company_id)
        if company is None:
            return
        from app.services.filing_scan_service import upsert_filings
        upsert_filings(db, company, sec_filings)
        _mark_filings_synced(ticker_upper, types_list)
    except Exception:
        logger.warning(
            "Background filings refresh failed for %s; serving persisted rows (stale within TTL)",
            ticker_upper,
            exc_info=True,
        )
        db.rollback()
    finally:
        db.close()
        _refreshing_keys.discard(key)


router = APIRouter()


class CompanyInfo(BaseModel):
    id: int
    ticker: str
    name: str
    exchange: Optional[str] = None

class FilingResponse(BaseModel):
    id: Optional[int]
    filing_type: str
    filing_date: str
    report_date: Optional[str]
    accession_number: str
    document_url: str
    sec_url: str
    company: Optional[CompanyInfo] = None
    
    @classmethod
    def from_orm(cls, filing):
        """Convert Filing model to FilingResponse"""
        company_info = None
        if hasattr(filing, 'company') and filing.company:
            company_info = CompanyInfo(
                id=filing.company.id,
                ticker=filing.company.ticker,
                name=filing.company.name,
                exchange=filing.company.exchange
            )
        
        return cls(
            id=filing.id,
            filing_type=filing.filing_type,
            filing_date=filing.filing_date.isoformat() if filing.filing_date else None,
            report_date=filing.period_end_date.isoformat() if filing.period_end_date else None,
            accession_number=filing.accession_number,
            document_url=filing.document_url,
            sec_url=filing.sec_url,
            company=company_info
        )
    
    class Config:
        from_attributes = True

@router.get("/company/{ticker}", response_model=List[FilingResponse])
async def get_company_filings(
    ticker: str,
    background: BackgroundTasks,
    filing_types: Optional[str] = Query(None, description="Comma-separated filing types (e.g., '10-K,10-Q')"),
    db: Session = Depends(get_db)
):
    """Get filings for a company.

    DB-first: once we hold any persisted filings for this company we serve them immediately and
    refresh from SEC in the background, so the request never blocks on a SEC round-trip. Only a
    first-ever view (empty DB) does a synchronous, bounded live fetch. Falls back to cached DB
    filings if SEC EDGAR is slow or unavailable.
    """
    ticker_upper = ticker.upper()
    company = db.query(Company).filter(Company.ticker == ticker_upper).first()

    if not company:
        # Try to fetch company from SEC and create it
        try:
            sec_results = await sec_edgar_service.search_company(ticker)
            if sec_results:
                sec_data = sec_results[0]
                # CIK-first: reuse an existing row for this CIK (e.g. stored under a preferred
                # ticker) instead of 500-ing on the unique-CIK insert (interim safeguard 1).
                # New rows take the canonical primary ticker (P0-1).
                primary = await sec_edgar_service.primary_ticker_for_cik(sec_data["cik"])
                company = resolve_or_create_company_by_cik(
                    db,
                    cik=sec_data["cik"],
                    ticker=primary or sec_data["ticker"],
                    name=sec_data["name"],
                    exchange=sec_data.get("exchange"),
                    path="filings.get_company_filings",
                    canonical_ticker=primary,  # self-heal a stale ticker → primary (P0-1)
                )
                db.commit()
                db.refresh(company)
            else:
                raise HTTPException(status_code=404, detail="Company not found")
        except HTTPException:
            raise
        except SECEdgarServiceError as e:
            raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching company: {str(e)}") from e

    # Parse filing types. Default to the domestic financial reports; when FPI support is enabled,
    # also discover foreign-issuer forms (20-F annual, 6-K interim, 40-F) so ADRs like Alibaba
    # ($BABA) list their filings instead of showing an empty state. An explicit ?filing_types=
    # query always wins. Page-scoped: only this endpoint expands — the dashboard feed / scanner /
    # alerts keep their own form sets (see tasks/fpi-support-roadmap.md, Phase 5).
    if filing_types:
        types_list = [t.strip() for t in filing_types.split(",")]
    elif settings.ENABLE_FPI_FILINGS:
        types_list = ["10-K", "10-Q", "20-F", "6-K", "40-F"]
    else:
        types_list = ["10-K", "10-Q"]

    # Helper to get cached filings from database. joinedload(company) so FilingResponse.from_orm
    # doesn't lazy-load the company per row (this is now the primary serving path, not just fallback).
    def get_cached_filings() -> List[FilingResponse]:
        cached = db.query(Filing).options(joinedload(Filing.company)).filter(
            Filing.company_id == company.id,
            Filing.filing_type.in_(types_list)
        ).order_by(Filing.filing_date.desc()).limit(CACHED_FILINGS_LIMIT).all()
        return [FilingResponse.from_orm(f) for f in cached]

    # B2 fast path: a recently-synced ticker serves its list from the DB (already populated by a
    # prior live fetch) without the 3-5s SEC round-trip. Falls through to the DB-first / live paths
    # on a cold or stale key.
    if _filings_cache_fresh(ticker_upper, types_list):
        cached = get_cached_filings()
        if cached:
            return cached

    # DB-first: we already hold persisted rows for this company (from a prior sync, the filing-scan
    # cron, or precompute), but the freshness stamp is cold/stale (e.g. a fresh Cloud Run instance,
    # or >TTL since last sync). Serve the rows instantly and refresh from SEC in the background —
    # the user never waits on SEC. The refresh is bounded (QW2) and in-flight-deduped. Only a
    # first-ever view with an empty DB (the mega-filer cold case) falls through to a synchronous
    # fetch below.
    cached = get_cached_filings()
    if cached:
        background.add_task(
            _refresh_company_filings, company.cik, ticker_upper, types_list, company.id
        )
        return cached

    try:
        # Try to fetch from SEC with a timeout to ensure we respond within frontend's limit
        sec_filings = await asyncio.wait_for(
            sec_edgar_service.get_filings(company.cik, types_list),
            timeout=SEC_REQUEST_TIMEOUT_SECONDS
        )

        filings = []
        new_filings = []  # Track newly added filings for batch refresh

        # Prefetch existing filings in a single query to avoid an N+1
        # (previously this loop issued one SELECT per SEC filing).
        accession_numbers = [
            f["accession_number"] for f in sec_filings if f.get("accession_number")
        ]
        existing_by_accession = {
            f.accession_number: f
            for f in db.query(Filing)
            .filter(Filing.accession_number.in_(accession_numbers))
            .all()
        } if accession_numbers else {}

        for sec_filing in sec_filings:
            # Validate required fields from SEC response before database operations
            sec_url = sec_filing.get("sec_url")
            document_url = sec_filing.get("document_url")

            # Skip filings with missing required URLs to prevent NOT NULL violations
            if not sec_url:
                logger.warning(
                    f"Skipping filing {sec_filing.get('accession_number')} - missing sec_url"
                )
                continue

            accession_number = sec_filing.get("accession_number")
            if not accession_number:
                logger.warning("Skipping filing - missing accession_number")
                continue

            # Check if filing exists (from the prefetched map — no per-iteration query)
            filing = existing_by_accession.get(accession_number)

            if not filing:
                # Only create new filing if we have all required fields
                if not document_url:
                    logger.warning(
                        f"Skipping new filing {sec_filing.get('accession_number')} - missing document_url"
                    )
                    continue

                filing = Filing(
                    company_id=company.id,
                    accession_number=accession_number,
                    filing_type=sec_filing["filing_type"],
                    filing_date=datetime.fromisoformat(sec_filing["filing_date"]),
                    period_end_date=datetime.fromisoformat(sec_filing["report_date"]) if sec_filing.get("report_date") else None,
                    document_url=document_url,
                    sec_url=sec_url
                )
                db.add(filing)
                new_filings.append(filing)
            else:
                # Update existing filing with new URL format if it's using old format
                # Only update if new values are valid (not None)
                if filing.sec_url and "cgi-bin/viewer" in filing.sec_url:
                    if sec_url and document_url:
                        filing.sec_url = sec_url
                        filing.document_url = document_url
                    else:
                        logger.warning(
                            f"Skipping URL update for filing {filing.accession_number} - "
                            f"new sec_url or document_url is None"
                        )

            filings.append(filing)

        # Batch commit: single transaction for all database changes
        if new_filings or db.dirty:
            db.commit()
            # Refresh new filings to get generated IDs
            for filing in new_filings:
                db.refresh(filing)

        # Mark this (ticker, types) freshly synced so subsequent loads take the B2 fast path.
        _mark_filings_synced(ticker_upper, types_list)

        # Convert to response models after commit
        return [FilingResponse.from_orm(f) for f in filings]

    except asyncio.TimeoutError:
        # SEC EDGAR is slow, fall back to cached data
        logger.warning(f"SEC EDGAR timeout for {ticker_upper}, returning cached filings")
        db.rollback()  # Ensure clean session state
        cached = get_cached_filings()
        if cached:
            return cached
        # No cached data available
        raise HTTPException(
            status_code=503,
            detail="SEC EDGAR is slow to respond and no cached data is available. Please retry in a moment."
        )
    except SECEdgarServiceError as e:
        # SEC EDGAR error, try to return cached data
        logger.warning(f"SEC EDGAR error for {ticker_upper}: {e}, attempting to return cached filings")
        db.rollback()  # Ensure clean session state
        cached = get_cached_filings()
        if cached:
            return cached
        raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
    except Exception as e:
        logger.exception(f"Unexpected error fetching filings for {ticker_upper}")
        # Rollback any pending transaction to recover session state
        db.rollback()
        # Try to return cached data on any error
        cached = get_cached_filings()
        if cached:
            logger.info(f"Returning {len(cached)} cached filings for {ticker_upper} after error")
            return cached
        raise HTTPException(status_code=500, detail=f"Error fetching filings: {str(e)}") from e

@router.get("/{filing_id}", response_model=FilingResponse)
async def get_filing(filing_id: int, db: Session = Depends(get_db)):
    """Get a specific filing"""
    from sqlalchemy.orm import joinedload
    filing = db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id == filing_id).first()
    
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    
    return FilingResponse.from_orm(filing)


class FilingContentResponse(BaseModel):
    filing_id: int
    has_content: bool
    markdown_content: Optional[str] = None


@router.get("/{filing_id}/content", response_model=FilingContentResponse)
async def get_filing_content(filing_id: int, db: Session = Depends(get_db)):
    """Return the cached full-text markdown for a filing (powers the in-app filing viewer).

    Serves ``FilingContentCache.markdown_content`` so the frontend can render the filing on-page and
    scroll/flash-highlight a cited passage in place. This is public SEC data (same content the
    summary cites), so it is not entitlement-gated. Returns 404 when the filing does not exist, or
    200 with ``has_content=false`` when it exists but has no cached markdown yet (caller falls back
    to the SEC deep link).
    """
    from sqlalchemy.orm import joinedload

    filing = (
        db.query(Filing)
        .options(joinedload(Filing.content_cache))
        .filter(Filing.id == filing_id)
        .first()
    )
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    cache = filing.content_cache
    markdown = getattr(cache, "markdown_content", None) if cache else None
    return FilingContentResponse(
        filing_id=filing_id,
        has_content=bool(markdown),
        markdown_content=markdown or None,
    )


@router.get("/{filing_id}/fundamentals", response_model=FundamentalsResponse)
async def get_filing_fundamentals(filing_id: int, db: Session = Depends(get_db)) -> FundamentalsResponse:
    """Annual fundamentals time-series **as reported in this specific filing** (roadmap B).

    Reads the normalized `financial_fact` rows for this `filing_id` (its own comparative years) — an
    immutable, document-faithful snapshot. A single indexed DB read, no live SEC calls. Returns empty
    `concepts` when the filing's facts aren't populated yet (they backfill when it's summarized).
    """
    from app.services import facts_service

    data = facts_service.get_filing_fundamentals(db, filing_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Filing not found")
    return data


@router.get("/recent/latest", response_model=List[FilingResponse])
async def get_recent_filings(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recent filings across all companies"""
    from sqlalchemy import desc
    from sqlalchemy.orm import joinedload
    # Use joinedload to eagerly load company relationship, avoiding N+1 queries
    filings = db.query(Filing).options(joinedload(Filing.company)).order_by(desc(Filing.filing_date)).limit(limit).all()

    return [FilingResponse.from_orm(filing) for filing in filings]


