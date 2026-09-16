"""The job-side stale-summary drain: shared staleness encoding, honest bounded outcomes, durable ledger.

Generation is replaced by a spy (the in-place UPDATE and keep-better mechanics are pinned in
test_background_generation_characterization.py); selection, bounds, classification and the job
ledger are real, on an isolated SQLite database."""
import functools
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, Filing, JobRun, Summary
from app.routers import admin
from app.services import job_run_service as jobs
from app.services import summary_refresh
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION
from scripts import refresh_stale_summaries as script

GENERATOR = "app.services.summary_generation_service.generate_summary_background"


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'drain.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _seed(sessions, stamps):
    """One company; one filing + summary per (schema_version, prompt_version, form)."""
    with sessions() as db:
        company = Company(cik="1", ticker="DRN", name="Drain Co")
        db.add(company)
        db.flush()
        ids = []
        for i, (schema, prompt, form) in enumerate(stamps):
            filing = Filing(company_id=company.id, accession_number=f"acc-{i}", filing_type=form,
                            filing_date=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                            document_url=f"https://sec.example/{i}.htm", sec_url=f"https://sec.example/{i}/")
            db.add(filing)
            db.flush()
            db.add(Summary(filing_id=filing.id, business_overview=f"summary {i}", schema_version=schema,
                           prompt_version=prompt, raw_summary={"quality": {"tier": "full"}}))
            ids.append(filing.id)
        db.commit()
        return ids


CURRENT = (SUMMARY_SCHEMA_VERSION, SUMMARY_PROMPT_VERSION)


def _last_report(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_shared_filter_is_the_admin_endpoints_filter():
    assert admin._stale_summary_filter is summary_refresh.stale_filter  # one encoding, pinned to is_stale elsewhere


def test_dry_run_reports_the_breakdown_records_a_dry_run_and_generates_nothing(sessions, monkeypatch, capsys):
    _seed(sessions, [(None, None, "10-K"), (SUMMARY_SCHEMA_VERSION, "summary-2026-09-m", "10-Q"),
                     (SUMMARY_SCHEMA_VERSION, "summary-2026-09-m", "10-K"), (*CURRENT, "10-K")])
    spy = AsyncMock()
    monkeypatch.setattr(GENERATOR, spy)
    assert script.main([]) == 0
    report = _last_report(capsys)
    assert report["dry_run"] is True and report["summaries_total"] == 4 and report["stale_total"] == 3
    assert report["by_stamp"] == {f"{SUMMARY_SCHEMA_VERSION}/summary-2026-09-m": 2, "null/null": 1}
    assert report["by_form"] == {"10-K": 2, "10-Q": 1}
    assert report["current_prompt_version"] == SUMMARY_PROMPT_VERSION and "updated" not in report
    spy.assert_not_called()
    with sessions() as db:
        run = db.query(JobRun).one()
        assert run.job_name == "refresh-stale" and run.status == "dry_run"
        assert run.counters == {"summaries_total": 4, "stale_total": 3}


def _stamp_current(sessions):
    def side_effect(filing_id, _user_id, *, force_regenerate=False):
        assert force_regenerate is True
        with sessions() as db:
            row = db.query(Summary).filter(Summary.filing_id == filing_id).first()
            row.schema_version, row.prompt_version = CURRENT
            db.commit()
        return {"type": "done"}
    return side_effect


def test_execute_classifies_updated_kept_error_event_and_exception_honestly_and_fails_the_run(
    sessions, monkeypatch, capsys,
):
    ids = _seed(sessions, [(None, None, "10-K")] * 4 + [(*CURRENT, "10-Q")])
    kept_id, raised_id, errored_id = ids[1], ids[2], ids[3]
    stamp = _stamp_current(sessions)
    engine = sessions.kw["bind"]

    def generate(filing_id, user_id, *, force_regenerate=False):
        assert engine.pool.checkedout() == 0  # no drain session or pooled connection is held during a generation
        if filing_id == raised_id:
            raise RuntimeError("provider unavailable")
        if filing_id == errored_id:  # the orchestrator converts failures into a terminal error EVENT
            return {"type": "error", "message": "SEC fetch timed out"}
        if filing_id == kept_id:  # the keep-better gate kept the stored version: row stays stale
            return {"type": "done"}
        return stamp(filing_id, user_id, force_regenerate=force_regenerate)

    spy = AsyncMock(side_effect=generate)
    monkeypatch.setattr(GENERATOR, spy)
    assert script.main(["--execute", "--limit", "10"]) == 1  # a failed regeneration is a failed execution
    report = _last_report(capsys)
    assert report["dry_run"] is False and report["stale_total"] == 4 and report["attempted"] == 4
    assert (report["updated"], report["kept_by_gate"], report["failed"], report["deferred"]) == (1, 1, 2, 0)
    assert report["kept_by_gate_filing_ids"] == [kept_id] and sorted(report["failed_filing_ids"]) == sorted([raised_id, errored_id])
    assert spy.await_count == 4 and all(call.kwargs == {"force_regenerate": True} for call in spy.await_args_list)
    with sessions() as db:
        run = db.query(JobRun).one()
        assert run.status == "failed" and run.error_type == "JobRunFailed"
        assert run.counters == {"summaries_total": 5, "stale_total": 4, "attempted": 4,
                                "updated": 1, "kept_by_gate": 1, "failed": 2, "deferred": 0}
        assert db.query(Summary).filter(Summary.filing_id == kept_id).one().prompt_version is None
        assert db.query(Summary).filter(Summary.filing_id == ids[0]).one().prompt_version == SUMMARY_PROMPT_VERSION


def test_limit_and_time_budget_bound_the_paid_work(sessions, monkeypatch, capsys):
    _seed(sessions, [(None, None, "10-K")] * 5)
    spy = AsyncMock(side_effect=_stamp_current(sessions))
    monkeypatch.setattr(GENERATOR, spy)
    assert script.main(["--execute", "--limit", "2"]) == 0
    report = _last_report(capsys)
    assert report["stale_total"] == 5 and report["attempted"] == 2 and report["updated"] == 2
    # Time budget: the drain's clock passes the budget after the first generation, so the rest are
    # deferred, never started (the clock is injected into the drain only; asyncio keeps the real one).
    ticks = iter([0.0, 0.0, 100.0])
    original = summary_refresh.drain_stale
    monkeypatch.setattr(summary_refresh, "drain_stale", functools.partial(original, clock=lambda: next(ticks, 100.0)))
    spy.reset_mock()
    assert script.main(["--execute", "--limit", "3", "--max-seconds", "50"]) == 0
    report = _last_report(capsys)
    assert report["stale_total"] == 3 and report["attempted"] == 1 and report["deferred"] == 2
    assert spy.await_count == 1
    with sessions() as db:
        assert [r.status for r in db.query(JobRun).order_by(JobRun.started_at)] == ["succeeded", "succeeded"]


def test_schema_threshold_above_the_current_schema_is_refused_before_any_work(sessions, monkeypatch, capsys):
    _seed(sessions, [(None, None, "10-K")])
    spy = AsyncMock(side_effect=_stamp_current(sessions))
    monkeypatch.setattr(GENERATOR, spy)
    with pytest.raises(SystemExit) as exc:  # argparse error: exit code 2, nothing recorded, nothing spent
        script.main(["--execute", "--schema-version-lt", str(SUMMARY_SCHEMA_VERSION + 1)])
    assert exc.value.code == 2 and "exceeds the current schema version" in capsys.readouterr().err
    spy.assert_not_called()
    with sessions() as db:
        assert db.query(JobRun).count() == 0
    # A threshold at or below the current schema works and classifies against that same threshold.
    assert script.main(["--execute", "--schema-version-lt", str(SUMMARY_SCHEMA_VERSION)]) == 0
    report = _last_report(capsys)
    assert report["stale_total"] == 1 and report["updated"] == 1 and report["kept_by_gate"] == 0
