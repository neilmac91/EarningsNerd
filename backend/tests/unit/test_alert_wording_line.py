"""The "wording changes in Item 1A" field of the filing alerts (tasks/todo.md E27, PR B).

Pins: the line's three states and its absence (no comparison, or the filing's own section only
points at the annual report); the renderers carry it in HTML and text; the scan and the digest
add it for a Pro recipient while the feature is on and never for a Free one or with the flag off;
a batch the delivery drain rebuilds (the recipient's address changed after selection) carries
it too, rendered from ``_item_dicts`` with the recipient. DB-backed on SQLite with the EDGAR
fetch and the sender injected; the comparison summary is written straight onto the
``filing_section_text`` rows, as the extraction batch leaves it.
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.models.filing_section_text import FilingSectionText
from app.services.email_service import build_daily_digest, render_daily_digest, render_new_filing_alert, wording_changes_line
from app.services.filing_scan_service import alert_wording_changes, run_daily_digest, run_filing_scan

NOW = datetime(2026, 6, 17, tzinfo=timezone.utc)
WATCH_SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
SUMMARY = {"items_total": 7, "has_changes": True, "reference_only": False, "prior_reference_only": False}


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


# --- the line and the renderers ----------------------------------------------------------------

def test_wording_line_states():
    assert wording_changes_line(None, "10-K") is None
    assert wording_changes_line({**SUMMARY, "reference_only": True}, "10-Q") is None
    assert wording_changes_line(SUMMARY, "10-K") == "Risk factor wording: 7 paragraphs changed since the prior 10-K."
    assert wording_changes_line({**SUMMARY, "items_total": 1}, "10-Q") == "Risk factor wording: 1 paragraph changed since the prior 10-Q."
    assert wording_changes_line({**SUMMARY, "items_total": 0, "has_changes": False}, "10-K") == "Risk factor wording: no changes since the prior 10-K."
    # No count on a restatement: the items also count the pointer paragraph(s) the prior lost.
    assert wording_changes_line({**SUMMARY, "items_total": 12, "prior_reference_only": True}, "10-Q") == "Risk factors restated in full since the prior 10-Q."


def test_alert_and_digest_carry_the_line_in_html_and_text_only_when_given():
    html, text = render_new_filing_alert(name="Jane", company_name="Acme Corp", ticker="ACME", filing_type="10-K",
                                         filing_date="2026-06-16", filing_id=42, wording_changes=SUMMARY)
    assert "Risk factor wording: 7 paragraphs changed since the prior 10-K." in html
    assert "/filing/42#what-changed" in html and "Review the changes" in html
    assert "Risk factor wording: 7 paragraphs changed since the prior 10-K. Review the changes: " in text
    plain_html, plain_text = render_new_filing_alert(name="Jane", company_name="Acme Corp", ticker="ACME",
                                                     filing_type="10-K", filing_date="2026-06-16", filing_id=42)
    assert "Risk factor" not in plain_html and "Risk factor" not in plain_text

    items = [
        {"company_name": "Acme Corp", "ticker": "ACME", "filing_type": "10-Q", "filing_date": "2026-06-16",
         "filing_id": 1, "wording_changes": {**SUMMARY, "items_total": 3}},
        {"company_name": "Globex", "ticker": "GBX", "filing_type": "8-K", "filing_date": "2026-06-15", "filing_id": 2},
    ]
    html, text = render_daily_digest(name="Jane", items=items)
    assert html.count("Risk factor wording") == 1 and "3 paragraphs changed since the prior 10-Q" in html
    assert "(2026-06-16): Risk factor wording: 3 paragraphs changed since the prior 10-Q. " in text
    subject, _html = build_daily_digest(name="Jane", items=items)
    assert subject == "2 new filings from your watchlist"


def test_the_line_is_escaped_like_the_other_filing_fields():
    html, _text = render_new_filing_alert(name="Jane", company_name="Acme", ticker="ACME", filing_type="<b>10-K</b>",
                                          filing_date="2026-06-16", filing_id=42, wording_changes=SUMMARY)
    assert "<b>10-K</b>" not in html and "&lt;b&gt;10-K&lt;/b&gt;" in html


# --- selection: the scan and the digest --------------------------------------------------------

@contextmanager
def _scenario(*, is_pro, realtime):
    """One watcher of one company that already has a prior 10-K and a new 10-K with a cached
    comparison summary (as the extraction batch leaves it). Yields (company, new filing, user id)."""
    from app.database import SessionLocal
    from app.models import Company, Filing, NotificationLog, NotificationPreferences, User, Watchlist

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=f"cik{suffix}", ticker=f"W{suffix[:4].upper()}", name=f"Co {suffix}")
    db.add(company)
    db.commit()
    db.refresh(company)
    prior = Filing(company_id=company.id, accession_number=f"wording-prior-{suffix}", filing_type="10-K",
                   filing_date=datetime(2025, 6, 10, tzinfo=timezone.utc), period_end_date=datetime(2025, 3, 31, tzinfo=timezone.utc),
                   document_url=f"https://sec.example/{suffix}/prior.htm", sec_url=f"https://sec.example/{suffix}/prior/")
    later = Filing(company_id=company.id, accession_number=f"wording-later-{suffix}", filing_type="10-K",
                   filing_date=datetime(2026, 6, 16, tzinfo=timezone.utc), period_end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
                   document_url=f"https://sec.example/{suffix}/later.htm", sec_url=f"https://sec.example/{suffix}/later/")
    db.add_all([prior, later])
    db.commit()
    db.refresh(prior)
    db.refresh(later)
    stamp = datetime(2026, 6, 16, 12, tzinfo=timezone.utc)
    db.add_all([
        FilingSectionText(filing_id=prior.id, section="item_1a", extractor_version=1, status="ok", text="prior",
                          char_count=5, paragraph_count=1, sha256="a" * 64, extracted_at=stamp, attempted_at=stamp),
        FilingSectionText(filing_id=later.id, section="item_1a", extractor_version=1, status="ok", text="later",
                          char_count=5, paragraph_count=1, sha256="b" * 64, extracted_at=stamp, attempted_at=stamp,
                          diff_prior_filing_id=prior.id, diff_engine_version=1, diff_computed_at=stamp,
                          diff_summary={"counts": {}, "words": {}, "paragraphs": {}, **SUMMARY}),
    ])
    user = User(email=f"wording-{suffix}@example.com", hashed_password="x", email_verified=True, is_active=True, is_pro=is_pro)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Watchlist(user_id=user.id, company_id=company.id, created_at=WATCH_SINCE))
    db.add(NotificationPreferences(user_id=user.id, realtime=realtime))
    db.commit()
    ids = (company.id, later.id, user.id, later.accession_number, later.sec_url, later.document_url)
    section_filing_ids = [prior.id, later.id]
    db.close()
    try:
        yield ids
    finally:
        db = SessionLocal()
        db.query(NotificationLog).filter(NotificationLog.user_id == ids[2]).delete(synchronize_session=False)
        db.query(Watchlist).filter(Watchlist.user_id == ids[2]).delete(synchronize_session=False)
        db.query(NotificationPreferences).filter(NotificationPreferences.user_id == ids[2]).delete(synchronize_session=False)
        db.query(FilingSectionText).filter(FilingSectionText.filing_id.in_(section_filing_ids)).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.company_id == ids[0]).delete(synchronize_session=False)
        db.query(Company).filter(Company.id == ids[0]).delete(synchronize_session=False)
        db.query(User).filter(User.id == ids[2]).delete(synchronize_session=False)
        db.commit()
        db.close()


def _fetch_returning(accession, sec_url, document_url):
    async def _fetch(cik, filing_types=None, limit=None):
        return [{"accession_number": accession, "filing_type": "10-K", "filing_date": "2026-06-16", "report_date": "2026-03-31",
                 "document_url": document_url, "sec_url": sec_url, "cik": "x"}]

    return _fetch


def _batch_html(user_id):
    from app.database import SessionLocal
    from app.models.notification_delivery import DeliveryBatch

    db = SessionLocal()
    try:
        return [b.body_html for b in db.query(DeliveryBatch).filter(DeliveryBatch.user_id == user_id).all()]
    finally:
        db.close()


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_pro_realtime_alert_carries_the_line_while_the_feature_is_on(monkeypatch):
    from app.database import SessionLocal

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    with _scenario(is_pro=True, realtime=True) as (_cid, _fid, uid, accession, sec_url, document_url):
        send = AsyncMock()
        db = SessionLocal()
        stats = await run_filing_scan(db, fetch_filings=_fetch_returning(accession, sec_url, document_url),
                                      send_alert=send, now=NOW, cadence_minutes=0)
        db.close()
        assert stats["alerts_sent"] == 1
        assert send.await_args.kwargs["wording_changes"] == SUMMARY
        [html] = _batch_html(uid)
        assert "Risk factor wording: 7 paragraphs changed since the prior 10-K." in html


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_the_line_is_withheld_with_the_flag_off(monkeypatch):
    from app.database import SessionLocal

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
    with _scenario(is_pro=True, realtime=True) as (_cid, _fid, uid, accession, sec_url, document_url):
        send = AsyncMock()
        db = SessionLocal()
        await run_filing_scan(db, fetch_filings=_fetch_returning(accession, sec_url, document_url),
                              send_alert=send, now=NOW, cadence_minutes=0)
        db.close()
        assert send.await_args.kwargs["wording_changes"] is None
        [html] = _batch_html(uid)
        assert "Risk factor wording" not in html


@pytest.mark.asyncio
@pytest.mark.requires_db
@pytest.mark.parametrize("is_pro", [True, False])
async def test_the_digest_carries_the_line_for_pro_only(monkeypatch, is_pro):
    from app.database import SessionLocal

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
    with _scenario(is_pro=is_pro, realtime=False) as (_cid, _fid, uid, _acc, _sec, _doc):
        send = AsyncMock()
        db = SessionLocal()
        stats = await run_daily_digest(db, send_digest=send, now=NOW)
        db.close()
        assert stats["digests_sent"] >= 1
        [item] = [i for i in send.await_args.kwargs["items"] if i["company_name"].startswith("Co ")] if is_pro else [
            i for i in send.await_args.kwargs["items"]]
        [html] = _batch_html(uid)
        if is_pro:
            assert item["wording_changes"] == SUMMARY
            assert "Risk factor wording: 7 paragraphs changed since the prior 10-K." in html
        else:
            assert item["wording_changes"] is None
            assert "Risk factor wording" not in html


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_a_batch_rebuilt_by_the_drain_carries_the_line(monkeypatch):
    """Selection ran with the feature off (so the frozen alert has no line); the recipient's address
    changed before the retry, so the drain releases the envelope and rebuilds the alert from the
    items with the recipient, where the line is read again: the rebuilt alert carries it."""
    from app.database import SessionLocal
    from app.models import User
    from app.models.notification_delivery import KIND_FILING_REALTIME
    from app.services import notification_delivery_service as delivery
    from app.services import resend_service

    monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
    with _scenario(is_pro=True, realtime=True) as (_cid, _fid, uid, accession, sec_url, document_url):
        async def refused(**_kwargs):
            raise resend_service.ResendRetryableError("429")

        sent = []

        async def record(prepared):
            sent.append(prepared)
            return "email_rebuilt"

        db = SessionLocal()
        try:
            stats = await run_filing_scan(db, fetch_filings=_fetch_returning(accession, sec_url, document_url),
                                          send_alert=refused, now=NOW, cadence_minutes=0)
            assert stats["alerts_sent"] == 0 and stats["alerts_failed"] == 1
            [frozen] = _batch_html(uid)
            assert "Risk factor wording" not in frozen
            db.query(User).filter(User.id == uid).update({"email": f"moved-{uid}@example.com"})
            db.commit()
            monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
            result = await delivery.drain(db, kind=KIND_FILING_REALTIME, send=record, now=NOW + timedelta(minutes=20))
        finally:
            db.close()
        assert (result.suppressed, result.rebuilt, result.accepted) == (1, 1, 1)
        [rebuilt] = sent
        assert rebuilt.to_email == f"moved-{uid}@example.com"
        assert "Risk factor wording: 7 paragraphs changed since the prior 10-K." in rebuilt.html
        assert rebuilt.items[0]["wording_changes"] == SUMMARY


def test_a_row_without_a_comparison_yet_is_not_a_zero_comparison():
    """An ok row whose prior is not extracted has its comparison fields written as None (a JSON
    null in the column, which ``IS NOT NULL`` admits): no summary, so no "no changes" line."""
    from app.database import SessionLocal
    from app.models import Company, Filing
    from app.services.entitlements import _PRO
    from app.services.filing_section_service import wording_change_summaries

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(cik=f"cik{suffix}", ticker=f"N{suffix[:4].upper()}", name=f"Co {suffix}")
    db.add(company)
    db.commit()
    filing = Filing(company_id=company.id, accession_number=f"wording-alone-{suffix}", filing_type="10-K",
                    filing_date=datetime(2026, 6, 16, tzinfo=timezone.utc), period_end_date=datetime(2026, 3, 31, tzinfo=timezone.utc),
                    document_url=f"https://sec.example/{suffix}/alone.htm", sec_url=f"https://sec.example/{suffix}/alone/")
    db.add(filing)
    db.commit()
    stamp = datetime(2026, 6, 16, 12, tzinfo=timezone.utc)
    db.add(FilingSectionText(filing_id=filing.id, section="item_1a", extractor_version=1, status="ok", text="alone",
                             char_count=5, paragraph_count=1, sha256="c" * 64, extracted_at=stamp, attempted_at=stamp,
                             diff_prior_filing_id=None, diff_engine_version=1, diff_computed_at=stamp, diff_summary=None))
    db.commit()
    try:
        assert wording_change_summaries(db, [filing.id]) == {}
        assert alert_wording_changes(db, _PRO, [filing.id]) == {}
        assert wording_changes_line(alert_wording_changes(db, _PRO, [filing.id]).get(filing.id), "10-K") is None
    finally:
        db.query(FilingSectionText).filter(FilingSectionText.filing_id == filing.id).delete(synchronize_session=False)
        db.query(Filing).filter(Filing.id == filing.id).delete(synchronize_session=False)
        db.query(Company).filter(Company.id == company.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_alert_wording_changes_needs_the_flag_the_plan_and_a_cached_comparison(monkeypatch):
    from app.database import SessionLocal
    from app.services.entitlements import _FREE, _PRO

    with _scenario(is_pro=True, realtime=True) as (_cid, fid, _uid, _acc, _sec, _doc):
        db = SessionLocal()
        try:
            monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", False)
            assert alert_wording_changes(db, _PRO, [fid]) == {}
            monkeypatch.setattr(settings, "ENABLE_SECTION_CHANGES", True)
            assert alert_wording_changes(db, _FREE, [fid]) == {}
            assert alert_wording_changes(db, _PRO, []) == {}
            assert alert_wording_changes(db, _PRO, [fid]) == {fid: SUMMARY}
            assert alert_wording_changes(db, _PRO, [0]) == {}
        finally:
            db.close()
