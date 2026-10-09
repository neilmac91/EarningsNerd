"""Company lookups and read-through persistence behind ``app/routers/companies.py``.

Moved from the router (search, trending, get-by-ticker) so it stays HTTP only. Every function is
one synchronous unit on the request's session and runs where the router used to run it (on the
event loop, between the router's SEC and Yahoo awaits). The units that end a request's database
work snapshot the response identities and close the session in the same unit, so no pooled
connection is held through a slow upstream (``tests/unit/test_company_routes_pool_lifetime.py``).
Outcomes the router turns into a log line or an HTTP error are signalled with
``SearchUpsertConflict`` or a ``None`` return.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, Filing
from app.services.company_resolution import resolve_or_create_company_by_cik


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


def release_company_row(db: Session, company: Company) -> dict:
    """Snapshot one company's response fields, then release the request's connection."""
    company_row = company_identity(company)
    db.close()
    return company_row


def release_company_rows(db: Session, companies: List[Company]) -> List[dict]:
    """Snapshot each company's response fields in order, then release the request's connection."""
    company_rows = [company_identity(company) for company in companies]
    db.close()
    return company_rows


def upsert_search_results(
    db: Session,
    sec_results: List[Dict[str, Any]],
    primary_by_cik: Dict[str, Optional[str]],
) -> List[Company]:
    """Store or update the searched companies, ONE row per CIK, in SEC result order.

    Raises :class:`SearchUpsertConflict` when the flush or commit hits the unique-CIK race.
    """
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
) -> List[Company]:
    """Recover from :class:`SearchUpsertConflict`: roll back, re-resolve each CIK, commit."""
    # The batch rollback discards ALL pending inserts, so re-resolve each CIK individually via
    # the per-row-SAVEPOINT helper — a race on one CIK no longer drops the other genuinely-new
    # companies from the response.
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
    return [by_cik[c] for c in response_ciks]


def trending_company_rows(db: Session, limit: int) -> List[dict]:
    """Companies with the most filings in the last 30 days, as response rows; releases the session."""
    # Get companies with most recent filings in the last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)

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

    company_rows = [
        {
            "id": row.id,
            "cik": row.cik,
            "ticker": row.ticker,
            "name": row.name,
            "exchange": row.exchange,
        }
        for row in trending_query
    ]
    db.close()
    return company_rows


def find_company_row_by_ticker(db: Session, ticker: str) -> Optional[dict]:
    """The stored company's response row, or None on a miss; releases the session either way.

    The miss releases the SELECT's transaction before the router's SEC wait; the Session stays
    reusable for :func:`persist_sec_company`.
    """
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        db.close()
        return None
    return release_company_row(db, company)


def persist_sec_company(db: Session, sec_data: Dict[str, Any], primary: Optional[str]) -> Company:
    """Create or self-heal the Company row for an SEC search hit and commit it.

    Does not release the session: the router snapshots it with :func:`release_company_row`.
    """
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
    return company
