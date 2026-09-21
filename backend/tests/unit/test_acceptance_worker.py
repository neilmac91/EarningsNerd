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


def _sixk_fixture(tmp_path, *, with_release=True):
    primary = "<html><body>Cover page material contained in this report.</body></html>"
    exhibit = "<html><body>Revenue was 10 million dollars in the quarter.</body></html>"
    source_root, spec, _ = _source_fixture(tmp_path, primary)
    spec["filing_type"] = "6-K"
    folder = source_root / "e7-sources" / "H01"
    documents = [f"<DOCUMENT>\n<TYPE>6-K\n<SEQUENCE>1\n<FILENAME>filing.htm\n<TEXT>{primary}</TEXT>\n</DOCUMENT>"]
    if with_release:
        documents.append(f"<DOCUMENT>\n<TYPE>EX-99.1\n<SEQUENCE>2\n<FILENAME>release.htm\n"
                         f"<TEXT>{exhibit}</TEXT>\n</DOCUMENT>")
        path = folder / "release.htm"
        path.write_text(exhibit, encoding="utf-8")
        sha = hashlib.sha256(exhibit.encode()).hexdigest()
        spec["source_packets"].append({"role": "earnings_exhibit", "path": "e7-sources/H01/release.htm",
                                       "bytes": len(exhibit.encode()), "sha256": sha,
                                       "provenance": {"representation": "httpx_decoded_response_text_utf8",
                                                      "sha256": sha, "requested_url": "https://www.sec.gov/release.htm"}})
    sgml = ("<SUBMISSION>\n<ACCESSION-NUMBER>0000000001-00-000001\n<TYPE>6-K\n"
            f"<PUBLIC-DOCUMENT-COUNT>{len(documents)}\n<PERIOD>20251231\n<FILING-DATE>20260115\n"
            "<FILER>\n<COMPANY-DATA>\n<CONFORMED-NAME>Test Company\n<CIK>0000000001\n"
            "</COMPANY-DATA>\n</FILER>\n" + "\n".join(documents) + "\n</SUBMISSION>")
    path = folder / "complete.txt"
    path.write_text(sgml, encoding="utf-8")
    sha = hashlib.sha256(sgml.encode()).hexdigest()
    spec["source_packets"].append({"role": "complete_submission", "path": "e7-sources/H01/complete.txt",
                                   "bytes": len(sgml.encode()), "sha256": sha,
                                   "provenance": {"representation": "httpx_decoded_response_text_utf8",
                                                  "sha256": sha, "requested_url": "https://www.sec.gov/complete.txt"}})
    return source_root, spec, primary, exhibit


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
@pytest.mark.parametrize("with_release", [True, False])
async def test_sixk_uses_embedded_sdk_extractor_or_verified_primary_fallback(tmp_path, monkeypatch,
                                                                             with_release):
    source_root, spec, primary, exhibit = _sixk_fixture(tmp_path, with_release=with_release)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=primary))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))
    from edgar import attachments as edgar_attachments
    from edgar.attachments import FilingHomepage

    def no_network(*_args, **_kwargs):
        raise AssertionError("SDK network attempted")

    monkeypatch.setattr(edgar_attachments, "download_file", no_network)
    monkeypatch.setattr(FilingHomepage, "load", no_network)
    seen = []

    async def fake_summary(text, *_args, **kwargs):
        seen.append(text)
        if kwargs["stream_cb"]:
            await kwargs["stream_cb"]("synthetic preview")
        return json.loads(json.dumps(CANONICAL_PAYLOAD))

    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", fake_summary)
    receipt = await run_invocation(spec, invocation_dir, config, StubMeter())
    assert receipt["status"] == "complete", receipt["errors"]
    assert receipt["source_identity"] == "archived_sgml_verified"
    assert ("Revenue was 10 million dollars" if with_release else primary) in seen[0]
    calls = json.loads((invocation_dir / "grounding.json").read_text())["source_calls"]
    assert any(call.get("complete_submission_sha256") == spec["source_packets"][-1]["sha256"] for call in calls)
    assert any(call.get("source_packet_match") == "verified_complete_submission" for call in calls)


@pytest.mark.asyncio
async def test_sixk_embedded_exhibit_mismatch_stops_before_provider(tmp_path, monkeypatch):
    source_root, spec, _, _ = _sixk_fixture(tmp_path)
    exhibit_packet = next(p for p in spec["source_packets"] if p["role"] == "earnings_exhibit")
    exhibit_path = source_root / exhibit_packet["path"]
    exhibit_path.write_text(exhibit_path.read_text() + " altered", encoding="utf-8")
    exhibit_packet["bytes"] = exhibit_path.stat().st_size
    exhibit_packet["sha256"] = hashlib.sha256(exhibit_path.read_bytes()).hexdigest()
    exhibit_packet["provenance"]["sha256"] = exhibit_packet["sha256"]
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    summarize = AsyncMock(return_value=CANONICAL_PAYLOAD)
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", summarize)
    with pytest.raises(InvalidMeasurement, match="embedded earnings exhibit differs"):
        await run_invocation(spec, invocation_dir, config, StubMeter())
    summarize.assert_not_awaited()
    assert not (invocation_dir / "invocation.sqlite3").exists()


@pytest.mark.asyncio
async def test_sixk_wrong_sgml_identity_stops_before_database(tmp_path, monkeypatch):
    source_root, spec, _, _ = _sixk_fixture(tmp_path)
    submission = next(p for p in spec["source_packets"] if p["role"] == "complete_submission")
    path = source_root / submission["path"]
    path.write_text(path.read_text().replace("<ACCESSION-NUMBER>0000000001-00-000001",
                                             "<ACCESSION-NUMBER>0000000001-00-000002"), encoding="utf-8")
    submission["bytes"] = path.stat().st_size
    submission["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    submission["provenance"]["sha256"] = submission["sha256"]
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    with pytest.raises(InvalidMeasurement, match="parsed identity differs"):
        await run_invocation(spec, invocation_dir, config, StubMeter())
    assert not (invocation_dir / "invocation.sqlite3").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["network", "wrong_filing"])
async def test_sixk_swallowed_source_fault_never_reaches_provider(tmp_path, monkeypatch, fault):
    source_root, spec, primary, _ = _sixk_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=primary))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))
    from app.services.edgar import sixk_extractor
    from edgar import attachments as edgar_attachments

    def force_sdk_fault(*_args):
        if fault == "network":
            return edgar_attachments.download_file("https://www.sec.gov/unexpected")
        return sixk_extractor.resolve_filing_by_accession("999", spec["accession_number"])

    monkeypatch.setattr(sixk_extractor, "_extract_sixk_text_sync", force_sdk_fault)
    provider = AsyncMock(return_value=CANONICAL_PAYLOAD)
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", provider)
    receipt = await run_invocation(spec, invocation_dir, config, StubMeter())
    assert receipt["status"] == "incomplete"
    assert receipt["source_identity"] == "incomplete"
    assert ("6-K SDK attempted network fallback" if fault == "network" else
            "6-K SDK requested a different filing") in receipt["errors"]
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_sixk_missing_bound_filing_never_reaches_provider(tmp_path, monkeypatch):
    source_root, spec, primary, _ = _sixk_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    from evals import acceptance_worker

    monkeypatch.setattr(acceptance_worker, "_prepare_sixk_source",
                        lambda *_args: (None, {"complete_submission_sha256": "synthetic"}))
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=primary))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))
    provider = AsyncMock(return_value=CANONICAL_PAYLOAD)
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", provider)
    receipt = await run_invocation(spec, invocation_dir, config, StubMeter())
    assert receipt["status"] == "incomplete"
    assert "6-K source binding missing" in receipt["errors"]
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_sixk_preparation_rejects_swallowed_sdk_network_attempt(tmp_path, monkeypatch):
    source_root, spec, _, _ = _sixk_fixture(tmp_path)
    invocation_dir = tmp_path / "run"
    config = _configure(monkeypatch, invocation_dir, source_root)
    from edgar import Filing as EdgarFiling
    from edgar import attachments as edgar_attachments

    original_obj = EdgarFiling.obj

    def obj_with_swallowed_fallback(self):
        try:
            edgar_attachments.download_file("https://www.sec.gov/unexpected")
        except InvalidMeasurement:
            pass
        return original_obj(self)

    monkeypatch.setattr(EdgarFiling, "obj", obj_with_swallowed_fallback)
    provider = AsyncMock(return_value=CANONICAL_PAYLOAD)
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", provider)
    with pytest.raises(InvalidMeasurement, match="network fallback during source preparation"):
        await run_invocation(spec, invocation_dir, config, StubMeter())
    provider.assert_not_awaited()
    assert not (invocation_dir / "invocation.sqlite3").exists()
