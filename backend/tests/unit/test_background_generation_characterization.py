"""T2 — characterization of ``generate_summary_background`` (the S1 "before photo").

This is the anchor that pins the *current* behavior of the background/cron generation path so the
Wave-2 S1 unification (routing it through ``stream_filing_summary``) can't silently change it. It
drives the REAL function against a seeded SQLite DB (the ``test_inflight_dedup`` pattern) — no
MagicMock DB.

This first slice covers the early-return branches, which reach a decision *before* the generation
core and so need no service mocking:
  - filing not found → no-op (no Summary row);
  - ``OPENAI_API_KEY`` unset → a placeholder Summary is persisted;
  - a Summary already exists → no regeneration.

The full-path assertions the plan also calls for — the ``previous_filings`` divergence (10-K gets
prior-10-K context, other forms ``None``), the 9-vs-7 coverage taxonomy, the ``determine_result_type``
verdict, no-row-on-partial, usage/quota, and zero PostHog funnel events on precompute — are the next
increment (they require mocking the fetch/XBRL/AI boundaries in this module's namespace; template:
``tests/integration/test_summaries_flow.py``).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import summary_generation_service
from app.services.summary_generation_service import generate_summary_background


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _seed_filing(filing_type: str = "10-K") -> int:
    """Seed a Company + Filing (unique, to avoid cross-test collisions) and return the filing id."""
    from app.database import SessionLocal
    from app.models import Company, Filing

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        company = Company(cik=f"cik{suffix}", ticker=f"BG{suffix[:4].upper()}", name="Background Co")
        db.add(company)
        db.commit()
        db.refresh(company)
        filing = Filing(
            company_id=company.id,
            accession_number=f"acc-{suffix}",
            filing_type=filing_type,
            filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/d.htm",
            sec_url=f"https://sec.example/{suffix}/",
        )
        db.add(filing)
        db.commit()
        db.refresh(filing)
        return filing.id


@pytest.mark.asyncio
async def test_missing_filing_is_a_noop():
    """A filing_id that doesn't exist returns without writing anything."""
    from app.database import SessionLocal
    from app.models import Summary

    missing_id = 990_500_000  # far above any autoincrement id the suite creates
    await generate_summary_background(missing_id, None)

    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == missing_id).first() is None


@pytest.mark.asyncio
async def test_no_api_key_persists_a_placeholder_summary(monkeypatch):
    """With OPENAI_API_KEY unset, the background path persists a placeholder Summary (current
    behavior) rather than failing — S1 must preserve or consciously change this."""
    from app.database import SessionLocal
    from app.models import Summary

    filing_id = _seed_filing()
    monkeypatch.setattr(summary_generation_service.settings, "OPENAI_API_KEY", "")

    await generate_summary_background(filing_id, None)

    with SessionLocal() as db:
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        assert summary is not None
        assert "OpenAI API key" in summary.business_overview
        assert summary.raw_summary == {"error": "OpenAI API key not configured"}


@pytest.mark.asyncio
async def test_existing_summary_is_not_regenerated():
    """If a Summary already exists for the filing, the background path returns without creating a
    second one (idempotence on the cron path)."""
    from app.database import SessionLocal
    from app.models import Summary

    filing_id = _seed_filing()
    with SessionLocal() as db:
        db.add(Summary(filing_id=filing_id, business_overview="EXISTING SUMMARY"))
        db.commit()

    # Guard: summarize_filing must NOT be reached on the existing-summary path.
    called = MagicMock()
    original = summary_generation_service.openai_service.summarize_filing
    summary_generation_service.openai_service.summarize_filing = called
    try:
        await generate_summary_background(filing_id, None)
    finally:
        summary_generation_service.openai_service.summarize_filing = original

    called.assert_not_called()
    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).count() == 1


# --- previous_filings divergence (the core S1 "before photo") ---------------------------------
# The background path injects the prior 10-K as year-over-year context for a 10-K, and passes None
# for other forms. The SSE path hardcodes previous_filings=None. S1 unification must not silently
# resolve this difference — these tests pin it.

_SUMMARY_DATA = {
    "status": "complete",
    "business_overview": "A technology company that designs and sells consumer electronics worldwide.",
    "financial_highlights": {"revenue": "1B", "notes": "Revenue increased 12% year over year."},
    "risk_factors": [{"summary": "Supply-chain constraints may impact production.", "supporting_evidence": "Item 1A."}],
    "management_discussion": "MD&A covers results of operations and financial condition.",
    "key_changes": "Higher R&D investment and expanded manufacturing capacity.",
    "raw_summary": {"sections": {"x": "y"}, "section_coverage": {"covered_count": 5, "total_count": 7}},
}


def _mock_generation_boundaries(monkeypatch):
    """Patch the network/AI/excerpt boundaries (in this module's namespace) so the generation core
    runs offline; return the summarize_filing AsyncMock so the caller can inspect its kwargs."""
    monkeypatch.setattr(
        summary_generation_service.sec_edgar_service, "get_filing_document",
        AsyncMock(return_value="FILING DOCUMENT TEXT " * 40),
    )
    monkeypatch.setattr(
        summary_generation_service.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        summary_generation_service.xbrl_service, "get_filing_sections", AsyncMock(return_value=None),
    )
    # Bypass excerpt construction (BeautifulSoup/cache) — not what these tests characterize.
    monkeypatch.setattr(
        summary_generation_service, "get_or_cache_excerpt", lambda *a, **k: "EXCERPT",
    )
    summarize = AsyncMock(return_value=_SUMMARY_DATA)
    monkeypatch.setattr(summary_generation_service.openai_service, "summarize_filing", summarize)
    return summarize


@pytest.mark.asyncio
async def test_10k_injects_prior_10k_as_previous_filings(monkeypatch):
    """A 10-K with a prior 10-K passes that prior to summarize_filing as previous_filings context."""
    from app.database import SessionLocal
    from app.models import Company, Filing

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        company = Company(cik=f"cik{suffix}", ticker=f"YY{suffix[:4].upper()}", name="YoY Co")
        db.add(company)
        db.commit()
        db.refresh(company)
        prior = Filing(
            company_id=company.id, accession_number=f"acc-prior-{suffix}", filing_type="10-K",
            filing_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/prior.htm", sec_url=f"https://sec.example/{suffix}/p/",
        )
        current = Filing(
            company_id=company.id, accession_number=f"acc-cur-{suffix}", filing_type="10-K",
            filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/cur.htm", sec_url=f"https://sec.example/{suffix}/c/",
        )
        db.add_all([prior, current])
        db.commit()
        db.refresh(current)
        current_id = current.id

    summarize = _mock_generation_boundaries(monkeypatch)
    await generate_summary_background(current_id, None)

    summarize.assert_called_once()
    previous = summarize.call_args.kwargs["previous_filings"]
    assert previous is not None
    assert len(previous) == 1  # the one prior 10-K, injected as YoY trend context


@pytest.mark.asyncio
async def test_10q_passes_no_previous_filings(monkeypatch):
    """A 10-Q does not fetch prior filings — summarize_filing receives previous_filings=None."""
    from app.database import SessionLocal
    from app.models import Company, Filing

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        company = Company(cik=f"cik{suffix}", ticker=f"QQ{suffix[:4].upper()}", name="Quarterly Co")
        db.add(company)
        db.commit()
        db.refresh(company)
        current = Filing(
            company_id=company.id, accession_number=f"acc-q-{suffix}", filing_type="10-Q",
            filing_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/q.htm", sec_url=f"https://sec.example/{suffix}/q/",
        )
        db.add(current)
        db.commit()
        db.refresh(current)
        current_id = current.id

    summarize = _mock_generation_boundaries(monkeypatch)
    await generate_summary_background(current_id, None)

    summarize.assert_called_once()
    assert summarize.call_args.kwargs["previous_filings"] is None
