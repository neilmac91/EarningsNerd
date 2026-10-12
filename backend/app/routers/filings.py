import asyncio
import logging
import json
from app.utils.datetimes import utcnow
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.schemas.fundamentals import FundamentalsResponse
# EdgarTools migration: Using new edgar module for SEC services
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.exceptions import EdgarError as SECEdgarServiceError
from app.services.durable_tasks import enqueue_task, TaskUnavailable
from app.services import filing_list_service, filing_read_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# The durable-task handoff stays here: it does no database work, and its outage warning keeps the
# app.routers.filings logger name. Bounded by filing_list_service.MAX_FILINGS_SYNC_ENTRIES.
_visit_task_handoffs: dict[str, float] = {}


async def _enqueue_visit_task(kind: str, payload: dict, *, key: str, seconds: int) -> None:
    """A queue outage must not hide already-persisted filings from the reader."""
    cache_key = f"{kind}:{key}:{json.dumps(payload, sort_keys=True)}"
    now = utcnow().timestamp()
    if now < _visit_task_handoffs.get(cache_key, 0):
        return
    try:
        await enqueue_task(kind, payload, dedupe_key=key, dedupe_seconds=seconds)
        expires = (int(now) // seconds + 1) * seconds
    except (TaskUnavailable, ValueError):
        logger.warning("On-visit task handoff unavailable kind=%s", kind)
        expires = now + 10  # a brief outage cooldown keeps cached page loads fast
    if len(_visit_task_handoffs) >= filing_list_service.MAX_FILINGS_SYNC_ENTRIES:
        _visit_task_handoffs.pop(next(iter(_visit_task_handoffs)), None)
    _visit_task_handoffs[cache_key] = expires


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
    superseded_by_accession: Optional[str] = None
    
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
            company=company_info,
            superseded_by_accession=getattr(filing, "superseded_by_accession", None),
        )
    
    class Config:
        from_attributes = True

@router.get("/company/{ticker}", response_model=List[FilingResponse])
async def get_company_filings(
    ticker: str,
    background: BackgroundTasks,
    filing_types: Optional[str] = Query(None, description="Comma-separated filing types (e.g., '10-K,10-Q')"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max filings to return; default serves the recent cap"),
    db: Session = Depends(get_db, scope="function")
):
    """Get filings for a company.

    DB-first: once we hold any persisted filings for this company we serve them immediately and
    refresh from SEC in the background, so the request never blocks on a SEC round-trip. Only a
    first-ever view (empty DB) does a synchronous, bounded live fetch. Falls back to cached DB
    filings if SEC EDGAR is slow or unavailable.
    """
    ticker_upper = ticker.upper()
    company = filing_list_service.company_by_ticker(db, ticker_upper)

    if not company:
        # Try to fetch company from SEC and create it
        # The initial lookup opened a read transaction. Release it before SEC network I/O; this
        # Session remains reusable for the short persistence unit after the await.
        filing_list_service.release_request_session(db)
        try:
            sec_results = await sec_edgar_service.search_company(ticker)
            if sec_results:
                sec_data = sec_results[0]
                # CIK-first: reuse an existing row for this CIK (e.g. stored under a preferred
                # ticker) instead of 500-ing on the unique-CIK insert (interim safeguard 1).
                # New rows take the canonical primary ticker (P0-1).
                primary = await sec_edgar_service.primary_ticker_for_cik(sec_data["cik"])
                company = filing_list_service.persist_sec_company(db, sec_data, primary)
            else:
                raise HTTPException(status_code=404, detail="Company not found")
        except HTTPException:
            raise
        except SECEdgarServiceError as e:
            raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching company: {str(e)}") from e

    types_list = filing_list_service.requested_filing_types(filing_types)
    company_id = company.id
    company_cik = company.cik
    needs_history_backfill = company.history_backfilled_at is None

    # Helpers to get cached filings from database; each builds its DTOs, then releases the session.
    def get_cached_filings() -> List[FilingResponse]:
        return filing_list_service.cached_filings(
            db, company_id, types_list, limit, FilingResponse.from_orm
        )

    def get_cached_filings_after_rollback() -> List[FilingResponse]:
        return filing_list_service.cached_filings_after_rollback(
            db, company_id, types_list, limit, FilingResponse.from_orm
        )

    # P1-6: enqueue a one-time deep-history backfill the first time this company is viewed. Guarded
    # by the stamp so it never re-walks a company; runs in the background so the page never waits on
    # the EFTS round-trips. Serving still uses whatever rows exist now; the backfill surfaces on the
    # next full-history fetch.
    if settings.ENABLE_HISTORY_BACKFILL_ON_VISIT and needs_history_backfill:
        if settings.DURABLE_TASKS_ENABLED:
            # Release the serving read before any queue/control-plane wait.
            filing_list_service.release_request_session(db)
            await _enqueue_visit_task(
                "history", {"company_id": company_id}, key=f"history:{company_id}", seconds=300,
            )
        else:
            background.add_task(filing_list_service.run_history_backfill_on_visit, company_id)

    # B2 fast path: a recently-synced ticker serves its list from the DB (already populated by a
    # prior live fetch) without the 3-5s SEC round-trip. Falls through to the DB-first / live paths
    # on a cold or stale key.
    if filing_list_service.filings_cache_fresh(ticker_upper, types_list):
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
        if settings.DURABLE_TASKS_ENABLED:
            await _enqueue_visit_task(
                "filings", {"company_id": company_id, "filing_types": types_list},
                key=f"filings:{company_id}",
                seconds=int(filing_list_service.FILINGS_LIST_TTL.total_seconds()),
            )
        else:
            background.add_task(
                filing_list_service.refresh_company_filings,
                company_cik, ticker_upper, types_list, company_id,
            )
        return cached

    try:
        # Try to fetch from SEC with a timeout to ensure we respond within frontend's limit
        # Both DB reads above are complete. Do not retain their connection during the bounded fetch.
        filing_list_service.release_request_session(db)
        sec_filings = await asyncio.wait_for(
            sec_edgar_service.get_filings(company_cik, types_list),
            timeout=filing_list_service.SEC_REQUEST_TIMEOUT_SECONDS
        )

        # Persist and commit the listing, then convert it to response models (still inside this
        # try, so the finally below releases the session only after the DTOs exist).
        return filing_list_service.persist_live_filings(
            db, ticker_upper, types_list, company_id, sec_filings, FilingResponse.from_orm
        )

    except asyncio.TimeoutError:
        # SEC EDGAR is slow, fall back to cached data
        logger.warning(f"SEC EDGAR timeout for {ticker_upper}, returning cached filings")
        cached = get_cached_filings_after_rollback()  # Ensure clean session state
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
        cached = get_cached_filings_after_rollback()  # Ensure clean session state
        if cached:
            return cached
        raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
    except Exception as e:
        logger.exception(f"Unexpected error fetching filings for {ticker_upper}")
        # Rollback any pending transaction to recover session state, then try to return cached
        # data on any error
        cached = get_cached_filings_after_rollback()
        if cached:
            logger.info(f"Returning {len(cached)} cached filings for {ticker_upper} after error")
            return cached
        raise HTTPException(status_code=500, detail=f"Error fetching filings: {str(e)}") from e
    finally:
        # Live results and error fallbacks also finish their DTOs before dependency cleanup.
        filing_list_service.release_request_session(db)

@router.get("/{filing_id}", response_model=FilingResponse)
async def get_filing(filing_id: int, db: Session = Depends(get_db)):
    """Get a specific filing"""
    filing = filing_read_service.filing_by_id(db, filing_id, FilingResponse.from_orm)
    if filing is None:
        raise HTTPException(status_code=404, detail="Filing not found")
    return filing


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
    def build(markdown: Optional[str]) -> FilingContentResponse:
        return FilingContentResponse(
            filing_id=filing_id,
            has_content=bool(markdown),
            markdown_content=markdown or None,
        )

    content = filing_read_service.filing_content(db, filing_id, build)
    if content is None:
        raise HTTPException(status_code=404, detail="Filing not found")
    return content


@router.get("/{filing_id}/fundamentals", response_model=FundamentalsResponse)
async def get_filing_fundamentals(filing_id: int, db: Session = Depends(get_db)) -> FundamentalsResponse:
    """Annual fundamentals time-series **as reported in this specific filing** (roadmap B).

    Reads the normalized `financial_fact` rows for this `filing_id` (its own comparative years) — an
    immutable, document-faithful snapshot. A single indexed DB read, no live SEC calls. Returns empty
    `concepts` when the filing's facts aren't populated yet (they backfill when it's summarized).
    """
    data = filing_read_service.filing_fundamentals(db, filing_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Filing not found")
    return data


@router.get("/recent/latest", response_model=List[FilingResponse])
async def get_recent_filings(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recent filings across all companies"""
    return filing_read_service.recent_filings(db, limit, FilingResponse.from_orm)
