"""Synthetic, offline checks of the E7 worker's production pipeline boundary."""

import hashlib
import json
from contextlib import nullcontext
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.config import settings
from app.services import summary_pipeline, summary_generation_service
from app.services.ai import provider_requests
from evals.acceptance_worker import (
    REQUIRED_FROZEN_SETTINGS, InvalidMeasurement, expected_database_url, run_invocation,
)
from tests.support.summary_stream_harness import CANONICAL_PAYLOAD


class StubMeter:
    def snapshot(self):
        return {"slot_id": "synthetic", "requests": [{"reservation_id": 17, "usage": {"total_tokens": 9}}]}


def _source_fixture(tmp_path, content="FILING DOCUMENT TEXT " * 200):
    source_root = tmp_path / "source"
    (source_root / "e7-sources" / "H01").mkdir(parents=True)
    source = source_root / "e7-sources" / "H01" / "filing.htm"
    source.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode()).hexdigest()
    url = "https://www.sec.gov/Archives/edgar/data/1/000000000100000001/filing.htm"
    spec = {
        "holdout_id": "H01", "ticker": "TEST", "company_name": "Test Company",
        "cik": "1", "filing_type": "10-K", "accession_number": "0000000001-00-000001",
        "filing_date": "2026-01-15", "period_of_report": "2025-12-31",
        "document_url": url, "index_url": url.replace("filing.htm", "index.htm"),
        "source_sha256": digest,
        "source_packets": [{"role": "primary", "path": "e7-sources/H01/filing.htm",
                            "bytes": len(content.encode()), "sha256": digest,
                            "provenance": {"representation": "httpx_decoded_response_text_utf8",
                                           "sha256": digest, "requested_url": url}}],
    }
    return source_root, spec, content


def _configure(monkeypatch, invocation_dir, source_root):
    invocation_dir.mkdir()
    url = expected_database_url(invocation_dir)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(summary_generation_service, "SessionLocal", session_factory)
    monkeypatch.setattr(settings, "STREAM_SECTION_REVEAL", True)
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "")
    monkeypatch.setattr(settings, "AI_FALLBACK_BASE_URL", "")
    monkeypatch.setattr(settings, "AI_FALLBACK_API_KEY", "")
    monkeypatch.setattr(settings, "POSTHOG_API_KEY", "")
    frozen = {key: getattr(settings, key) for key in REQUIRED_FROZEN_SETTINGS}
    monkeypatch.setattr(provider_requests, "measure_provider_requests", lambda meter: nullcontext(), raising=False)
    monkeypatch.setattr(provider_requests, "current_provider_attempt", lambda: 17, raising=False)
    return {"source_root": str(source_root), "frozen_settings": frozen,
            "allow_sec_network": True, "allow_provider": True}


@pytest.mark.asyncio
async def test_worker_runs_real_pipeline_and_retains_every_raw_preview(tmp_path, monkeypatch):
    source_root, spec, content = _source_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=content))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))

    async def fake_summary(*args, **kwargs):
        await kwargs["stream_cb"]("first raw preview")
        await kwargs["stream_cb"]("second raw preview")
        return json.loads(json.dumps(CANONICAL_PAYLOAD))

    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", fake_summary)
    receipt = await run_invocation(spec, invocation_dir, config, StubMeter())
    assert receipt["status"] == "complete", receipt["errors"]
    assert receipt["source_identity"] == "primary_verified"
    previews = [json.loads(line) for line in (invocation_dir / "raw_previews.jsonl").read_text().splitlines()]
    assert [item["markdown"] for item in previews] == ["first raw preview", "second raw preview"]
    assert [item["provider_attempt"] for item in previews] == [17, 17]
    grounding = json.loads((invocation_dir / "grounding.json").read_text())
    assert grounding["summarizer_calls"][0]["args"][0] == content
    assert any(call.get("sha256") == spec["source_sha256"] for call in grounding["source_calls"])
    assert (invocation_dir / "canonical_summary.json").exists()
    assert (invocation_dir / "rendered_summary.md").exists()
    assert (invocation_dir / "export.html").exists()
    assert json.loads((invocation_dir / "provider_accounting.json").read_text())["requests"][0]["reservation_id"] == 17


@pytest.mark.asyncio
async def test_source_mismatch_is_incomplete_before_provider(tmp_path, monkeypatch):
    source_root, spec, content = _source_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document",
                        AsyncMock(return_value=content + " changed"))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))
    summarize = AsyncMock(return_value=CANONICAL_PAYLOAD)
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", summarize)
    receipt = await run_invocation(spec, invocation_dir, config, StubMeter())
    assert receipt["status"] == "incomplete"
    assert any("Primary source" in error for error in receipt["errors"])
    summarize.assert_not_awaited()
    assert (invocation_dir / "events.jsonl").exists()


@pytest.mark.asyncio
async def test_bad_packet_and_imported_database_fail_before_execution(tmp_path, monkeypatch):
    source_root, spec, _ = _source_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    spec["source_packets"][0]["sha256"] = "0" * 64
    with pytest.raises(InvalidMeasurement, match="hash/size mismatch"):
        await run_invocation(spec, invocation_dir, config, StubMeter())
    assert not (invocation_dir / "invocation.sqlite3").exists()
    spec["source_packets"][0]["sha256"] = spec["source_sha256"]
    monkeypatch.setattr(database, "engine", create_engine("sqlite:///:memory:"))
    with pytest.raises(InvalidMeasurement, match="Imported app database engine"):
        await run_invocation(spec, invocation_dir, config, StubMeter())
    assert not (invocation_dir / "invocation.sqlite3").exists()


@pytest.mark.asyncio
async def test_partial_result_is_retained_but_not_eligible(tmp_path, monkeypatch):
    source_root, spec, content = _source_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=content))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))
    payload = json.loads(json.dumps(CANONICAL_PAYLOAD))
    payload["status"] = "partial"
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", AsyncMock(return_value=payload))
    receipt = await run_invocation(spec, invocation_dir, config, StubMeter())
    assert receipt["status"] == "incomplete"
    assert not receipt["eligible_for_measurement"]
    assert (invocation_dir / "canonical_summary.json").exists()
    assert (invocation_dir / "grounding.json").exists()
    events = [json.loads(line) for line in (invocation_dir / "events.jsonl").read_text().splitlines()]
    assert events[-1]["type"] == "partial"


@pytest.mark.asyncio
async def test_stream_disabled_preserves_non_streaming_provider_mode(tmp_path, monkeypatch):
    source_root, spec, content = _source_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    monkeypatch.setattr(settings, "STREAM_SECTION_REVEAL", False)
    config["frozen_settings"]["STREAM_SECTION_REVEAL"] = False
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=content))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))

    async def fake_summary(*args, **kwargs):
        assert kwargs["stream_cb"] is None
        return json.loads(json.dumps(CANONICAL_PAYLOAD))

    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", fake_summary)
    receipt = await run_invocation(spec, invocation_dir, config, StubMeter())
    assert receipt["status"] == "complete", receipt["errors"]
    assert (invocation_dir / "raw_previews.jsonl").read_text() == ""


@pytest.mark.asyncio
async def test_sixk_exhibit_without_packet_identity_is_refused_before_provider(tmp_path, monkeypatch):
    source_root, spec, _ = _source_fixture(tmp_path)
    spec["filing_type"] = "6-K"
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    summarize = AsyncMock(return_value=CANONICAL_PAYLOAD)
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", summarize)
    with pytest.raises(InvalidMeasurement, match="6-K exhibit text lacks"):
        await run_invocation(spec, invocation_dir, config, StubMeter())
    summarize.assert_not_awaited()
    assert not (invocation_dir / "invocation.sqlite3").exists()
