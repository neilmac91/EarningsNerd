"""Filing alerts treat ``Filing.filing_date`` as a calendar date, never an instant.

EDGAR gives a filing a date with no time of day; ``upsert_filings`` stores it as UTC midnight. These
tests drive the hourly scan and the daily digest over several days on a disposable SQLite database,
with filings in the exact shape the EDGAR layer returns (``EdgarFiling.to_dict()``) stored through
the real ``upsert_filings``. Only the SEC fetch and the email send are injected; no network.
"""
from datetime import date, datetime, time, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Company, Filing, NotificationLog, NotificationPreferences, User, Watchlist
from app.services.edgar.models import Filing as EdgarFiling
from app.services.edgar.models import FilingType
from app.services.filing_scan_service import run_daily_digest, run_filing_scan, upsert_filings
from app.utils.sec_urls import build_sec_archive_url

CIK = "320193"
WATCH_SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=timezone.utc)


def _edgar_row(accession: str, form: str, filed: date) -> dict:
    sec_url = build_sec_archive_url(CIK, accession)
    return EdgarFiling(
        accession_number=accession, filing_type=FilingType.from_string(form), filing_date=filed,
        ticker="AAPL", cik=CIK, document_url=sec_url + "doc.htm", sec_url=sec_url,
    ).to_dict()


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _seed(engine, *, is_pro: bool, **prefs) -> None:
    with Session(engine) as db:
        db.add_all([
            Company(id=1, cik=CIK, ticker="AAPL", name="Apple Inc."),
            User(id=1, email="calendar-dates@example.com", hashed_password="x", is_active=True, is_pro=is_pro),
        ])
        db.flush()
        db.add_all([
            Watchlist(user_id=1, company_id=1, created_at=WATCH_SINCE),
            NotificationPreferences(user_id=1, notify_10q=True, notify_10k=True, **prefs),
        ])
        db.commit()


def _accessions(engine, filing_ids: list[int]) -> list[str]:
    with Session(engine) as db:
        return [db.get(Filing, fid).accession_number for fid in filing_ids]


def _log_rows(engine) -> int:
    with Session(engine) as db:
        return db.query(NotificationLog).count()


# Each filing: (accession, form, EDGAR filing date, when the hourly scan first lists it).
FILINGS = [
    # Accepted during the business day of June 16: dated that day, scanned that afternoon.
    ("0000320193-26-000101", "10-Q", date(2026, 6, 16), _utc(16, 15)),
    # Accepted after 17:30 ET on June 16: EDGAR dates it the next business day.
    ("0000320193-26-000102", "10-K", date(2026, 6, 17), _utc(16, 22)),
    # Accepted during the business day of June 17: the same date as the after-hours 10-K above,
    # which the digest may already have sent (the watermark then sits on June 17).
    ("0000320193-26-000103", "10-Q", date(2026, 6, 17), _utc(17, 20)),
    # Accepted late on June 18 and scanned just before midnight UTC.
    ("0000320193-26-000104", "10-Q", date(2026, 6, 18), _utc(18, 23)),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("digest_at", [time(8, 0), time(0, 0), time(13, 0), time(23, 59)],
                         ids=["08:00Z-production", "00:00Z", "13:00Z", "23:59Z"])
async def test_daily_digest_sends_each_date_only_filing_exactly_once(engine, digest_at):
    """Gate for "filing_date is a calendar date": the digest runs daily at ``digest_at`` (production:
    ``0 8 * * *`` UTC) between hourly scans, and every filing dated D reaches exactly one digest.

    The window opens at the start of a UTC day, so a filing dated the day before the run is in it,
    and a filing dated the same day as an already-digested one is still new to the watcher. A
    filing seen by two consecutive windows is sent once (``NotificationLog`` / delivery ownership)."""
    _seed(engine, is_pro=False)
    events = [(scanned, "scan") for *_rest, scanned in FILINGS]
    events += [(datetime.combine(date(2026, 6, day), digest_at, tzinfo=timezone.utc), "digest")
               for day in range(15, 21)]
    realtime, digested = AsyncMock(), []
    for when, kind in sorted(events):
        with Session(engine) as db:
            if kind == "scan":
                listed = [_edgar_row(acc, form, filed) for acc, form, filed, scanned in FILINGS if scanned <= when]
                await run_filing_scan(db, fetch_filings=AsyncMock(return_value=listed), send_alert=realtime,
                                      now=when, cadence_minutes=0)
            else:
                send = AsyncMock()
                await run_daily_digest(db, send_digest=send, now=when)
                for call in send.await_args_list:
                    digested += [item["filing_id"] for item in call.kwargs["items"]]

    realtime.assert_not_awaited()  # Free: the digest is the only channel
    assert sorted(_accessions(engine, digested)) == [acc for acc, *_rest in FILINGS]  # each exactly once
    assert _log_rows(engine) == len(FILINGS)


@pytest.mark.asyncio
async def test_realtime_8k_then_same_date_10q_in_a_later_tick_are_each_alerted_once(engine):
    """An earnings 8-K and the 10-Q often share a filing date but land in different hourly ticks.
    The 8-K's alert moves the watermark to that date; the 10-Q dated the same day is still new.
    Neither is sent again by the next digest or a later tick."""
    _seed(engine, is_pro=True, realtime=True, notify_8k=True)
    eight_k = _edgar_row("0000320193-26-000201", "8-K", date(2026, 6, 16))
    ten_q = _edgar_row("0000320193-26-000202", "10-Q", date(2026, 6, 16))
    timeline = [
        (_utc(16, 13), [eight_k]),
        (_utc(16, 21), [ten_q, eight_k]),
        (_utc(17, 8), None),  # the daily digest
        (_utc(17, 13), [ten_q, eight_k]),
    ]
    sent = []
    for when, listed in timeline:
        send = AsyncMock()
        with Session(engine) as db:
            if listed is None:
                await run_daily_digest(db, send_digest=send, now=when)
                ids = [item["filing_id"] for call in send.await_args_list for item in call.kwargs["items"]]
            else:
                await run_filing_scan(db, fetch_filings=AsyncMock(return_value=listed), send_alert=send,
                                      now=when, cadence_minutes=0)
                ids = [call.kwargs["filing_id"] for call in send.await_args_list]
        sent += [(when, accession) for accession in _accessions(engine, ids)]

    assert sent == [(_utc(16, 13), eight_k["accession_number"]), (_utc(16, 21), ten_q["accession_number"])]
    assert _log_rows(engine) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("scan_at, alerted", [
    (_utc(17, 23, 59), True),
    (_utc(18, 0), False),
    (datetime(2026, 9, 1, 14, tzinfo=timezone.utc), False),
], ids=["next-day", "two-days-later", "weeks-later"])
async def test_realtime_admits_the_watermark_day_only_while_it_is_recent(engine, scan_at, alerted):
    """A 10-Q dated the watermark's own day that was stored but never alerted (what the strict
    pre-fix watermark left behind) is new through the end of the next UTC day, the span the digest
    window covers. Weeks later it is back-catalogue: the first real-time scan after the fix must not
    mail a months-old filing."""
    _seed(engine, is_pro=True, realtime=True, notify_8k=True)
    eight_k = _edgar_row("0000320193-26-000301", "8-K", date(2026, 6, 16))
    ten_q = _edgar_row("0000320193-26-000302", "10-Q", date(2026, 6, 16))
    with Session(engine) as db:
        await run_filing_scan(db, fetch_filings=AsyncMock(return_value=[eight_k]), send_alert=AsyncMock(),
                              now=_utc(16, 13), cadence_minutes=0)
        upsert_filings(db, db.get(Company, 1), [ten_q])
    send = AsyncMock()
    with Session(engine) as db:
        await run_filing_scan(db, fetch_filings=AsyncMock(return_value=[ten_q, eight_k]), send_alert=send,
                              now=scan_at, cadence_minutes=0)

    sent = _accessions(engine, [call.kwargs["filing_id"] for call in send.await_args_list])
    assert sent == ([ten_q["accession_number"]] if alerted else [])
