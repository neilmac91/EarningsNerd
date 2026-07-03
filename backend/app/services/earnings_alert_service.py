"""Earnings-day alerts — per-company opt-in with a per-plan cap, plus the morning digest send.

The subscription is a boolean on the user's ``Watchlist`` row (``earnings_alert``), not a new table:
an alert only makes sense for a company you follow, so enabling one ensures the company is watched.
Watchlists stay unlimited; the cap is purely on how many companies may have the alert ON:

  Free = 3   — a VISIBLE product surface (the 4th enable returns a 403 with an upsell + the
               machine-readable ``earnings_alert_limit`` code the frontend keys on)
  Pro  = 100 — an INVISIBLE anti-abuse guardrail (nothing surfaces it; only the 101st enable
               returns a terse generic 403 with NO code — the frontend renders it verbatim)

Enforced in one place (`set_earnings_alert`) so the rule has a single home, mirroring how
``monthly_summary_limit`` is enforced. The digest reuses the existing email machinery and dedups on
``(user, event, event_date)`` so a moved date re-alerts while an old send can't fire twice.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Awaitable, Callable, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, EarningsAlertLog, EarningsEvent, User, Watchlist
from app.models.notifications import CHANNEL_EMAIL
from app.services.entitlements import Plan, get_entitlements

logger = logging.getLogger(__name__)


class EarningsAlertLimitError(Exception):
    """Raised when enabling an alert would exceed the user's plan cap. Carries the plan so the
    router can render the tier-appropriate 403 (Free: visible upsell + code; Pro: terse, no code)."""

    def __init__(self, *, plan_is_pro: bool, limit: int) -> None:
        self.plan_is_pro = plan_is_pro
        self.limit = limit
        super().__init__("earnings alert limit reached")


class CompanyNotResolvable(Exception):
    """Raised when a ticker can't be resolved to a company to attach the alert to."""


def count_enabled(db: Session, user_id: int) -> int:
    # Count DISTINCT companies, not rows: the watchlist table has no UNIQUE(user_id, company_id),
    # so a duplicate row must not inflate the cap accounting.
    return (
        db.query(func.count(func.distinct(Watchlist.company_id)))
        .filter(Watchlist.user_id == user_id, Watchlist.earnings_alert.is_(True))
        .scalar()
        or 0
    )


def enabled_tickers(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(Company.ticker)
        .join(Watchlist, Watchlist.company_id == Company.id)
        .filter(Watchlist.user_id == user_id, Watchlist.earnings_alert.is_(True))
        .all()
    )
    return [t.upper() for (t,) in rows if t]


def _get_or_create_company(db: Session, ticker: str) -> Company:
    """Resolve a ticker to a Company row, borrowing CIK/name from a known earnings_event when the
    company hasn't been persisted yet (companies are created on-demand). Raises CompanyNotResolvable
    when there is no CIK to satisfy the NOT NULL/unique constraint."""
    ticker = ticker.upper()
    company = db.query(Company).filter(func.upper(Company.ticker) == ticker).first()
    if company is not None:
        return company
    ev = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.ticker == ticker, EarningsEvent.cik.isnot(None))
        .order_by(EarningsEvent.event_date.desc())
        .first()
    )
    if ev is None or not ev.cik:
        raise CompanyNotResolvable(ticker)
    cik = str(ev.cik)
    company = Company(cik=cik, ticker=ticker, name=ev.company_name or ticker)
    try:
        with db.begin_nested():  # SAVEPOINT so a unique-CIK clash doesn't poison the transaction
            db.add(company)
            db.flush()
    except IntegrityError:
        # The CIK already exists under a different ticker (e.g. a ticker rename). Reuse that row
        # rather than 500-ing on the unique constraint.
        company = db.query(Company).filter(Company.cik == cik).first()
        if company is None:
            raise CompanyNotResolvable(ticker)
    return company


def set_earnings_alert(db: Session, user: User, ticker: str, enabled: bool) -> bool:
    """Enable/disable the earnings-day alert for ``ticker``. Enabling enforces the plan cap and
    ensures the company is on the user's watchlist. Disabling is always allowed. Returns the new
    on/off state. Raises EarningsAlertLimitError (cap) or CompanyNotResolvable (unknown ticker)."""
    ticker = ticker.upper()

    if not enabled:
        row = (
            db.query(Watchlist)
            .join(Company, Watchlist.company_id == Company.id)
            .filter(Watchlist.user_id == user.id, func.upper(Company.ticker) == ticker)
            .first()
        )
        if row is not None and row.earnings_alert:
            row.earnings_alert = False
            db.commit()
        return False

    ent = get_entitlements(user)
    company = _get_or_create_company(db, ticker)
    row = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user.id, Watchlist.company_id == company.id)
        .first()
    )
    if row is not None and row.earnings_alert:
        return True  # already on — idempotent, doesn't consume a new slot

    # Cap check: count of currently-enabled alerts. Enabling a not-yet-enabled company adds one.
    if count_enabled(db, user.id) >= ent.earnings_alert_limit:
        raise EarningsAlertLimitError(plan_is_pro=ent.plan is Plan.PRO, limit=ent.earnings_alert_limit)

    if row is None:
        row = Watchlist(user_id=user.id, company_id=company.id, earnings_alert=True)
        db.add(row)
    else:
        row.earnings_alert = True
    db.commit()
    return True


# --------------------------------------------------------------------------- digest send

SendEarningsAlert = Callable[..., Awaitable[None]]


async def send_earnings_day_alerts(
    db: Session,
    *,
    today: Optional[date] = None,
    sender: Optional[SendEarningsAlert] = None,
) -> dict:
    """Send one batched email per opted-in user whose watched companies report today, then record
    the dedup ledger. Injectable ``sender`` keeps this unit-testable with no live Resend."""
    if today is None:
        from app.services.earnings_calendar_service import today_eastern
        today = today_eastern()  # event_date is an ET calendar day; don't use the server's UTC date
    if sender is None:
        from app.services.email_service import send_earnings_day_alert
        sender = send_earnings_day_alert

    # Users with an enabled alert on a company reporting today. Exclude users with no usable email —
    # otherwise they'd hit a guaranteed send failure that then permanently dedups as handled.
    rows = (
        db.query(User, Company.ticker, EarningsEvent)
        .join(Watchlist, Watchlist.user_id == User.id)
        .join(Company, Watchlist.company_id == Company.id)
        .join(EarningsEvent, func.upper(Company.ticker) == EarningsEvent.ticker)
        .filter(
            Watchlist.earnings_alert.is_(True),
            EarningsEvent.event_date == today,
            User.is_active.is_(True),
            User.email.isnot(None),
            func.trim(User.email) != "",
        )
        .all()
    )

    per_user: dict[int, dict] = {}
    for user, ticker, ev in rows:
        bucket = per_user.setdefault(user.id, {"user": user, "events": {}})
        bucket["events"][ev.id] = (ticker, ev)

    emails = 0
    events_sent = 0
    for user_id, bucket in per_user.items():
        user = bucket["user"]
        # Claim each (user, event, today) send before sending, using the unique constraint as the
        # lock: a freshly-inserted 'pending' row that raises IntegrityError means a concurrent run
        # already owns this send, so we skip it (no double-send). An EXISTING non-'sent' row is a
        # prior run's failed/pending attempt — we take it over and retry (a transient failure must
        # not silently lose a time-sensitive alert). Only a 'sent' row is terminal.
        claimed: list = []  # (ticker, ev, log_row)
        for ticker, ev in bucket["events"].values():
            existing = (
                db.query(EarningsAlertLog)
                .filter(
                    EarningsAlertLog.user_id == user_id,
                    EarningsAlertLog.earnings_event_id == ev.id,
                    EarningsAlertLog.event_date == today,
                    EarningsAlertLog.channel == CHANNEL_EMAIL,
                )
                .first()
            )
            if existing is not None:
                # Take over ONLY committed 'failed' rows, and claim atomically: the UPDATE's WHERE
                # re-evaluates under the row lock, so of two concurrent runs exactly one gets
                # rowcount=1 and sends; the other sees 0 and skips. ('pending' rows are never
                # committed — the claim transaction commits only after the send resolves — so a
                # visible 'pending' is unreachable today and deliberately NOT retried.)
                if existing.status == "failed":
                    took_over = (
                        db.query(EarningsAlertLog)
                        .filter(EarningsAlertLog.id == existing.id, EarningsAlertLog.status == "failed")
                        .update({"status": "pending"}, synchronize_session=False)
                    )
                    if took_over:
                        claimed.append((ticker, ev, existing))
                continue
            log = EarningsAlertLog(
                user_id=user_id, earnings_event_id=ev.id, event_date=today,
                channel=CHANNEL_EMAIL, status="pending",
            )
            try:
                with db.begin_nested():  # SAVEPOINT: an IntegrityError rolls back only this insert
                    db.add(log)
                    db.flush()
                claimed.append((ticker, ev, log))
            except IntegrityError:
                # A concurrent run just claimed this exact send — let it own it; we skip.
                continue

        if not claimed:
            continue

        items = [
            {"ticker": t, "company_name": ev.company_name or t, "time": ev.event_time, "status": ev.status}
            for t, ev, _ in sorted(claimed, key=lambda c: -float(c[1].anticipation_score or 0))
        ]
        try:
            await sender(to_email=user.email, name=getattr(user, "full_name", None), items=items)
            status = "sent"
            emails += 1
            events_sent += len(claimed)
        except Exception:
            logger.exception("Earnings-day alert send failed for user %s", user_id)
            status = "failed"  # ledger keeps the claim as non-terminal → retried next run

        for _t, _ev, log in claimed:
            log.status = status
        db.commit()

    return {"users": len(per_user), "emails": emails, "events": events_sent}
