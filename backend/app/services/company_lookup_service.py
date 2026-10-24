"""Company lookups and read-through persistence behind ``app/routers/companies.py``.

Moved from the router (search, trending, get-by-ticker) so it stays HTTP only. Each function the
router calls is one synchronous unit on the request's session, which the router runs in the thread
pool between its SEC and Yahoo awaits, so its checkout never waits on the event loop. Each unit
snapshots its response rows, then releases the request's pooled connection in a ``finally``
(:func:`~app.services.filing_list_service.release_request_session`), so none is held through a slow
upstream or left for the dependency's finalizer (``tests/unit/test_company_routes_pool_lifetime.py``
and ``tests/unit/test_cached_filings_pool_lifetime.py``; the filing routes follow the same rule,
``lessons/ops-release-cached-filing-reads-before-yield.md``). The snapshot must precede the release
inside one unit: after a commit the rows are expired, and the release expunges them, so a read after
it raises DetachedInstanceError (a 500) instead of serving the row. The Session object stays
reusable after a release, which the get-by-ticker miss path and the search's conflict recovery rely
on. Outcomes the router turns into a log line or an HTTP error are signalled with
``SearchUpsertConflict`` or a ``None`` return.
"""
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, Filing
from app.services.company_resolution import resolve_or_create_company_by_cik
from app.services.filing_list_service import release_request_session
from app.services.latest_filing_service import LatestFilingRef, latest_filings
from app.utils.datetimes import utcnow


class SearchUpsertConflict(Exception):
    """A concurrent request inserted one of these CIKs between the read and the flush.

    The router logs ``company_upsert_conflict`` and calls :func:`resolve_search_conflict`.
    """

    def __init__(self, response_ciks: List[str]) -> None:
        super().__init__(",".join(response_ciks))
        self.response_ciks = response_ciks


def company_identity(company: Company) -> dict:
    """Snapshot response fields before the request Session is released for network I/O."""
    return {
        "id": company.id,
        "cik": company.cik,
        "ticker": company.ticker,
        "name": company.name,
        "exchange": company.exchange,
    }


def _search_rows(db: Session, companies: List[Company]) -> Tuple[List[dict], Dict[int, LatestFilingRef]]:
    """Each company's response fields in order, and the filing each company page leads with (keyed by
    company id, absent when none is stored)."""
    company_rows = [company_identity(company) for company in companies]
    return company_rows, latest_filings(db, [row["id"] for row in company_rows])


def upsert_search_results(
    db: Session,
    sec_results: List[Dict[str, Any]],
    primary_by_cik: Dict[str, Optional[str]],
) -> Tuple[List[dict], Dict[int, LatestFilingRef]]:
    """Store or update the searched companies, ONE row per CIK, in SEC result order, and return
    their response rows and lead filings; releases the session.

    Raises :class:`SearchUpsertConflict` when the flush or commit hits the unique-CIK race, after
    the release has rolled the batch back.
    """
    try:
        return _search_rows(db, _upsert_companies(db, sec_results, primary_by_cik))
    finally:
        release_request_session(db)


def _upsert_companies(
    db: Session,
    sec_results: List[Dict[str, Any]],
    primary_by_cik: Dict[str, Optional[str]],
) -> List[Company]:
    """The searched companies' rows, stored or updated and committed, in SEC result order."""
    # Store or update companies in database — ONE row per CIK (data-quality plan P0-1).
    # SEC's ticker file carries one entry per LISTED SECURITY: iterating it raw returned N
    # duplicate rows per company and let the LAST entry's ticker win the persisted row
    # (preferred classes sort last in the file — that is how JPMorgan became "JPM-PM" and
    # served the preferred share's quote as its stock price).
    companies: List[Company] = []
    ciks = [result["cik"] for result in sec_results if result.get("cik")]
    existing_companies: Dict[str, Company] = {}
    if ciks:
        existing = db.query(Company).filter(Company.cik.in_(ciks)).all()
        existing_companies = {company.cik: company for company in existing}

    new_companies: List[Company] = []
    updated_companies: List[Company] = []
    seen_ciks: set = set()
    response_ciks: List[str] = []

    for sec_data in sec_results:
        cik = sec_data.get("cik")
        if not cik or cik in seen_ciks:
            continue  # one response row per company, not per listed share class
        seen_ciks.add(cik)

        # The canonical listing ticker — NEVER assigned from the per-entry sec_data, which
        # for a multi-class issuer can be any share class. None (CIK absent from the file,
        # e.g. delisted) leaves an existing row's ticker unchanged.
        primary = primary_by_cik[cik]

        company = existing_companies.get(cik)
        if not company:
            company = Company(
                cik=cik,
                ticker=primary or sec_data.get("ticker"),
                name=sec_data.get("name"),
                exchange=sec_data.get("exchange"),
            )
            db.add(company)
            new_companies.append(company)
        else:
            updated = False
            name = sec_data.get("name")
            exchange = sec_data.get("exchange")

            # Ticker updates only TO the canonical primary: permits real renames, forbids
            # preferred-class downgrades (the pre-P0-1 last-write-wins corruption).
            if primary and company.ticker != primary:
                company.ticker = primary
                updated = True
            if name and company.name != name:
                company.name = name
                updated = True
            if company.exchange != exchange:
                company.exchange = exchange
                updated = True

            if updated:
                updated_companies.append(company)

        companies.append(company)
        response_ciks.append(cik)

    if new_companies or updated_companies:
        try:
            with db.begin_nested():  # SAVEPOINT: a concurrent-search race must not 500
                db.flush()
            db.commit()
            for company in new_companies:
                db.refresh(company)
        except IntegrityError as exc:
            raise SearchUpsertConflict(response_ciks) from exc

    return companies


def resolve_search_conflict(
    db: Session,
    sec_results: List[Dict[str, Any]],
    primary_by_cik: Dict[str, Optional[str]],
    response_ciks: List[str],
) -> Tuple[List[dict], Dict[int, LatestFilingRef]]:
    """Recover from :class:`SearchUpsertConflict`: re-resolve each CIK, commit, and return the
    response rows and lead filings in SEC order; releases the session."""
    # The failed batch's release rolled back ALL its pending inserts (and the rollback below any a
    # caller left unreleased), so re-resolve each CIK individually via the per-row-SAVEPOINT helper —
    # a race on one CIK no longer drops the other genuinely-new companies from the response.
    try:
        db.rollback()
        by_cik: Dict[str, Company] = {}
        for cik in response_ciks:
            sec_data = next(r for r in sec_results if r.get("cik") == cik)
            primary = primary_by_cik[cik]
            by_cik[cik] = resolve_or_create_company_by_cik(
                db,
                cik=cik,
                ticker=primary or sec_data.get("ticker"),
                name=sec_data.get("name"),
                exchange=sec_data.get("exchange"),
                path="companies.search",
                canonical_ticker=primary,
            )
        db.commit()
        return _search_rows(db, [by_cik[c] for c in response_ciks])
    finally:
        release_request_session(db)


def trending_company_rows(db: Session, limit: int) -> List[dict]:
    """Companies with the most filings in the last 30 days, as response rows; releases the session."""
    # Get companies with most recent filings in the last 30 days. Filing dates are stored as UTC, so
    # the bound is the UTC instant, never the process's local wall clock.
    thirty_days_ago = utcnow() - timedelta(days=30)

    try:
        # Get companies with most filings in recent period
        trending_query = db.query(
            Company.id,
            Company.cik,
            Company.ticker,
            Company.name,
            Company.exchange,
            func.count(Filing.id).label('filing_count')
        ).join(
            Filing, Company.id == Filing.company_id
        ).filter(
            Filing.filing_date >= thirty_days_ago
        ).group_by(
            Company.id
        ).order_by(
            desc('filing_count')
        ).limit(limit).all()

        return [
            {
                "id": row.id,
                "cik": row.cik,
                "ticker": row.ticker,
                "name": row.name,
                "exchange": row.exchange,
            }
            for row in trending_query
        ]
    finally:
        release_request_session(db)


def find_company_row_by_ticker(db: Session, ticker: str) -> Optional[dict]:
    """The stored company's response row, or None on a miss; releases the session either way, so the
    miss path's SEC awaits hold no connection. The Session stays reusable for
    :func:`persist_sec_company`.
    """
    try:
        company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
        return None if company is None else company_identity(company)
    finally:
        release_request_session(db)


def persist_sec_company(db: Session, sec_data: Dict[str, Any], primary: Optional[str]) -> dict:
    """Create or self-heal the Company row for an SEC search hit, commit it, and return its response
    row; releases the session.

    Any exception propagates to the router's miss-path handlers unchanged.
    """
    try:
        # CIK-first: when this CIK already has a row under another ticker (e.g. a
        # preferred-class overwrite like JPM-PM), reuse it instead of 500-ing on the
        # unique-CIK insert (data-quality plan, interim safeguard 1). A genuinely-new
        # row gets the CANONICAL primary ticker, not whatever class was queried (P0-1).
        company = resolve_or_create_company_by_cik(
            db,
            cik=sec_data["cik"],
            ticker=primary or sec_data["ticker"],
            name=sec_data["name"],
            exchange=sec_data.get("exchange"),
            path="companies.get_company",
            canonical_ticker=primary,  # self-heal a stale JPM-PM row → JPM (P0-1)
        )
        db.commit()
        db.refresh(company)
        return company_identity(company)
    finally:
        release_request_session(db)
