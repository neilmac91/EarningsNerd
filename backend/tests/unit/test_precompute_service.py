"""Precompute service (roadmap A1): idempotent warm-the-cold-path generation + batch cost guard.

DB-backed on SQLite (create_all); SEC fetch and ``generate_summary_background`` are mocked, so no
live SEC/DeepSeek calls. Covers: form validation, idempotent skip (no regeneration when a Summary
exists), dry-run writes/generates nothing, real generation, company-not-found, and the MAX_BATCH
cap + per-item error resilience that bound cost. The forced-precompute cases at the end run the real
orchestrator through the stream harness instead (SEC and the provider faked): ``force`` regenerates
in place under keep-better and reports generated, kept, failed or generation_failed.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services import precompute_service
from app.services.precompute_service import precompute, precompute_one


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _mk_company(ticker: str):
    from app.database import SessionLocal
    from app.models import Company

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        c = Company(cik=f"cik{suffix}", ticker=ticker.upper(), name=f"Co {suffix}")
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id
    finally:
        db.close()


def _mk_filing(company_id: int, accession: str, ftype: str = "10-K", with_summary: bool = False) -> int:
    from app.database import SessionLocal
    from app.models import Filing, Summary

    db = SessionLocal()
    try:
        f = Filing(
            company_id=company_id,
            accession_number=accession,
            filing_type=ftype,
            filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{accession}/d.htm",
            sec_url=f"https://sec.example/{accession}/",
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        fid = f.id
        if with_summary:
            db.add(Summary(filing_id=fid, business_overview="x"))
            db.commit()
        return fid
    finally:
        db.close()


def _sec_filing(accession: str, ftype: str = "10-K") -> dict:
    return {
        "accession_number": accession,
        "filing_type": ftype,
        "filing_date": "2026-01-15",
        "report_date": "2025-12-31",
        "document_url": f"https://sec.example/{accession}/d.htm",
        "sec_url": f"https://sec.example/{accession}/",
        "cik": "x",
    }


def _patch_sec(monkeypatch, *, filings, search_result=None):
    from app.services.edgar.compat import sec_edgar_service

    monkeypatch.setattr(sec_edgar_service, "get_filings", AsyncMock(return_value=filings))
    monkeypatch.setattr(sec_edgar_service, "search_company", AsyncMock(return_value=search_result or []))


@pytest.mark.asyncio
async def test_unsupported_form_short_circuits():
    r = await precompute_one("AAPL", "8-K")
    assert r["status"] == "unsupported_form"


@pytest.mark.asyncio
async def test_20f_unsupported_when_fpi_flag_off(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", False)
    r = await precompute_one("BABA", "20-F")
    assert r["status"] == "unsupported_form"


@pytest.mark.asyncio
async def test_20f_supported_when_fpi_flag_on(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    ticker = f"FPI{uuid.uuid4().hex[:4].upper()}"
    _mk_company(ticker)
    acc = f"acc-{uuid.uuid4().hex[:10]}"
    _patch_sec(monkeypatch, filings=[_sec_filing(acc, "20-F")])

    async def fake_gen(filing_id, user_id=None, *, force_regenerate=False):
        from app.database import SessionLocal
        from app.models import Summary

        db = SessionLocal()
        try:
            db.add(Summary(filing_id=filing_id, business_overview="generated"))
            db.commit()
        finally:
            db.close()

    gen = AsyncMock(side_effect=fake_gen)
    monkeypatch.setattr("app.services.summary_generation_service.generate_summary_background", gen)

    r = await precompute_one(ticker, "20-F")
    assert r["status"] == "generated"
    gen.assert_awaited_once()


@pytest.mark.asyncio
async def test_idempotent_skip_when_summary_exists(monkeypatch):
    ticker = f"IDEM{uuid.uuid4().hex[:4].upper()}"
    cid = _mk_company(ticker)
    acc = f"acc-{uuid.uuid4().hex[:10]}"
    _mk_filing(cid, acc, with_summary=True)
    _patch_sec(monkeypatch, filings=[_sec_filing(acc)])
    gen = AsyncMock()
    monkeypatch.setattr("app.services.summary_generation_service.generate_summary_background", gen)

    r = await precompute_one(ticker, "10-K")

    assert r["status"] == "already_cached"
    gen.assert_not_called()


@pytest.mark.asyncio
async def test_generates_when_missing(monkeypatch):
    ticker = f"GEN{uuid.uuid4().hex[:4].upper()}"
    _mk_company(ticker)
    acc = f"acc-{uuid.uuid4().hex[:10]}"
    _patch_sec(monkeypatch, filings=[_sec_filing(acc)])

    async def fake_gen(filing_id, user_id=None, *, force_regenerate=False):
        from app.database import SessionLocal
        from app.models import Summary

        db = SessionLocal()
        try:
            db.add(Summary(filing_id=filing_id, business_overview="generated"))
            db.commit()
        finally:
            db.close()

    gen = AsyncMock(side_effect=fake_gen)
    monkeypatch.setattr("app.services.summary_generation_service.generate_summary_background", gen)

    r = await precompute_one(ticker, "10-K")

    assert r["status"] == "generated"
    assert r["filing_id"] is not None
    gen.assert_awaited_once()


@pytest.mark.asyncio
async def test_dry_run_writes_and_generates_nothing(monkeypatch):
    ticker = f"DRY{uuid.uuid4().hex[:4].upper()}"
    _mk_company(ticker)
    acc = f"acc-{uuid.uuid4().hex[:10]}"
    _patch_sec(monkeypatch, filings=[_sec_filing(acc)])
    gen = AsyncMock()
    monkeypatch.setattr("app.services.summary_generation_service.generate_summary_background", gen)

    r = await precompute_one(ticker, "10-K", dry_run=True)

    assert r["status"] == "would_generate"
    gen.assert_not_called()
    # A dry run must not create the Filing row.
    from app.database import SessionLocal
    from app.models import Filing

    db = SessionLocal()
    try:
        assert db.query(Filing).filter(Filing.accession_number == acc).first() is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_company_not_found(monkeypatch):
    _patch_sec(monkeypatch, filings=[], search_result=[])
    r = await precompute_one(f"NOPE{uuid.uuid4().hex[:4]}", "10-K")
    assert r["status"] == "company_not_found"


@pytest.mark.asyncio
async def test_precompute_caps_batch(monkeypatch):
    calls: list = []

    async def fake_one(ticker, form, *, force=False, dry_run=False):
        calls.append((ticker, form))
        return {"ticker": ticker, "form": form, "status": "generated", "filing_id": 1, "accession": "a"}

    monkeypatch.setattr(precompute_service, "precompute_one", fake_one)

    out = await precompute([f"T{i}" for i in range(10)], forms=["10-K", "10-Q"], cap=5)

    assert out["stats"]["requested"] == 20
    assert out["stats"]["ran"] == 5
    assert out["stats"]["truncated_at_cap"] == 15
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_precompute_aggregates_and_survives_errors(monkeypatch):
    async def fake_one(ticker, form, *, force=False, dry_run=False):
        if ticker == "BOOM":
            raise RuntimeError("kaboom")
        return {"ticker": ticker, "form": form, "status": "already_cached", "filing_id": 1, "accession": "a"}

    monkeypatch.setattr(precompute_service, "precompute_one", fake_one)

    out = await precompute(["AAA", "BOOM", "CCC"], forms=["10-K"])

    assert out["stats"]["already_cached"] == 2
    assert out["stats"]["error"] == 1
    assert out["stats"]["ran"] == 3


# --- Forced precompute regenerates in place (no DELETE) -------------------------------------------
# precompute_one(force=True) used to DELETE the filing's Summary before generating, outside the
# keep-better gate: a failed run left the filing with no summary, a timeout fallback replaced a full
# summary under a new id, and a bookmarked summary was orphaned (SQLite) or the DELETE broke
# saved_summaries.summary_id's FK (PostgreSQL). It now drives the ONE orchestrator with
# force_regenerate, which updates the row in place under keep-better. These run the real pipeline
# through the stream harness; only SEC and the provider are faked.

STORED_FULL = "# Summary\n\nA full, shown analysis."
STORED_EXCERPT = "Item 7. MD&A excerpt the stored summary was generated from."
FRESH_EXCERPT = "Item 7. MD&A excerpt the current extraction builds."
PROVIDER_ERROR = {"status": "error", "message": "provider down"}


def _seed_forced(*, with_summary: bool = True, updated_at=None, excerpt=STORED_EXCERPT):
    from app.database import SessionLocal
    from app.models import FilingContentCache, SavedSummary, Summary, User

    ticker = f"FRC{uuid.uuid4().hex[:4].upper()}"
    acc = f"acc-{uuid.uuid4().hex[:10]}"
    filing_id = _mk_filing(_mk_company(ticker), acc)
    summary_id = user_id = None
    with SessionLocal() as db:
        db.add(FilingContentCache(filing_id=filing_id, critical_excerpt=excerpt))
        if with_summary:
            summary = Summary(filing_id=filing_id, business_overview=STORED_FULL, updated_at=updated_at,
                              raw_summary={"sections": {}, "quality": {"tier": "full"}})
            user = User(email=f"bm-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x")
            db.add_all([summary, user])
            db.commit()
            db.add(SavedSummary(user_id=user.id, summary_id=summary.id))
            summary_id, user_id = summary.id, user.id
        db.commit()
    return ticker, acc, filing_id, summary_id, user_id


def _stored(filing_id):
    """(summary rows, the row's id, its overview, the filing's cached excerpt)."""
    from app.database import SessionLocal
    from app.models import FilingContentCache, Summary

    with SessionLocal() as db:
        rows = db.query(Summary).filter(Summary.filing_id == filing_id).all()
        cache = db.query(FilingContentCache).filter(FilingContentCache.filing_id == filing_id).one()
        row = rows[0] if rows else None
        return len(rows), row and row.id, row and row.business_overview, cache.critical_excerpt


def _bookmark_target_exists(user_id):
    from app.database import SessionLocal
    from app.models import SavedSummary, Summary

    with SessionLocal() as db:
        bookmark = db.query(SavedSummary).filter(SavedSummary.user_id == user_id).one()
        return db.get(Summary, bookmark.summary_id) is not None


def _writes_a_fresh_excerpt(db, filing, _filing_text, sections=None):
    # As get_or_cache_excerpt does for a cleared excerpt: build one and store it before the run's
    # result is judged, so a kept summary would otherwise be left beside an excerpt it never saw.
    filing.content_cache.critical_excerpt = FRESH_EXCERPT
    db.commit()
    return FRESH_EXCERPT


def _forced_precompute(monkeypatch, ticker, acc, *, payload=None, side_effect=None, document_fails=False):
    from contextlib import nullcontext

    from app.services import summary_pipeline
    from tests.support.summary_stream_harness import reset_inflight, stream_boundaries

    _patch_sec(monkeypatch, filings=[_sec_filing(acc)])
    failing_document = patch.object(summary_pipeline.sec_edgar_service, "get_filing_document",
                                    AsyncMock(side_effect=RuntimeError("SEC 503")))
    reset_inflight()
    try:
        with stream_boundaries(payload=payload) as summarize, \
                patch.object(summary_pipeline, "get_or_cache_excerpt", _writes_a_fresh_excerpt), \
                failing_document if document_fails else nullcontext():
            summarize.side_effect = side_effect
            return asyncio.run(precompute_one(ticker, "10-K", force=True))
    finally:
        reset_inflight()


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        ("replaced", "generated"),        # the fresh full result is written over the stored row
        ("timeout_fallback", "kept"),     # the AI-timeout fallback is partial: keep-better keeps the full
        ("provider_error", "failed"),     # an error payload saves nothing
        ("provider_raises", "failed"),    # an exception becomes a terminal error and saves nothing
        ("document_fails", "failed"),     # an SEC document-fetch failure ends the run before generation
    ],
)
# A summary stored beside no excerpt had its quotes verified against the cached document; a kept one
# must not be left beside the excerpt this run built (Codex 4364816435 on #1545).
@pytest.mark.parametrize("stored_excerpt", [STORED_EXCERPT, None], ids=["excerpt", "no-excerpt"])
def test_forced_precompute_regenerates_in_place_under_keep_better(monkeypatch, outcome, status, stored_excerpt):
    ticker, acc, filing_id, summary_id, user_id = _seed_forced(excerpt=stored_excerpt)
    side_effect = {"timeout_fallback": TimeoutError("budget exhausted"),
                   "provider_raises": RuntimeError("provider down")}.get(outcome)

    result = _forced_precompute(monkeypatch, ticker, acc, side_effect=side_effect,
                                payload=PROVIDER_ERROR if outcome == "provider_error" else None,
                                document_fails=outcome == "document_fails")

    assert result["status"] == status
    count, row_id, overview, excerpt = _stored(filing_id)
    assert (count, row_id) == (1, summary_id)  # one row, the same id: never deleted and re-inserted
    assert _bookmark_target_exists(user_id)
    if outcome == "replaced":
        assert overview != STORED_FULL
        assert excerpt == FRESH_EXCERPT  # the refresh's own excerpt sits with its summary
    else:
        assert overview == STORED_FULL
        assert excerpt == stored_excerpt  # the stored summary keeps the excerpt it was generated from, or none


@pytest.mark.parametrize(("outcome", "status"), [("replaced", "generated"), ("timeout_fallback", "kept")])
def test_forced_precompute_tells_a_replace_from_a_keep_on_a_row_refreshed_before(monkeypatch, outcome, status):
    # A row refreshed in place before carries an updated_at; a rerun of --force over it is the common
    # case, so the replace/keep comparison is pinned from a stamped row too, not only from NULL.
    ticker, acc, filing_id, summary_id, _user_id = _seed_forced(
        updated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    side_effect = TimeoutError("budget exhausted") if outcome == "timeout_fallback" else None

    result = _forced_precompute(monkeypatch, ticker, acc, side_effect=side_effect)

    assert result["status"] == status
    count, row_id, overview, excerpt = _stored(filing_id)
    assert (count, row_id) == (1, summary_id)
    assert (overview == STORED_FULL, excerpt) == (
        (False, FRESH_EXCERPT) if outcome == "replaced" else (True, STORED_EXCERPT))


@pytest.mark.parametrize("stored_excerpt", [STORED_EXCERPT, None], ids=["excerpt", "no-excerpt"])
@pytest.mark.parametrize("error", [RuntimeError("database down"), asyncio.CancelledError()],
                         ids=["raises", "cancelled"])
def test_forced_precompute_puts_the_excerpt_back_when_the_run_raises_or_is_cancelled(monkeypatch, error, stored_excerpt):
    # The excerpt is cleared before the run so that it rebuilds with the current extraction. A run that
    # raises (a database error before the pipeline turns failures into events) or is cancelled (the
    # job or the API server stops) still leaves the kept summary with the excerpt it was built from.
    from app.services import summary_generation_service

    ticker, acc, filing_id, summary_id, user_id = _seed_forced(excerpt=stored_excerpt)
    _patch_sec(monkeypatch, filings=[_sec_filing(acc)])
    mid_run = {}

    async def run_that_ends_abruptly(fid, user_id=None, *, force_regenerate=False):
        from app.database import SessionLocal
        from app.models import FilingContentCache

        mid_run["excerpt"] = _stored(fid)[3]
        with SessionLocal() as db:  # as the run's excerpt build does before it is judged
            db.query(FilingContentCache).filter(FilingContentCache.filing_id == fid).one() \
                .critical_excerpt = FRESH_EXCERPT
            db.commit()
        raise error

    monkeypatch.setattr(summary_generation_service, "generate_summary_background", run_that_ends_abruptly)

    with pytest.raises(type(error)):
        asyncio.run(precompute_one(ticker, "10-K", force=True))

    assert mid_run == {"excerpt": None}  # cleared while the run builds its own
    assert _stored(filing_id) == (1, summary_id, STORED_FULL, stored_excerpt)
    assert _bookmark_target_exists(user_id)


def test_forced_precompute_never_deletes_a_bookmarked_summary_under_enforced_foreign_keys(monkeypatch):
    # PostgreSQL enforces saved_summaries.summary_id -> summaries.id (NO ACTION); emulate it in SQLite.
    from sqlalchemy import event

    from app.database import engine

    ticker, acc, filing_id, summary_id, user_id = _seed_forced()

    def foreign_keys_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    event.listen(engine, "connect", foreign_keys_on)
    engine.dispose()
    try:
        result = _forced_precompute(monkeypatch, ticker, acc)
    finally:
        event.remove(engine, "connect", foreign_keys_on)
        engine.dispose()

    assert result["status"] == "generated"
    assert _stored(filing_id)[:2] == (1, summary_id)
    assert _bookmark_target_exists(user_id)


@pytest.mark.parametrize(("payload", "status"), [(None, "generated"), (PROVIDER_ERROR, "generation_failed")])
def test_forced_precompute_of_a_filing_without_a_summary(monkeypatch, payload, status):
    ticker, acc, filing_id, _summary_id, _user_id = _seed_forced(with_summary=False)

    result = _forced_precompute(monkeypatch, ticker, acc, payload=payload)

    assert result["status"] == status
    assert _stored(filing_id)[0] == (1 if status == "generated" else 0)


@pytest.mark.parametrize(
    ("status", "detail", "job_fails"),
    [("kept", "stored summary kept", False), ("failed", "forced refresh failed", True)],
)
def test_the_pregenerate_job_reports_a_forced_refresh_honestly(monkeypatch, capsys, status, detail, job_fails):
    # A kept summary is a keep-better decision, the job's work done; a failed refresh is a failed paid
    # attempt, and "failed" is one of job_run_service's error counters, so the job run fails as it
    # did when the old DELETE turned that case into generation_failed.
    from app.services import job_run_service
    from scripts import pregenerate_examples

    monkeypatch.setattr(precompute_service, "precompute_one", AsyncMock(return_value={
        "ticker": "AAPL", "form": "10-K", "status": status, "filing_id": 7, "accession": "acc-7"}))

    if job_fails:
        with pytest.raises(job_run_service.JobRunFailed):
            asyncio.run(pregenerate_examples.main(["AAPL"], force=True, annual_only=True))
    else:
        asyncio.run(pregenerate_examples.main(["AAPL"], force=True, annual_only=True))

    assert f"AAPL: filing_id=7 accession=acc-7 -> {detail}" in capsys.readouterr().out
