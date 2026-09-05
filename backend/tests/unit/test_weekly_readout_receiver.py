"""The weekly receiver uses the real bounded validator and mocked email transport only."""
import asyncio
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base
from app.services import data_quality_service, email_service, job_run_service, resend_service
from app.services.ai_readout import encode_readout, unavailable_readout
from scripts import data_quality_report


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'receiver.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(job_run_service, "SessionLocal", sessions)
    monkeypatch.setattr(data_quality_service, "ticker_integrity", AsyncMock(return_value={"mismatches": [], "not_in_file": []}))
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(resend_service, "send_email", send)
    yield sessions, send
    engine.dispose()


def complete_readout():
    readout = unavailable_readout("")
    readout.update(status="complete", source_sha="a" * 40, cohort_sha256="b" * 64,
                   golden_set_sha256="c" * 64, run_url="https://github.com/neilmac91/EarningsNerd/actions/runs/123",
                   artifact_url="https://github.com/neilmac91/EarningsNerd/actions/runs/123/artifacts/456",
                   generator_model="deepseek-v4-pro", completed=24, scored=24, missing=0,
                   negative_judgments=2, deterministic_vetoes=1,
                   dimensions={"faithfulness": 4.0, "insight": 3.5, "clarity": 4.2, "specificity": 3.8})
    return readout


def test_real_cli_receives_complete_negative_judgments_without_sending(receiver, monkeypatch, capsys):
    _, send = receiver
    readout = complete_readout()
    path = Path(__file__).parents[2] / "scripts/data_quality_report.py"
    monkeypatch.setattr(sys, "argv", [str(path), "--dry-run", "--weekly-readout-b64", encode_readout(readout)])
    runpy.run_path(str(path), run_name="__main__")
    report = json.loads(capsys.readouterr().out)
    assert report["weekly_readout"] == readout
    assert report["summary_audits"]["snapshot_population"] == 0
    assert "universe_coverage" in report and "job_health" in report
    send.assert_not_awaited()
    html, text = email_service.render_data_quality_report(report)
    assert "negative judgments · 2" in html and "negative judgments: 2" in text
    assert "deterministic vetoes · 1" in html and "deterministic vetoes: 1" in text
    for rendered in (html, text):
        assert "No weekly readout supplied" not in rendered
        assert "deterministic vetoes" in rendered
        assert "faithfulness" in rendered and "4.0" in rendered
        assert "configured generator model" in rendered and "deepseek-v4-pro" in rendered
        assert "configured judge model" in rendered and "claude-opus-4-8" in rendered
        assert readout["artifact_url"] in rendered
        assert "This report never activates guards" in rendered


@pytest.mark.parametrize("encoded", [None, "not base64", "A" * 9000])
def test_missing_invalid_or_oversize_readout_keeps_operational_report_visible(receiver, capsys, encoded):
    _, send = receiver
    asyncio.run(data_quality_report._main(dry_run=True, weekly_readout_b64=encoded))
    report = json.loads(capsys.readouterr().out)
    readout = report["weekly_readout"]
    assert readout["status"] == "unavailable" and readout["scored"] == 0 and readout["missing"] == 24
    assert all(value is None for value in readout["dimensions"].values())
    assert "universe_coverage" in report and "summary_audits" in report
    for rendered in email_service.render_data_quality_report(report):
        assert "unavailable" in rendered
        assert "do not satisfy the first-readout prerequisite" in rendered
    send.assert_not_awaited()


def test_email_receiver_preserves_readout_and_escapes_visible_and_hidden_text(receiver):
    _, send = receiver
    reason = '<script>alert("unsafe")</script>'
    readout = unavailable_readout(reason)
    asyncio.run(data_quality_report._main(dry_run=False, weekly_readout_b64=encode_readout(readout)))
    send.assert_awaited_once()
    html = send.await_args.kwargs["html"]
    visible, hidden = html.split('<pre style="display:none">')
    for part in (visible, hidden):
        assert "<script>" not in part
        assert "&lt;script&gt;" in part
        assert "unavailable" in part
    assert send.await_args.kwargs["subject"] == "EarningsNerd data-quality report"
