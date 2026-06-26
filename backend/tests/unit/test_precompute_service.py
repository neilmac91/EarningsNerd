"""Precompute service (roadmap A1): idempotent warm-the-cold-path generation + batch cost guard.

DB-backed on SQLite (create_all); SEC fetch and ``generate_summary_background`` are mocked, so no
live SEC/DeepSeek calls. Covers: form validation, idempotent skip (no regeneration when a Summary
exists), dry-run writes/generates nothing, real generation, company-not-found, and the MAX_BATCH
cap + per-item error resilience that bound cost.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

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

    async def fake_gen(filing_id, user_id=None):
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
