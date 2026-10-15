# `filing_date` is a calendar date, never an instant: compare it by whole days

Date: 2026-10-15   Area: sec / notifications

**Context**: EDGAR gives a filing a date with no time of day (`edgar/models.py` `Filing.filing_date: date`,
serialized `YYYY-MM-DD`), and every writer stores `datetime.fromisoformat("YYYY-MM-DD")`, which is
UTC midnight (`filing_scan_service.upsert_filings`, `filing_list_service`, `precompute_service`). The
alert engine compared that midnight with instants. The daily digest's window was `now - 24h`, and the
job runs at 08:00 UTC, so a filing dated D (stored D 00:00) was before the window of the D+1 run and
every later one: only after-hours filings, which EDGAR dates the next day, ever reached a Free user's
digest. The watermark had the same flaw: an alert sets `last_alerted_at` to the filing's midnight
and candidates were `fdate > watermark`, so a 10-Q dated the same day as an 8-K alerted an hour
earlier was dropped on every channel. The tests passed because they ran the digest at exactly
midnight UTC or seeded filing dates with an hour, which production never stores.

**Rule**: Treat `Filing.filing_date` as a day. Open a time window at the start of a UTC day
(`.replace(hour=0, minute=0, second=0, microsecond=0)`), and let a watermark that was copied from a
filing date admit its own date (`fdate < watermark` skips, equality passes). Day granularity selects
some filings twice, so exactness comes from per-(user, filing) dedupe (`NotificationLog`, delivery
ownership), never from a tighter date bound. Where a date cannot be ordered against an instant (a
filing dated the day a watch began may predate it), keep the conservative side and say so. A test of
date logic runs the clock at a non-midnight hour, like the production schedule, and stores dates
through the real writer.

**Evidence**: `backend/app/services/filing_scan_service.py` (`run_daily_digest` window,
`_candidate_filings`); `backend/tests/unit/test_filing_alert_calendar_dates.py` runs the digest at
08:00, 00:00, 13:00 and 23:59 UTC on six consecutive days with filings stored through `upsert_filings` and
asserts each is digested exactly once, plus an 8-K and a same-date 10-Q in two realtime ticks.
`backend/tests/unit/test_digest_window_query.py` fixture 6 keeps the watch-start baseline strict.
Not yet day-granular: `facts/ingest.py` compares `Filing.filing_date > facts_synced_at` in its TTL
short-circuit, so a filing dated the day of a sync waits for the TTL.
