"""New-filing detection + alert delivery — the Phase 2 retention engine.

`run_filing_scan` walks the distinct set of watched companies, fetches their latest filings via the
existing EDGAR client (SEC rate limiter + circuit breaker), upserts `Filing` rows, and fans out
**real-time** alerts to eligible Pro watchers. `run_daily_digest` batches everything else (Free, or
Pro with real-time off) into one email per user.

Correctness guarantees:
- **No historical spam:** a watcher is only alerted about filings dated after they started watching
  (``Watchlist.created_at``) or after the last alert (``last_alerted_at``) — the baseline.
- **Never sent twice:** the ``NotificationLog`` unique ``(user_id, filing_id, channel)`` is the hard
  dedup; a pre-check short-circuits the common case and the constraint backstops concurrent runs.

EDGAR fetch and email send are injectable so the whole engine is unit-testable on SQLite with no
live SEC/Resend calls.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, Filing, NotificationLog, User, Watchlist
from app.models.notifications import CHANNEL_EMAIL
from app.services import email_service
from app.services.entitlements import get_entitlements
from app.services.notification_service import evaluate_delivery, get_or_create_preferences

logger = logging.getLogger(__name__)

SCAN_FORM_TYPES = ["10-K", "10-Q", "8-K"]
DEFAULT_PER_COMPANY_LIMIT = 10
DEFAULT_CADENCE_MINUTES = 60
DEFAULT_DIGEST_WINDOW_HOURS = 24

# Type aliases for the injectable collaborators.
FetchFilings = Callable[..., Awaitable[list[dict]]]
SendAlert = Callable[..., Awaitable[None]]
SendDigest = Callable[..., Awaitable[None]]


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise to tz-aware UTC (treat naive — i.e. SQLite — values as UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _filing_date_str(dt: Optional[datetime]) -> str:
    d = _as_utc(dt)
    return d.date().isoformat() if d else ""


# --------------------------------------------------------------------------- filing upsert

def upsert_filings(db: Session, company: Company, sec_filings: list[dict]) -> list[Filing]:
    """Insert any not-yet-seen filings for a company; return the resulting Filing rows.

    Mirrors the production upsert in routers/filings.py: prefetch existing by accession (no N+1),
    skip rows missing the NOT NULL urls, parse ISO dates, batch-commit.
    """
    if not sec_filings:
        return []

    accession_numbers = [f.get("accession_number") for f in sec_filings if f.get("accession_number")]
    existing = {
        f.accession_number: f
        for f in db.query(Filing).filter(Filing.accession_number.in_(accession_numbers)).all()
    } if accession_numbers else {}

    result: list[Filing] = []
    new_filings: list[Filing] = []
    for sf in sec_filings:
        accession = sf.get("accession_number")
        sec_url = sf.get("sec_url")
        document_url = sf.get("document_url")
        if not accession or not sec_url or not document_url:
            logger.warning("Skipping filing with missing accession/url: %s", accession)
            continue

        filing = existing.get(accession)
        if filing is None:
            try:
                filing = Filing(
                    company_id=company.id,
                    accession_number=accession,
                    filing_type=sf["filing_type"],
                    filing_date=datetime.fromisoformat(sf["filing_date"]),
                    period_end_date=datetime.fromisoformat(sf["report_date"]) if sf.get("report_date") else None,
                    document_url=document_url,
                    sec_url=sec_url,
                )
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed filing %s: %s", accession, e)
                continue
            db.add(filing)
            new_filings.append(filing)
        result.append(filing)

    if new_filings:
        db.commit()
        for f in new_filings:
            db.refresh(f)
    return result


# --------------------------------------------------------------------------- dedup helpers

def _already_logged(db: Session, user_id: int, filing_id: int, channel: str) -> bool:
    return (
        db.query(NotificationLog.id)
        .filter(
            NotificationLog.user_id == user_id,
            NotificationLog.filing_id == filing_id,
            NotificationLog.channel == channel,
        )
        .first()
        is not None
    )


def _write_log(db: Session, user_id: int, filing_id: int, channel: str, status: str) -> bool:
    """Insert a log row inside a SAVEPOINT so a duplicate (unique-constraint) hit rolls back only
    this insert — never the surrounding transaction's pending watermark / last-check updates. The
    caller is responsible for the outer commit. Returns whether the row was newly inserted."""
    try:
        with db.begin_nested():
            db.add(NotificationLog(user_id=user_id, filing_id=filing_id, channel=channel, status=status))
        return True
    except IntegrityError:
        return False


def _candidate_filings(filings: list[Filing], baseline: Optional[datetime]) -> list[Filing]:
    """Filings dated strictly after the baseline (what's new since the user started watching),
    newest first. This is what prevents alerting on a company's back-catalogue."""
    out = []
    for f in filings:
        fdate = _as_utc(f.filing_date)
        if fdate is None:
            continue
        if baseline is not None and fdate <= baseline:
            continue
        out.append(f)
    out.sort(key=lambda f: _as_utc(f.filing_date), reverse=True)
    return out


def _baseline_for(watch: Watchlist) -> Optional[datetime]:
    return _as_utc(watch.last_alerted_at) if watch.last_alerted_at else _as_utc(watch.created_at)


def _advance_watermark(watch: Watchlist, filing: Filing) -> None:
    fdate = _as_utc(filing.filing_date)
    current = _as_utc(watch.last_alerted_at)
    if fdate and (current is None or fdate > current):
        watch.last_alerted_at = fdate
        watch.last_alerted_accession = filing.accession_number


# --------------------------------------------------------------------------- scan + digest

async def run_filing_scan(
    db: Session,
    *,
    fetch_filings: Optional[FetchFilings] = None,
    send_alert: Optional[SendAlert] = None,
    now: Optional[datetime] = None,
    cadence_minutes: int = DEFAULT_CADENCE_MINUTES,
    per_company_limit: int = DEFAULT_PER_COMPANY_LIMIT,
) -> dict:
    """Detect new filings for watched companies and send real-time alerts to eligible Pro watchers.

    Non-real-time-eligible filings (Free users, or Pro with real-time off) are left for
    :func:`run_daily_digest`.
    """
    now = _as_utc(now or datetime.now(timezone.utc))  # tolerate a naive `now` from callers/tests
    send_alert = send_alert or email_service.send_new_filing_alert
    if fetch_filings is None:
        from app.services.edgar.compat import sec_edgar_service
        fetch_filings = sec_edgar_service.get_filings

    stats = {"companies_scanned": 0, "filings_upserted": 0, "alerts_sent": 0, "alerts_failed": 0}

    company_ids = [row[0] for row in db.query(Watchlist.company_id).distinct().all()]
    for cid in company_ids:
        company = db.get(Company, cid)
        if company is None:
            continue
        last_check = _as_utc(company.last_filings_check_at)
        if last_check is not None and last_check > now - timedelta(minutes=cadence_minutes):
            continue  # checked recently — honour the scan cadence

        try:
            sec_filings = await fetch_filings(company.cik, filing_types=SCAN_FORM_TYPES, limit=per_company_limit)
        except Exception as e:  # EdgarError / CircuitOpenError — skip this company, keep scanning
            logger.warning("Filing fetch failed for %s (%s): %s", company.ticker, company.cik, e)
            continue

        before = db.query(Filing).filter(Filing.company_id == cid).count()
        filings = upsert_filings(db, company, sec_filings)
        stats["filings_upserted"] += max(0, db.query(Filing).filter(Filing.company_id == cid).count() - before)
        company.last_filings_check_at = now
        db.commit()
        stats["companies_scanned"] += 1

        watchers = db.query(Watchlist).filter(Watchlist.company_id == cid).all()
        for watch in watchers:
            user = db.get(User, watch.user_id)
            if user is None or not user.is_active:
                continue
            prefs = get_or_create_preferences(db, user.id)
            ent = get_entitlements(user)
            for filing in _candidate_filings(filings, _baseline_for(watch)):
                eligible, realtime = evaluate_delivery(prefs, ent, filing.filing_type)
                if not eligible or not realtime:
                    continue  # ineligible, or queued for the digest
                if _already_logged(db, user.id, filing.id, CHANNEL_EMAIL):
                    continue
                status = "sent"
                try:
                    await send_alert(
                        to_email=user.email,
                        name=user.full_name,
                        company_name=company.name,
                        ticker=company.ticker,
                        filing_type=filing.filing_type,
                        filing_date=_filing_date_str(filing.filing_date),
                        filing_id=filing.id,
                        filing_url=filing.sec_url,
                    )
                    stats["alerts_sent"] += 1
                except Exception as e:
                    status = "failed"
                    stats["alerts_failed"] += 1
                    logger.warning("Alert send failed (user %s, filing %s): %s", user.id, filing.id, e)
                _write_log(db, user.id, filing.id, CHANNEL_EMAIL, status)
                _advance_watermark(watch, filing)
            db.commit()

    return stats


async def run_daily_digest(
    db: Session,
    *,
    send_digest: Optional[SendDigest] = None,
    now: Optional[datetime] = None,
    window_hours: int = DEFAULT_DIGEST_WINDOW_HOURS,
) -> dict:
    """Send one batched email per user for eligible, not-yet-alerted filings in the window.

    Real-time alerts already sent by :func:`run_filing_scan` carry a NotificationLog row and are
    therefore excluded here — so Free users get the digest and Pro/real-time users don't get dupes.
    """
    now = _as_utc(now or datetime.now(timezone.utc))  # tolerate a naive `now` from callers/tests
    send_digest = send_digest or email_service.send_daily_digest
    window_start = now - timedelta(hours=window_hours)

    stats = {"digests_sent": 0, "digests_failed": 0, "filings_included": 0}

    # Pre-fetch filings for all watched companies in ONE query and group in memory, so the
    # per-user/per-watch loop below issues no further filing queries (avoids the N+1). We filter to
    # the window in Python (via _as_utc) rather than in SQL, to stay tz-safe across Postgres + SQLite.
    watched_company_ids = [row[0] for row in db.query(Watchlist.company_id).distinct().all()]
    filings_by_company: dict[int, list[Filing]] = {}
    if watched_company_ids:
        for f in db.query(Filing).filter(Filing.company_id.in_(watched_company_ids)).all():
            filings_by_company.setdefault(f.company_id, []).append(f)

    user_ids = [row[0] for row in db.query(Watchlist.user_id).distinct().all()]
    for uid in user_ids:
        user = db.get(User, uid)
        if user is None or not user.is_active:
            continue
        prefs = get_or_create_preferences(db, uid)
        ent = get_entitlements(user)

        items: list[dict] = []
        to_log: list[tuple[Watchlist, Filing]] = []
        for watch in db.query(Watchlist).filter(Watchlist.user_id == uid).all():
            company = db.get(Company, watch.company_id)
            if company is None:
                continue
            baseline = _baseline_for(watch)
            recent = filings_by_company.get(watch.company_id, [])
            for filing in _candidate_filings(recent, baseline):
                fdate = _as_utc(filing.filing_date)
                if fdate is None or fdate < window_start:
                    continue
                eligible, _realtime = evaluate_delivery(prefs, ent, filing.filing_type)
                if not eligible:
                    continue
                if _already_logged(db, uid, filing.id, CHANNEL_EMAIL):
                    continue  # already sent (real-time) or already digested
                items.append({
                    "company_name": company.name,
                    "ticker": company.ticker,
                    "filing_type": filing.filing_type,
                    "filing_date": _filing_date_str(filing.filing_date),
                    "filing_id": filing.id,
                    "filing_url": filing.sec_url,
                })
                to_log.append((watch, filing))

        if not items:
            continue

        status = "sent"
        try:
            await send_digest(to_email=user.email, name=user.full_name, items=items)
            stats["digests_sent"] += 1
        except Exception as e:
            status = "failed"
            stats["digests_failed"] += 1
            logger.warning("Digest send failed (user %s): %s", uid, e)

        for watch, filing in to_log:
            if _write_log(db, uid, filing.id, CHANNEL_EMAIL, status):
                stats["filings_included"] += 1
                _advance_watermark(watch, filing)
        db.commit()

    return stats
