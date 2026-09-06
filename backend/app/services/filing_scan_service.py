"""New-filing detection + alert delivery — the Phase 2 retention engine.

`run_filing_scan` walks the distinct set of watched companies, fetches their latest filings via the
existing EDGAR client (SEC rate limiter + circuit breaker), upserts `Filing` rows, and fans out
**real-time** alerts to eligible Pro watchers. `run_daily_digest` batches everything else (Free, or
Pro with real-time off) into one email per user.

Eligibility and delivery limits:
- **No historical spam:** a watcher is only alerted about filings dated after they started watching
  (``Watchlist.created_at``) or after the last alert (``last_alerted_at``) — the baseline.
- **Durable delivery (E11b-1):** selection persists a delivery batch (frozen email, provider
  idempotency key, owned filings) before any send; ``notification_delivery_service.drain`` then
  dispatches through fenced claims, so concurrent runs cannot both send one batch and a failed
  attempt is retried from the durable record. ``NotificationLog`` rows (historical rows still
  suppress re-selection) and watchlist watermarks are written only on provider acceptance.

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
from app.models.notification_delivery import KIND_FILING_DIGEST, KIND_FILING_REALTIME
from app.models.notifications import CHANNEL_EMAIL
from app.services import email_service
from app.services import notification_delivery_service as delivery
from app.services.entitlements import get_entitlements
from app.services.notification_service import evaluate_delivery, get_or_create_preferences

logger = logging.getLogger(__name__)

SCAN_FORM_TYPES = ["10-K", "10-K/A", "10-Q", "10-Q/A", "8-K"]
# FPI forms added to the scan only behind ENABLE_FPI_FILINGS — the roadmap warns against a blanket
# global default (each extra form is one more SEC get_filings call per watched company per tick, and
# the watched universe is overwhelmingly domestic). Per-form alert eligibility is still gated by the
# user's notify_20f / notify_6k prefs in evaluate_delivery, and 6-K is forced digest-only.
SCAN_FPI_FORM_TYPES = ["20-F", "6-K", "40-F"]
DEFAULT_PER_COMPANY_LIMIT = 10
DEFAULT_CADENCE_MINUTES = 60
DEFAULT_DIGEST_WINDOW_HOURS = 24


def _scan_form_types() -> list[str]:
    """Forms fetched per watched company — FPI forms appended only behind ENABLE_FPI_FILINGS."""
    from app.config import settings

    if settings.ENABLE_FPI_FILINGS:
        return SCAN_FORM_TYPES + SCAN_FPI_FORM_TYPES
    return SCAN_FORM_TYPES


# Type aliases for the injectable collaborators.
FetchFilings = Callable[..., Awaitable[list[dict]]]
SendAlert = Callable[..., Awaitable[None]]
SendDigest = Callable[..., Awaitable[None]]


def _alert_transport(send_alert: Optional[SendAlert]) -> Optional[delivery.Send]:
    """An injected legacy alert sender keeps its keyword shape; None means the frozen payload
    goes to Resend under the batch's idempotency key."""
    if send_alert is None:
        return None

    async def send(prepared: delivery.PreparedSend) -> Optional[str]:
        item = prepared.items[0]
        await send_alert(to_email=prepared.to_email, name=prepared.name, **item)
        return None

    return send


def _digest_transport(send_digest: Optional[SendDigest]) -> Optional[delivery.Send]:
    if send_digest is None:
        return None

    async def send(prepared: delivery.PreparedSend) -> Optional[str]:
        await send_digest(to_email=prepared.to_email, name=prepared.name, items=prepared.items)
        return None

    return send


def _merge_drain(stats: dict, drained: delivery.DrainStats, *, sent_key: str, failed_key: str) -> None:
    stats[sent_key] += drained.accepted
    stats[failed_key] += drained.retryable + drained.ambiguous + drained.rejected
    stats.update(drained.as_dict())


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

    from app.services.filing_amendment_service import mark_superseded_filings
    changed_links = mark_superseded_filings(db, company.id)
    if new_filings or changed_links:
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
    delivery_now = now  # Explicit test clock only; production delivery uses its own live clock.
    now = _as_utc(now or datetime.now(timezone.utc))  # tolerate a naive `now` from callers/tests
    if fetch_filings is None:
        from app.services.edgar.compat import sec_edgar_service
        fetch_filings = sec_edgar_service.get_filings

    stats = {"companies_scanned": 0, "filings_upserted": 0, "alerts_sent": 0, "alerts_failed": 0, "source_errors": 0}

    company_ids = [row[0] for row in db.query(Watchlist.company_id).distinct().all()]
    form_types = _scan_form_types()  # resolve once (flag read + concat) — not per company
    for cid in company_ids:
        company = db.get(Company, cid)
        if company is None:
            continue
        last_check = _as_utc(company.last_filings_check_at)
        if last_check is not None and last_check > now - timedelta(minutes=cadence_minutes):
            continue  # checked recently — honour the scan cadence

        try:
            sec_filings = await fetch_filings(company.cik, filing_types=form_types, limit=per_company_limit)
        except Exception as e:  # EdgarError / CircuitOpenError — skip this company, keep scanning
            stats["source_errors"] += 1
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
                    continue  # historical rows are never replayed
                if delivery.already_owned(db, user.id, filing.id, CHANNEL_EMAIL):
                    continue  # owned by a durable batch (any state)
                subject, html = email_service.build_new_filing_alert(
                    name=user.full_name,
                    company_name=company.name,
                    ticker=company.ticker,
                    filing_type=filing.filing_type,
                    filing_date=_filing_date_str(filing.filing_date),
                    filing_id=filing.id,
                    filing_url=filing.sec_url,
                )
                delivery.create_batch(
                    db, kind=KIND_FILING_REALTIME, user_id=user.id, subject=subject, html=html,
                    filing_ids=[filing.id], now=now,
                )
            db.commit()

    drained = await delivery.drain(db, kind=KIND_FILING_REALTIME, send=_alert_transport(send_alert), now=delivery_now)
    _merge_drain(stats, drained, sent_key="alerts_sent", failed_key="alerts_failed")
    return stats


async def run_daily_digest(
    db: Session,
    *,
    send_digest: Optional[SendDigest] = None,
    now: Optional[datetime] = None,
    window_hours: int = DEFAULT_DIGEST_WINDOW_HOURS,
) -> dict:
    """Send one batched email per user for eligible, not-yet-alerted filings in the window.

    Historical NotificationLog rows and filings already owned by a delivery batch are excluded;
    the digest's membership and payload are frozen on its batch before dispatch.
    """
    delivery_now = now  # Explicit test clock only; production delivery uses its own live clock.
    now = _as_utc(now or datetime.now(timezone.utc))  # tolerate a naive `now` from callers/tests
    window_start = now - timedelta(hours=window_hours)

    stats = {"digests_sent": 0, "digests_failed": 0, "filings_included": 0}

    # Pre-fetch filings for all watched companies in ONE query and group in memory, so the
    # per-user/per-watch loop below issues no further filing queries (avoids the N+1). Apply the
    # UTC-normalized lower bound in SQL so historical rows are not materialized.
    watched_company_ids = [row[0] for row in db.query(Watchlist.company_id).distinct().all()]
    filings_by_company: dict[int, list[Filing]] = {}
    if watched_company_ids:
        for f in db.query(Filing).filter(
            Filing.company_id.in_(watched_company_ids),
            Filing.filing_date >= window_start,
        ).all():
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
                    continue  # historical rows are never replayed
                if delivery.already_owned(db, uid, filing.id, CHANNEL_EMAIL):
                    continue  # owned by a durable batch (any state)
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

        subject, html = email_service.build_daily_digest(name=user.full_name, items=items)
        delivery.create_batch(
            db, kind=KIND_FILING_DIGEST, user_id=uid, subject=subject, html=html,
            filing_ids=[filing.id for _watch, filing in to_log], now=now,
        )

    drained = await delivery.drain(db, kind=KIND_FILING_DIGEST, send=_digest_transport(send_digest), now=delivery_now)
    _merge_drain(stats, drained, sent_key="digests_sent", failed_key="digests_failed")
    stats["filings_included"] += drained.accepted_items
    return stats
