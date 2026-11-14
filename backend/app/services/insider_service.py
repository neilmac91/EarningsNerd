"""Insider activity (SEC Form 4) as the endpoint serves it: read from the store, never from SEC (ADR 0009).

A background scan fills the store a few filings at a time (``insider_scan_service``). This module reads what is
stored for a company, aggregates it over the reader's trailing window, and says how far the scan has got. The
aggregation is ``ownership_extractor``'s and is pure, so a different window is a different slice of the same rows.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Company
from app.models.insider import InsiderTransaction
from app.services import insider_scan_service
from app.services.ownership_extractor import summarize_insider_activity, transactions_in_window
from app.utils.datetimes import iso_z, utcnow
from app.utils.sec_urls import normalize_cik

# How many individual transactions to return in the response (most recent first).
DEFAULT_RECENT_LIMIT = 30


def _row(trade: InsiderTransaction) -> dict:
    return {
        "insider_name": trade.insider_name, "insider_title": trade.insider_title,
        "is_director": trade.is_director, "is_officer": trade.is_officer, "is_ten_pct_owner": trade.is_ten_pct_owner,
        "ticker": trade.ticker,
        "transaction_date": trade.transaction_date.isoformat() if trade.transaction_date else None,
        "transaction_code": trade.transaction_code, "transaction_label": trade.transaction_label,
        "shares": trade.shares, "price": trade.price, "value": trade.value,
        "acquired_disposed": trade.acquired_disposed, "is_10b5_1": trade.is_10b5_1,
        "accession": trade.accession, "filed_date": trade.filed_date.isoformat() if trade.filed_date else None,
    }


def _sort_recent(transactions: list[dict]) -> list[dict]:
    """Most recent first, by transaction date (falling back to filed date)."""
    return sorted(transactions, key=lambda row: row["transaction_date"] or row["filed_date"] or "", reverse=True)


def read_insider_activity(
    db: Session,
    ticker: str,
    *,
    window_days: int = 90,
    recent_limit: int = DEFAULT_RECENT_LIMIT,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """The stored insider activity of the company with this ticker, and its scan's state; None when no stored
    company has the ticker. ``scan_due`` says a scan step would do something now; the caller hands one off."""
    now = now or utcnow()
    company = db.query(Company).filter(Company.ticker == ticker.upper().strip()).first()
    if company is None:
        return None
    try:
        cik = normalize_cik(company.cik)
    except ValueError:
        return None   # a company row without a real CIK has no filings to scan
    transactions = [_row(trade) for trade in db.query(InsiderTransaction).filter(InsiderTransaction.issuer_cik == cik)]
    today = now.date()
    # One slice for the list, the count and the summary, so a 30-day response never lists a trade outside its
    # window or reports a total that disagrees with the signal.
    windowed = transactions_in_window(transactions, window_days, now=today)
    view = insider_scan_service.scan_view(db, cik, now=now)
    # A step for this issuer is handed off only while few enough other issuers are scanning (the worker is shared).
    due = view.due and (
        insider_scan_service.scans_under_way(db, excluding=cik, now=now) < insider_scan_service.MAX_SCANS_UNDER_WAY)
    return {
        "ticker": company.ticker,
        "company_name": company.name,
        "cik": cik,
        "window_days": window_days,
        "summary": summarize_insider_activity(transactions, window_days=window_days, now=today),
        "transactions": _sort_recent(windowed)[:recent_limit],
        "total_transactions": len(windowed),
        "scan": {
            "status": view.status,
            "filings_listed": view.filings_listed,
            "filings_read": view.filings_read,
            "oldest_filed_date": view.oldest_filed_date.isoformat() if view.oldest_filed_date else None,
            "refreshed_at": iso_z(view.refreshed_at) if view.refreshed_at else None,
            "retry_after_seconds": view.retry_after_seconds,
        },
        "scan_due": due,
    }
