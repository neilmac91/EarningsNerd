"""Upcoming earnings calendar for a user's watched companies (Phase 3).

Backed by FMP (`fmp_client.fetch_upcoming_earnings`), filtered to the tickers the user tracks. The
FMP client is injectable for tests and returns ``{}`` when ``FMP_API_KEY`` is unset, so this
degrades to an empty calendar in CI / before a key is provisioned — never raising on the render path.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Company, Watchlist

logger = logging.getLogger(__name__)


async def upcoming_for_user(db: Session, user_id: int, *, fmp=None, days_ahead: int = 14) -> list[dict]:
    """Return upcoming earnings events for the user's watched tickers, soonest first."""
    if fmp is None:
        from app.integrations.fmp import fmp_client
        fmp = fmp_client

    rows = (
        db.query(Company.ticker, Company.name)
        .join(Watchlist, Watchlist.company_id == Company.id)
        .filter(Watchlist.user_id == user_id)
        .all()
    )
    if not rows:
        return []
    name_by_ticker = {ticker.upper(): name for ticker, name in rows if ticker}

    try:
        events = await fmp.fetch_upcoming_earnings(days_ahead=days_ahead)
    except Exception as e:  # never let a flaky integration break the dashboard
        logger.warning("Upcoming earnings fetch failed: %s", e)
        return []

    out: list[dict] = []
    for symbol, event in (events or {}).items():
        sym = symbol.upper()
        if sym not in name_by_ticker:
            continue
        earnings_date = getattr(event, "earnings_date", None)
        out.append({
            "ticker": sym,
            "company_name": name_by_ticker[sym],
            "earnings_date": earnings_date.isoformat() if earnings_date else None,
            "time": getattr(event, "time", None),
            "eps_estimated": getattr(event, "eps_estimated", None),
            "revenue_estimated": getattr(event, "revenue_estimated", None),
        })
    out.sort(key=lambda e: e["earnings_date"] or "9999")
    return out
