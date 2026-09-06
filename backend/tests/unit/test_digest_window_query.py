"""Digest window materialization on a disposable SQLite DB; no SEC or email calls."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models import Base, Company, Filing, NotificationPreferences, User, Watchlist
from app.services.filing_scan_service import run_daily_digest


@pytest.mark.asyncio
@pytest.mark.parametrize("now", [
    datetime(2026, 6, 17, tzinfo=timezone.utc),
    datetime(2026, 6, 17, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    datetime(2026, 6, 17),  # Existing callers treat naive now as UTC.
], ids=["utc", "offset", "naive"])
async def test_digest_loads_only_watched_filings_since_normalized_window(now):
    cutoff = datetime(2026, 6, 16, tzinfo=timezone.utc)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            companies = [Company(id=i, cik=str(i), ticker=f"T{i}", name=f"Company {i}")
                         for i in (1, 2, 3)]
            user = User(id=1, email="digest-window@example.com", hashed_password="x",
                        is_active=True, is_pro=False)
            db.add_all([*companies, user])
            db.flush()
            db.add_all([
                Watchlist(user_id=1, company_id=1, created_at=cutoff - timedelta(days=1)),
                Watchlist(user_id=1, company_id=2, created_at=cutoff + timedelta(hours=12)),
                NotificationPreferences(user_id=1, notify_10q=True, notify_10k=False),
            ])
            fixtures = [
                (1, 1, cutoff, "10-Q"),                           # inclusive window boundary
                (2, 1, cutoff + timedelta(hours=1), "10-Q"),      # recent and eligible
                (3, 1, cutoff + timedelta(days=2), "10-Q"),       # preserve future-date behavior
                (4, 1, cutoff - timedelta(microseconds=1), "10-Q"),  # just outside window
                (5, 3, cutoff + timedelta(hours=1), "10-Q"),      # unwatched company
                (6, 2, cutoff + timedelta(hours=12), "10-Q"),     # at watch baseline: excluded
                (7, 1, cutoff + timedelta(hours=2), "10-K"),      # preference: excluded
            ]
            db.add_all([Filing(
                id=fid, company_id=cid, accession_number=f"digest-window-{fid}",
                filing_type=form, filing_date=date,
                sec_url=f"https://sec.example/{fid}/",
                document_url=f"https://sec.example/{fid}/doc.htm",
            ) for fid, cid, date, form in fixtures])
            db.commit()
            # Ensure observations cover DB materialization rather than the seeding identity map.
            db.expunge_all()
            loaded_ids = set()

            def record_loaded_filing(_session, instance):
                if isinstance(instance, Filing):
                    loaded_ids.add(instance.id)

            send = AsyncMock()
            event.listen(db, "loaded_as_persistent", record_loaded_filing)
            try:
                stats = await run_daily_digest(db, now=now, send_digest=send)
            finally:
                event.remove(db, "loaded_as_persistent", record_loaded_filing)

            assert loaded_ids == {1, 2, 3, 6, 7}, (
                "Digest must not materialize out-of-window or unwatched Filing rows"
            )
            send.assert_awaited_once()
            assert [item["filing_id"] for item in send.await_args.kwargs["items"]] == [3, 2, 1]
            assert stats == {"digests_sent": 1, "digests_failed": 0, "filings_included": 3}
    finally:
        engine.dispose()
