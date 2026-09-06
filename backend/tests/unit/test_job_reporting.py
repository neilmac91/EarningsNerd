"""WS-7 durable attempts, job adapters, and honest universe/report denominators."""
import asyncio
import builtins
import runpy
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, Filing, JobRun, Summary, User, Watchlist
from app.services import data_quality_service, email_service, index_membership_service
from app.services import job_run_service as jobs
from app.utils.datetimes import utcnow


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.sqlite'}")
    Table("job_runs", MetaData(), Column("legacy_id", Integer, primary_key=True)).create(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    monkeypatch.setattr(database, "SessionLocal", factory)
    yield factory
    engine.dispose()


def test_schema_and_lifecycle_survive_business_rollback(sessions):
    with jobs.track_job("filing-scan") as attempt:
        with sessions() as business:
            business.add(Company(cik="1", ticker="A", name="A"))
            business.flush()
            business.rollback()
        attempt.record({"companies_scanned": 3, "private_ids": [1, 2]})
    with sessions() as db:
        row = db.query(JobRun).one()
        assert JobRun.__tablename__ == "earningsnerd_job_runs"
        assert inspect(db.bind).get_columns("job_runs")[0]["name"] == "legacy_id"
        assert row.status == "succeeded" and row.finished_at is not None
        assert row.counters == {"companies_scanned": 3}
        assert db.query(Company).count() == 0


def test_original_exception_and_dry_run_never_advance_success(sessions):
    with pytest.raises(ValueError, match="business failed"):
        with jobs.track_job("filing-scan"):
            raise ValueError("business failed")
    with jobs.track_job("filing-scan", dry_run=True):
        pass
    with sessions() as db:
        assert {r.status for r in db.query(JobRun)} == {"failed", "dry_run"}
        assert db.query(JobRun).filter_by(status="failed").one().error_type == "ValueError"
        health = {r["job"]: r for r in jobs.job_health(db)}
        assert health["filing-scan"]["last_success"] is None
        assert health["filing-scan"]["stale"] is True


@pytest.mark.parametrize("counter", [
    "source_errors", "errors", "extract_errors", "alerts_failed", "digests_failed", "failed",
    "commit_failed", "generation_failed", "missing_urls", "unsupported_form", "company_not_found",
])
def test_returned_failure_counters_fail_the_execution(sessions, counter):
    with pytest.raises(jobs.JobRunFailed):
        with jobs.track_job("filing-scan") as attempt:
            attempt.record({counter: 1})
    with sessions() as db:
        row = db.query(JobRun).one()
        assert row.status == "failed" and row.counters[counter] == 1


def test_last_success_is_independent_of_latest_attempt_and_missing_jobs(sessions):
    now = utcnow()
    with sessions() as db:
        db.add_all([
            JobRun(id="a", job_name="filing-scan", started_at=now-timedelta(hours=4),
                   finished_at=now-timedelta(hours=3), status="succeeded"),
            JobRun(id="b", job_name="filing-scan", started_at=now-timedelta(hours=1),
                   finished_at=now, status="failed"),
            JobRun(id="c", job_name="pregenerate", started_at=now-timedelta(days=15), status="running"),
        ])
        db.commit()
        report = {r["job"]: r for r in jobs.job_health(db, now=now)}
    assert set(report) == {"pregenerate", "filing-scan", "filing-digest", "backfill-facts",
                           "earnings-calendar-refresh", "earnings-day-alerts", "notable-filings",
                           "data-quality-report"}
    assert report["filing-scan"]["stale"] and report["filing-scan"]["latest_status"] == "failed"
    assert report["filing-scan"]["last_success"] == jobs.iso_z(now-timedelta(hours=3))
    assert report["notable-filings"]["latest_status"] == "never_observed"
    assert report["pregenerate"]["last_success"] is None
    assert report["notable-filings"]["cadence_hours"] == 14


@pytest.mark.parametrize("mode", ["scan", "digest", "calendar", "alerts", "notable", "facts", "pregenerate"])
def test_every_scheduled_entrypoint_records_swallowed_failures(sessions, monkeypatch, mode):
    from scripts import filing_scan, earnings_calendar_job, notable_filings_job, backfill_facts, pregenerate_examples
    from app.services import filing_scan_service, earnings_calendar_service, earnings_alert_service
    from app.services import notable_filings_service, facts_service
    stats = {"errors": 1}
    structured = SimpleNamespace(as_dict=lambda: stats)
    if mode in ("scan", "digest"):
        service = "run_daily_digest" if mode == "digest" else "run_filing_scan"
        monkeypatch.setattr(filing_scan_service, service, AsyncMock(return_value=stats))
        def run():
            return asyncio.run(filing_scan._main(digest=mode == "digest", dry_run=False, cadence_minutes=60))
        expected = "filing-digest" if mode == "digest" else "filing-scan"
    elif mode in ("calendar", "alerts"):
        if mode == "alerts":
            monkeypatch.setattr(earnings_alert_service, "send_earnings_day_alerts", AsyncMock(return_value=stats))
        else:
            monkeypatch.setattr(earnings_calendar_service, "run_refresh", AsyncMock(return_value=structured))
        def run():
            return asyncio.run(earnings_calendar_job._main(alerts=mode == "alerts"))
        expected = "earnings-day-alerts" if mode == "alerts" else "earnings-calendar-refresh"
    elif mode == "notable":
        monkeypatch.setattr(notable_filings_service, "run_scan", AsyncMock(return_value=structured))
        def run():
            return asyncio.run(notable_filings_job._main(days=None))
        expected = "notable-filings"
    elif mode == "facts":
        monkeypatch.setattr(facts_service, "backfill_facts", lambda *a, **kw: stats)
        def run():
            return backfill_facts._main(only_unprocessed=True, limit=None)
        expected = "backfill-facts"
    else:
        monkeypatch.setattr(pregenerate_examples, "pregenerate_for_ticker", AsyncMock(return_value={"status": "generation_failed"}))
        def run():
            return asyncio.run(pregenerate_examples.main(["AAPL"]))
        expected = "pregenerate"
    with pytest.raises(jobs.JobRunFailed):
        run()
    with sessions() as db:
        row = db.query(JobRun).one()
        assert row.job_name == expected and row.status == "failed"



@pytest.mark.parametrize("digest", [False, True], ids=["scan", "digest"])
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry-run", "normal"])
def test_filing_cli_rejects_dry_run_before_application_work(monkeypatch, digest, dry_run):
    from app.services import filing_scan_service

    db = MagicMock()
    factory = MagicMock(return_value=db)
    tracker = MagicMock()
    attempt = tracker.return_value.__enter__.return_value
    stats = {"digests_sent": 1} if digest else {"companies_scanned": 1}
    scan = AsyncMock(return_value=stats)
    daily_digest = AsyncMock(return_value=stats)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(jobs, "track_job", tracker)
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", scan)
    monkeypatch.setattr(filing_scan_service, "run_daily_digest", daily_digest)
    argv = ["filing_scan.py", "--cadence-minutes", "17"]
    if digest:
        argv.append("--digest")
    if dry_run:
        argv.append("--dry-run")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(sys, "path", list(sys.path))
    app_imports = []
    original_import = builtins.__import__

    def observe_import(name, *args, **kwargs):
        if name == "app" or name.startswith("app."):
            app_imports.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", observe_import)
    exit_code = None
    try:
        runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/filing_scan.py"),
                       run_name="__main__")
    except SystemExit as exc:
        exit_code = exc.code

    if dry_run:
        assert app_imports == [], "Dry-run must reject before importing the application"
        factory.assert_not_called()
        tracker.assert_not_called()
        scan.assert_not_called()
        daily_digest.assert_not_called()
        assert isinstance(exit_code, str) and "Safe preview is unavailable" in exit_code
    else:
        assert exit_code is None
        assert app_imports  # The control actually reached normal application initialization.
        factory.assert_called_once_with()
        tracker.assert_called_once_with("filing-digest" if digest else "filing-scan", dry_run=False)
        if digest:
            daily_digest.assert_awaited_once_with(db, send_digest=None)
            scan.assert_not_called()
        else:
            scan.assert_awaited_once_with(db, send_alert=None, cadence_minutes=17)
            daily_digest.assert_not_called()
        attempt.record.assert_called_once_with(stats)
        db.close.assert_called_once_with()


def test_provider_exceptions_are_counted_by_services(sessions, monkeypatch):
    from app.services import earnings_calendar_service as calendar, notable_filings_service as notable
    from app.services import filing_scan_service as scan
    failure = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    with sessions() as db:
        c = Company(cik="2", ticker="B", name="B")
        u = User(email="job@example.test", hashed_password="unused")
        db.add_all([c, u])
        db.commit()
        db.add(Watchlist(user_id=u.id, company_id=c.id))
        db.commit()
        result = asyncio.run(scan.run_filing_scan(db, fetch_filings=failure))
        assert result["source_errors"] == 1
        monkeypatch.setattr(calendar, "_sweep_edgar_2_02", failure)
        stats = asyncio.run(calendar.run_refresh(db, av_client=SimpleNamespace(fetch_earnings_calendar=failure)))
        assert stats.source_errors == 2 and stats.as_dict()["source_errors"] == 2
        monkeypatch.setattr(notable, "_paged_search", failure)
        stats = asyncio.run(notable.run_scan(db, days=0))
        assert stats.source_errors > 0 and stats.as_dict()["source_errors"] == stats.source_errors


def test_universe_coverage_uses_members_and_summaryless_definition(sessions, monkeypatch):
    monkeypatch.setattr(index_membership_service, "member_tickers", lambda: frozenset({"A", "BRK.B", "MISSING"}))
    monkeypatch.setattr(index_membership_service, "universe_generated_on", lambda: "2026-07-07")
    with sessions() as db:
        companies = [Company(cik=str(i), ticker=t, name=t) for i, t in enumerate(["A", "BRK-B", "OUTSIDE"], 10)]
        db.add_all(companies)
        db.commit()
        for i, c in enumerate(companies):
            filing = Filing(company_id=c.id, accession_number=str(i), filing_type="10-K",
                            filing_date=date(2026, 1, 1), sec_url="https://x/", document_url="https://x/a.htm")
            db.add(filing)
            db.flush()
            if c.ticker != "A":
                db.add(Summary(filing_id=filing.id, raw_summary={"quality": {"tier": "partial"}}))
        db.commit()
        coverage = data_quality_service.universe_coverage(db, today=date(2026, 9, 5))
        assert coverage == {"universe_members": 3, "companies_present": 2, "companies_with_summary": 1,
                            "company_coverage_pct": 66.67, "summary_coverage_pct": 33.33,
                            "stored_filings": 2, "summaryless_filings": 1, "stub_ratio_pct": 50.0,
                            "generated_on": "2026-07-07", "universe_age_days": 60}
        report = {"universe_coverage": coverage, "job_health": jobs.job_health(db)}
        html, text = email_service.render_data_quality_report(report)
        for rendered in (html, text):
            assert "33.33" in rendered and "never observed" in rendered and "STALE" in rendered
            assert "filing-digest" in rendered and "universe age days" in rendered


def test_invalid_universe_is_unavailable(sessions, monkeypatch, tmp_path):
    source = tmp_path / "index.json"
    source.write_text('{"generated_on":"not-a-date"}')
    monkeypatch.setattr(index_membership_service, "_DATA_PATH", source)
    monkeypatch.setattr(index_membership_service, "member_tickers", lambda: frozenset())
    with sessions() as db:
        result = data_quality_service.universe_coverage(db)
    assert result["summary_coverage_pct"] is None and result["stub_ratio_pct"] is None
    assert result["generated_on"] is None and result["universe_age_days"] is None


def test_sic_fetch_uses_limiter_and_circuit_boundary(monkeypatch):
    from app.services.edgar import company_sic
    seen = []
    async def limited(call):
        seen.append("limiter")
        return await call()
    async def guarded(call):
        seen.append("circuit")
        return call()
    monkeypatch.setattr(company_sic.sec_rate_limiter, "execute", limited)
    monkeypatch.setattr(company_sic, "run_with_circuit_breaker", guarded)
    monkeypatch.setattr(company_sic, "EdgarCompany", lambda cik: SimpleNamespace(sic=6021, industry="Banks"))
    assert company_sic.fetch_company_sic_sync("19617") == ("6021", "Banks")
    assert seen == ["limiter", "circuit"]


def test_statement_default_and_explicit_override():
    from app.config import Settings
    assert Settings.model_fields["USE_STATEMENT_FINANCIALS"].default is True
    assert Settings(USE_STATEMENT_FINANCIALS=False).USE_STATEMENT_FINANCIALS is False


def test_new_table_migration_is_project_specific():
    migration = Path(__file__).resolve().parents[2] / "migrations/20260905_earningsnerd_job_runs.sql"
    sql = migration.read_text()
    assert "CREATE TABLE IF NOT EXISTS earningsnerd_job_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS job_runs" not in sql
    assert "pg_indexes" in sql and "ix_earningsnerd_job_runs_job_started" in sql


def test_report_script_emits_new_sections_and_uses_separate_identity(sessions, monkeypatch, capsys):
    import json
    from scripts import data_quality_report
    monkeypatch.setattr(data_quality_service, "ticker_integrity", AsyncMock(return_value={"mismatches": [], "not_in_file": []}))
    asyncio.run(data_quality_report._main(dry_run=True))
    report = json.loads(capsys.readouterr().out)
    assert "summary_coverage_pct" in report["universe_coverage"]
    assert any(r["job"] == "filing-digest" and r["latest_status"] == "never_observed" for r in report["job_health"])
    with sessions() as db:
        row = db.query(JobRun).one()
        assert row.job_name == "data-quality-report" and row.status == "dry_run"


def test_ops_describe_statement_default_matches_settings():
    from app.config import Settings
    workflow = Path(__file__).resolve().parents[3] / ".github/workflows/ops.yml"
    default = Settings.model_fields["USE_STATEMENT_FINANCIALS"].default
    assert f"Settings default applies ({default})" in workflow.read_text()


def test_notable_midpagination_failure_is_not_success():
    from app.services import notable_filings_service as notable
    hit = SimpleNamespace(accession_no="one")
    client = SimpleNamespace(search=AsyncMock(side_effect=[
        SimpleNamespace(hits=[hit], total=2), RuntimeError("second page unavailable"),
    ]))
    stats = notable.ScanStats()
    collected = []
    asyncio.run(notable._paged_search(client, stats, set(), collected, query="earnings",
                                     forms="8-K", start="2026-09-01", end="2026-09-05", max_pages=2))
    assert collected == [hit] and stats.source_errors == 1
    assert stats.truncated_queries == ["8-K:earnings@1"]


@pytest.mark.parametrize("body", ['{"Information":"rate limited"}', 'bad,columns\n1,2', "http_failure"])
def test_alpha_vantage_strict_ingest_exposes_provider_failure(monkeypatch, body):
    import httpx
    from app.integrations.alpha_vantage import AlphaVantageClient
    client = AlphaVantageClient()
    client._api_key = "fixture-key"
    response = httpx.Response(503 if body == "http_failure" else 200, text=body,
                              request=httpx.Request("GET", "https://example.test"))
    transport = AsyncMock()
    transport.__aenter__.return_value.get.return_value = response
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: transport)
    assert asyncio.run(client.fetch_earnings_calendar()) == []
    with pytest.raises(httpx.HTTPStatusError if body == "http_failure" else ValueError):
        asyncio.run(client.fetch_earnings_calendar(raise_on_error=True))


def test_calendar_opts_into_provider_error_visibility(sessions, monkeypatch):
    from app.integrations.alpha_vantage import alpha_vantage_client
    from app.services import earnings_calendar_service as calendar
    fetch = AsyncMock(side_effect=RuntimeError("provider failed"))
    monkeypatch.setattr(alpha_vantage_client, "fetch_earnings_calendar", fetch)
    monkeypatch.setattr(calendar, "_sweep_edgar_2_02", AsyncMock(return_value=[]))
    with sessions() as db:
        stats = asyncio.run(calendar.run_refresh(db))
    fetch.assert_awaited_once_with(raise_on_error=True)
    assert stats.source_errors == 1
