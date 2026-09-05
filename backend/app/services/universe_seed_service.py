"""Seed committed-universe Company identities from the SEC ticker file, without generation."""
from typing import Optional

from app.database import SessionLocal
from app.models import Company
from app.services.company_resolution import resolve_or_create_company_by_cik
from app.services.edgar.compat import sec_edgar_service
from app.services.index_membership_service import member_tickers


async def seed_universe_companies(*, apply: bool = False, limit: Optional[int] = None) -> dict:
    """Preview by default; one SEC service fetch, short write transaction per new identity.

    Multiple share classes can map to one CIK; preserve the existing Company's primary ticker
    instead of inventing duplicate issuers or rewriting a canonical ticker to a secondary class.
    New rows need the separately authorized SIC backfill before financial pregeneration.
    """
    members = sorted(member_tickers())
    if not members:
        raise ValueError("Committed universe is unavailable")
    members = members[: min(limit if limit is not None else 1000, 1000)]
    tickers = await sec_edgar_service.get_company_tickers()
    by_ticker = {}
    primary_by_cik = {}
    for row in tickers.values():
        if not isinstance(row, dict):
            continue
        cik = str(row.get("cik_str", ""))
        ticker = row.get("ticker")
        name = row.get("title")
        if not cik.isdigit() or not isinstance(ticker, str) or not isinstance(name, str) or not name.strip():
            continue
        cik = cik.zfill(10)
        normalized = ticker.upper().replace("-", ".")
        by_ticker[normalized] = (cik, ticker.upper(), name)
        primary_by_cik.setdefault(cik, ticker.upper())
    with SessionLocal() as db:
        existing = {str(cik).zfill(10) for (cik,) in db.query(Company.cik).all()}
    stats = {"members": len(members), "created": 0, "would_create": 0, "existing": 0,
             "source_errors": 0, "unresolved_tickers": []}
    for member in members:
        record = by_ticker.get(member.upper().replace("-", "."))
        if record is None:
            stats["source_errors"] += 1
            stats["unresolved_tickers"].append(member)
            continue
        cik, ticker, name = record
        if cik in existing:
            stats["existing"] += 1
            continue
        if apply:
            with SessionLocal() as db:
                resolve_or_create_company_by_cik(
                    db, cik=cik, ticker=primary_by_cik.get(cik, ticker), name=name,
                    path="universe-company-seed",
                )
                db.commit()
            stats["created"] += 1
        else:
            stats["would_create"] += 1
        existing.add(cik)
    return stats
