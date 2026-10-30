"""8-K earnings sources reach the existing orchestrator before cache and provider."""
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest

from app.database import SessionLocal, engine
from app.models import Base, Filing, FilingContentCache, Summary
from app.services import summary_generation_service, summary_pipeline as pipeline
from app.services.edgar.exceptions import EdgarError
from app.utils.sec_urls import build_sec_archive_url
from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, seed_company_filing, stream_boundaries

COVER = '<p>Item 2.02 Results of Operations and Financial Condition.</p><p>Our earnings release is attached as <a href="release.htm">Exhibit 99.1</a>.</p>'
RELEASE = b'<h1>Third quarter results</h1><p>Revenue $5.1 billion. GAAP EPS $19.16. Cash flow $2.7 billion.</p>'


@pytest.fixture(autouse=True)
def tables():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


def seed_with_legacy_excerpt():
    filing_id = seed_company_filing(filing_type="8-K")
    with SessionLocal() as db:
        filing = db.get(Filing, filing_id)
        # Company fixture identity stays unique; use the same numeric CIK for the
        # URL + company without creating duplicate issuers across the test cases.
        filing.company.cik = str(800_000_000 + filing.company_id)
        filing.accession_number = f"0000872589-26-{filing_id:06d}"
        archive = build_sec_archive_url(filing.company.cik, filing.accession_number)
        filing.document_url = archive + "current.htm"
        filing.sec_url = archive
        db.add(FilingContentCache(filing_id=filing_id, critical_excerpt="LEGACY COVER ONLY WITHOUT EARNINGS"))
        db.commit()
    return filing_id


async def drain(filing_id):
    return [event async for event in pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    )]


def member(content=RELEASE):
    async def fetch(cik, accession_number, filename, **kwargs):
        return content, {"accession_number": accession_number, "filename": filename, "bytes": len(content), "requested_url": build_sec_archive_url(cik, accession_number) + filename}
    return AsyncMock(side_effect=fetch)


@pytest.mark.asyncio
async def test_legacy_cover_cache_rebuilt_release_reaches_provider_and_provenance_persists():
    filing_id = seed_with_legacy_excerpt()
    attachment = member()
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as provider, \
            patch.object(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=COVER)) as primary, \
            patch.object(pipeline.sec_edgar_service, "get_filing_attachment_bytes", attachment), \
            patch.object(pipeline, "get_or_cache_excerpt", summary_generation_service.get_or_cache_excerpt):
        events = await drain(filing_id)
        assert events[-1]["type"] == "complete", events
        primary.assert_awaited_once()
        attachment.assert_awaited_once()
        provider.assert_awaited_once()
        assert "Revenue $5.1 billion" in provider.await_args.args[0]
        assert "GAAP EPS $19.16" in provider.await_args.kwargs["filing_excerpt"]
        assert "LEGACY COVER" not in provider.await_args.kwargs["filing_excerpt"]
    with SessionLocal() as db:
        summary = db.query(Summary).filter_by(filing_id=filing_id).one()
        source = summary.raw_summary["filing_source_provenance"]
        assert source["source"] == "eightk_same_accession_v1"
        assert source["members"][0]["filename"] == "release.htm"
        assert source["members"][0]["accession_number"] == db.get(Filing, filing_id).accession_number
        assert "Cash flow $2.7 billion" in db.query(FilingContentCache).filter_by(filing_id=filing_id).one().critical_excerpt

    # Completed artifacts remain cacheable; a revisit does not generate again.
    with stream_boundaries() as provider, patch.object(pipeline.sec_edgar_service, "get_filing_attachment_bytes", attachment):
        events = await drain(filing_id)
        assert events[-1]["type"] == "complete"
        provider.assert_not_awaited()
        attachment.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [EdgarError("release not published yet"), None])
async def test_unavailable_earnings_never_becomes_cover_only_summary_or_cache(failure):
    filing_id = seed_with_legacy_excerpt()
    attachment = AsyncMock(side_effect=failure) if failure else member(b"<html></html>")
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as provider, \
            patch.object(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=COVER)), \
            patch.object(pipeline.sec_edgar_service, "get_filing_attachment_bytes", attachment), \
            patch.object(pipeline, "get_or_cache_excerpt", summary_generation_service.get_or_cache_excerpt):
        events = await drain(filing_id)
        assert events[-1]["type"] == "error", events
        provider.assert_not_awaited()
    with SessionLocal() as db:
        assert db.query(Summary).filter_by(filing_id=filing_id).count() == 0
        assert db.query(FilingContentCache).filter_by(filing_id=filing_id).one().critical_excerpt == "LEGACY COVER ONLY WITHOUT EARNINGS"
