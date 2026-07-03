"""Upcoming earnings calendar for a user's watched companies (dashboard).

Now served from the owned `earnings_events` table (strategy §3.2) — the FMP calendar path is retired.
Reads are DB-only (no provider call on the render path) and filtered to the tickers the user tracks;
degrades to an empty calendar if the table isn't seeded yet, never raising on the render path.

Response shape is unchanged from the FMP era (dashboard.py's CalendarEvent contract), so the
frontend needs no change: ``eps_estimated`` comes from the event, ``revenue_estimated`` is always
None (the engine doesn't carry a revenue estimate).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Company, EarningsEvent, Watchlist

logger = logging.getLogger(__name__)


async def upcoming_for_user(db: Session, user_id: int, *, days_ahead: int = 14, **_ignored) -> list[dict]:
    """Return upcoming earnings events for the user's watched tickers, soonest first.

    ``**_ignored`` keeps the old ``fmp=`` keyword accepted (some callers/tests still pass it) without
    doing anything — the FMP dependency is gone.
    """
    rows = (
        db.query(Company.ticker, Company.name)
        .join(Watchlist, Watchlist.company_id == Company.id)
        .filter(Watchlist.user_id == user_id)
        .all()
    )
    if not rows:
        return []
    name_by_ticker = {t.upper(): n for t, n in rows if t}
    tickers = list(name_by_ticker.keys())

    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    try:
        events = (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.ticker.in_(tickers),
                EarningsEvent.event_date >= today,
                EarningsEvent.event_date <= horizon,
            )
            .order_by(EarningsEvent.event_date.asc())
            .all()
        )
    except Exception as e:  # never let a query hiccup break the dashboard
        logger.warning("Upcoming earnings fetch failed: %s", e)
        return []

    out: list[dict] = []
    for ev in events:
        eps = ev.eps_estimate
        out.append({
            "ticker": ev.ticker,
            "company_name": name_by_ticker.get(ev.ticker, ev.company_name or ev.ticker),
            "earnings_date": ev.event_date.isoformat() if ev.event_date else None,
            "time": ev.event_time,
            "eps_estimated": float(eps) if eps is not None else None,
            "revenue_estimated": None,
        })
    out.sort(key=lambda e: e["earnings_date"] or "9999")
    return out
