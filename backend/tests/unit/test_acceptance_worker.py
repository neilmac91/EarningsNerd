"""Offline E7 worker checks through the real pipeline and frozen-source adapter."""

import hashlib
import json
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.config import settings
from app.services import summary_pipeline, summary_generation_service
from app.services.ai import provider_requests
from evals.acceptance_worker import (
    REQUIRED_FROZEN_SETTINGS, InvalidMeasurement, SourceBoundMeter, expected_database_url, run_invocation,
)
from tests.support.summary_stream_harness import CANONICAL_PAYLOAD
from tests.unit.test_acceptance_archive import _fixture


class StubMeter:
    def snapshot(self):
        return {"slot_id": "synthetic", "requests": [{"reservation_id": 17, "usage": {"total_tokens": 9}}]}


def setup_sources(tmp_path, monkeypatch, *, form="10-K", with_release=False):
    root, spec, content, submissions, facts, embedding = _fixture(
        tmp_path, form=form, with_release=with_release)
    invocation = tmp_path / "run"
    config = _configure(monkeypatch, invocation, root, {
        "submissions": submissions, "companyfacts": facts, "embedding": embedding,
    })
    return root, spec, content, invocation, config


def _configure(monkeypatch, invocation_dir, source_root, records):
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
    monkeypatch.setattr(provider_requests, "current_provider_attempt", lambda: 17, raising=False)
    return {"source_root": str(source_root), "frozen_settings": frozen,
            "allow_sec_network": False, "allow_provider": True, "source_binding": records}



@pytest.mark.asyncio
@pytest.mark.parametrize("form,with_release", [("10-K", False), ("10-Q", False), ("20-F", False),
                                                 ("6-K", True), ("6-K", False)])
async def test_worker_uses_frozen_sources_and_retains_every_surface(tmp_path, monkeypatch, form, with_release):
    root, spec, content, invocation, config = setup_sources(tmp_path, monkeypatch, form=form, with_release=with_release)
    live = AsyncMock(side_effect=AssertionError("Live SEC fetch attempted"))
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document", live)
    seen = []

    async def fake_summary(text, *args, **kwargs):
        assert isinstance(provider_requests._request_meter.get(), SourceBoundMeter)
        seen.append(text)
        await kwargs["stream_cb"]("first raw preview")
        await kwargs["stream_cb"]("second raw preview")
        return json.loads(json.dumps(CANONICAL_PAYLOAD))

    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", fake_summary)
    receipt = await run_invocation(spec, invocation, config, StubMeter())
    assert receipt["status"] == "complete", receipt["errors"]
    assert receipt["source_identity"] == "frozen_archive_verified"
    assert receipt["artifact_sha256"] == {
        key: hashlib.sha256((invocation / relative).read_bytes()).hexdigest()
        for key, relative in receipt["artifacts"].items()
    }
    assert json.loads((invocation / "receipt.json").read_text()) == receipt
    previews = [json.loads(line) for line in (invocation / "raw_previews.jsonl").read_text().splitlines()]
    assert [item["markdown"] for item in previews] == ["first raw preview", "second raw preview"]
    assert {item["provider_attempt"] for item in previews} == {17}
    grounding = json.loads((invocation / "grounding.json").read_text())
    from app.models import Company
    with database.SessionLocal() as session:
        assert session.query(Company).one().sic == "3571"
    assert grounding["seeded_company_metadata"] == {
        "sic": "3571", "source_sha256": receipt["source_packets"]["company_submissions"]["sha256"],
    }
    archive = grounding["archive_binding"]
    assert archive["source_violations"] == []
    assert archive["source_evidence"] == receipt["source_packets"]
    calls = archive["source_calls"]
    if form != "6-K":
        assert any(row["path"] == "edgar.companyfacts" and row["outcome"] == "bound" for row in calls)
    else:
        assert any(row["path"] == "edgar.get_sixk_text" for row in calls)
    assert any(row["path"] == "statement_source" and row["outcome"] == "bound" for row in calls)
    assert any(row["path"] == "filing_excerpt" and row["outcome"] == "returned" for row in calls)
    if form == "6-K" and with_release:
        assert "Archived earnings release facts and management context." in seen[0]
    else:
        assert seen == [content]
    for name in ("canonical_summary.json", "rendered_summary.md", "export.html"):
        assert (invocation / name).exists()
    live.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_packet_or_wrong_database_fails_before_execution(tmp_path, monkeypatch):
    root, spec, _, invocation, config = setup_sources(tmp_path, monkeypatch)
    spec["source_packets"][0]["sha256"] = "0" * 64
    with pytest.raises(InvalidMeasurement, match="hash/size mismatch"):
        await run_invocation(spec, invocation, config, StubMeter())
    assert not (invocation / "invocation.sqlite3").exists()
    spec["source_packets"][0]["sha256"] = spec["source_sha256"]
    monkeypatch.setattr(database, "engine", create_engine("sqlite:///:memory:"))
    with pytest.raises(InvalidMeasurement, match="Imported app database engine"):
        await run_invocation(spec, invocation, config, StubMeter())
    assert not (invocation / "invocation.sqlite3").exists()


@pytest.mark.asyncio
async def test_missing_source_contract_fails_before_execution(tmp_path, monkeypatch):
    _, spec, _, invocation, config = setup_sources(tmp_path, monkeypatch)
    config.pop("source_binding")
    with pytest.raises(InvalidMeasurement, match="requires a verified frozen archive"):
        await run_invocation(spec, invocation, config, StubMeter())
    assert not (invocation / "invocation.sqlite3").exists()


@pytest.mark.asyncio
async def test_partial_result_is_retained_but_not_eligible(tmp_path, monkeypatch):
    _, spec, _, invocation, config = setup_sources(tmp_path, monkeypatch)
    payload = json.loads(json.dumps(CANONICAL_PAYLOAD))
    payload["status"] = "partial"
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", AsyncMock(return_value=payload))
    receipt = await run_invocation(spec, invocation, config, StubMeter())
    assert receipt["status"] == "incomplete"
    assert not receipt["eligible_for_measurement"]
    assert (invocation / "canonical_summary.json").exists()
    assert (invocation / "grounding.json").exists()
    events = [json.loads(line) for line in (invocation / "events.jsonl").read_text().splitlines()]
    assert events[-1]["type"] == "partial"


@pytest.mark.asyncio
async def test_stream_disabled_preserves_non_streaming_provider_mode(tmp_path, monkeypatch):
    _, spec, _, invocation, config = setup_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "STREAM_SECTION_REVEAL", False)
    config["frozen_settings"]["STREAM_SECTION_REVEAL"] = False

    async def fake_summary(*args, **kwargs):
        assert kwargs["stream_cb"] is None
        return json.loads(json.dumps(CANONICAL_PAYLOAD))

    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", fake_summary)
    receipt = await run_invocation(spec, invocation, config, StubMeter())
    assert receipt["status"] == "complete", receipt["errors"]
    assert (invocation / "raw_previews.jsonl").read_text() == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["network", "wrong_filing", "unbound_xbrl"])
async def test_swallowed_source_fault_never_reaches_provider(tmp_path, monkeypatch, fault):
    _, spec, _, invocation, config = setup_sources(tmp_path, monkeypatch,
                                                          form="10-K" if fault == "unbound_xbrl" else "6-K")
    from app.services.edgar import sixk_extractor
    from edgar import attachments

    def force_fault(*_args):
        if fault == "network":
            return attachments.download_file("https://www.sec.gov/unexpected")
        return sixk_extractor.resolve_filing_by_accession("999", spec["accession_number"])

    if fault == "unbound_xbrl":
        monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value={"revenues": 999}))
    else:
        monkeypatch.setattr(sixk_extractor, "_extract_sixk_text_sync", force_fault)
    provider = AsyncMock(return_value=CANONICAL_PAYLOAD)
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", provider)
    receipt = await run_invocation(spec, invocation, config, StubMeter())
    assert receipt["status"] == "incomplete"
    assert receipt["source_identity"] == "incomplete"
    assert json.loads((invocation / "grounding.json").read_text())["archive_binding"]["source_violations"]
    provider.assert_not_awaited()


def test_every_provider_reservation_checks_source_binding(tmp_path):
    from evals.acceptance_archive import prepare_archive_binding
    from edgar import attachments

    root, spec, _, submissions, facts, embedding = _fixture(tmp_path)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)
    delegate = Mock()
    delegate.reserve.return_value = 17
    meter = SourceBoundMeter(delegate, binding)
    with pytest.raises(InvalidMeasurement, match="patch is not active"):
        meter.reserve({}, "summary_primary", "https://fake.invalid")
    with pytest.raises(InvalidMeasurement, match="Archive source violation"):
        with binding.patch_production():
            # Covers the initial request followed by a swallowed fault before a
            # recovery or retry: no second reservation (and thus no SDK I/O).
            assert meter.reserve({}, "summary_primary", "https://fake.invalid") == 17
            try:
                attachments.download_file("https://www.sec.gov/unexpected")
            except InvalidMeasurement:
                pass
            with pytest.raises(InvalidMeasurement, match="Archive source violation"):
                meter.reserve({}, "section_recovery", "https://fake.invalid")
    assert delegate.reserve.call_count == 1
