"""Watchlist reads and writes behind ``app/routers/watchlist.py`` (add / list / remove / insights).

Moved verbatim from the router so it stays HTTP only. Outcomes the router turns into an HTTP error
are small exceptions defined here; the router maps each to its unchanged ``HTTPException``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.models import Company, Filing, Summary, Watchlist


class WatchlistCompanyNotFound(Exception):
    """No company row carries this ticker (router: 404 "Company not found")."""


class AlreadyOnWatchlist(Exception):
    """The user already watches this company (router: 400 "Company already in watchlist")."""


class NotOnWatchlist(Exception):
    """The user does not watch this company (router: 404 "Company not in watchlist")."""


def _company_by_ticker(db: Session, ticker: str) -> Company:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise WatchlistCompanyNotFound(ticker)
    return company


def add_company(db: Session, user_id: int, ticker: str) -> tuple[Watchlist, Company]:
    company = _company_by_ticker(db, ticker)

    # Check if already in watchlist
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == user_id,
        Watchlist.company_id == company.id
    ).first()

    if existing:
        raise AlreadyOnWatchlist(ticker)

    watchlist_item = Watchlist(
        user_id=user_id,
        company_id=company.id
    )
    db.add(watchlist_item)
    db.commit()
    db.refresh(watchlist_item)
    return watchlist_item, company


def list_items(db: Session, user_id: int) -> List[Watchlist]:
    return (
        db.query(Watchlist)
        .options(joinedload(Watchlist.company))
        .filter(Watchlist.user_id == user_id)
        .order_by(desc(Watchlist.created_at))
        .all()
    )


def remove_company(db: Session, user_id: int, ticker: str) -> None:
    company = _company_by_ticker(db, ticker)

    watchlist_item = db.query(Watchlist).filter(
        Watchlist.user_id == user_id,
        Watchlist.company_id == company.id
    ).first()

    if not watchlist_item:
        raise NotOnWatchlist(ticker)

    db.delete(watchlist_item)
    db.commit()


@dataclass(frozen=True)
class WatchlistInsightRows:
    watchlist_items: List[Watchlist]
    latest_filing_by_company: Dict[int, Filing]
    filing_counts: Dict[int, int]
    summary_by_filing: Dict[int, Summary]


def load_insight_rows(db: Session, user_id: int) -> Optional[WatchlistInsightRows]:
    """None when no watched row carries a company id (the router answers ``[]``)."""
    watchlist_items = list_items(db, user_id)

    company_ids = [item.company_id for item in watchlist_items if item.company_id]
    if not company_ids:
        return None

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
        .order_by(desc(Filing.id))
        .all()
    )
    # Same-day tie-break: a company that files (e.g.) a 10-K and a 10-Q on the same date matches the
    # max-date join twice. Order by id desc and keep the FIRST (highest id) so "latest filing" is
    # deterministic — mirrors the dashboard feed's (filing_date, id) desc tie-break so the insights
    # page and the "Your companies" rows it powers land on the same filing.
    latest_filing_by_company: Dict[int, Filing] = {}
    for filing in latest_filings:
        latest_filing_by_company.setdefault(filing.company_id, filing)

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

    return WatchlistInsightRows(
        watchlist_items=watchlist_items,
        latest_filing_by_company=latest_filing_by_company,
        filing_counts=filing_counts,
        summary_by_filing=summary_by_filing,
    )
