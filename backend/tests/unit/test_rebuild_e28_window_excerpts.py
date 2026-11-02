"""E28 (b)'s rebuild selects the window's regex-excerpt filings and rebuilds each in place, reporting counts only.

``scripts/rebuild_e28_window_excerpts.py`` reads its window and builder openings as ``ops/excerpts/source_cohort.sql``
does (the excerpt-cohort receipt sized the cohort with that SQL), selects by last write, refuses any count but the
reviewed one, and rebuilds through ``generate_summary_background(filing_id, None, force_regenerate=True,
rebuild_excerpt=True)``, the forced call ``precompute_one`` makes. It deletes and writes nothing itself: the
orchestrator keeps or replaces each summary in place. Only a Cloud Run task's first attempt runs: a retry, which a
failed attempt sets off, reads and writes nothing. Its one output line holds counts, never a filing id, accession,
ticker or error text. SQLite runs the selection and the outcome classes; the orchestrator is faked here.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Company, Filing, FilingContentCache, SavedSummary, Summary

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "backend" / "scripts" / "rebuild_e28_window_excerpts.py"
SQL = ROOT / "ops" / "excerpts" / "source_cohort.sql"
_spec = importlib.util.spec_from_file_location("rebuild_e28_window_excerpts", SCRIPT)
rebuild = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rebuild)

TARGETED = "\n\n" + "=" * 50 + "ITEM 7 - MD&A\nregex section text"
RECOVERED = "FINANCIAL & MD&A CONTEXT (recovered from filing):\nwindow text"
NATIVE = "ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS:\nnative section text"
IN_WINDOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
BEFORE = datetime(2026, 9, 20, tzinfo=timezone.utc)
AFTER = datetime(2026, 10, 20, tzinfo=timezone.utc)


@pytest.fixture
def sessions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    engine.dispose()


def _seed(sessions, form, excerpt, *, created, updated=None, summary=True, saved=False) -> int:
    with sessions() as db:
        company = db.query(Company).first()
        if company is None:
            company = Company(cik="320193", ticker="E28B", name="Window Co")
            db.add(company)
            db.flush()
        n = db.query(Filing).count()
        filing = Filing(company_id=company.id, accession_number=f"e28b-{n}", filing_type=form,
                        filing_date=datetime(2026, 8, 1, tzinfo=timezone.utc) + timedelta(days=n),
                        document_url=f"https://sec.example/e28b-{n}.htm", sec_url=f"https://sec.example/e28b-{n}/")
        db.add(filing)
        db.flush()
        db.add(FilingContentCache(filing_id=filing.id, critical_excerpt=excerpt, created_at=created, updated_at=updated))
        if summary:
            row = Summary(filing_id=filing.id, business_overview="regex-grounded summary")
            db.add(row)
            db.flush()
            if saved:
                db.add(SavedSummary(user_id=1, summary_id=row.id))
        db.commit()
        return filing.id


def _window_cohort(sessions):
    """The 15-shaped mix the receipt saw, plus every row the selection must leave alone."""
    selected = [
        _seed(sessions, "10-Q", TARGETED, created=IN_WINDOW),
        _seed(sessions, "10-K", TARGETED, created=IN_WINDOW, saved=True),  # a bookmark does not exclude it
        _seed(sessions, "10-K/A", RECOVERED, created=IN_WINDOW),
        _seed(sessions, " 10-q ", TARGETED, created=IN_WINDOW),  # the SQL reads upper(btrim(form))
        _seed(sessions, "10-Q", TARGETED, created=BEFORE, updated=IN_WINDOW),  # by last write, like the receipt
    ]
    _seed(sessions, "10-Q", NATIVE, created=IN_WINDOW)  # native: not the regex builders'
    _seed(sessions, "8-K", RECOVERED, created=IN_WINDOW)  # a form with no native sections
    _seed(sessions, "10-Q", TARGETED, created=BEFORE)  # before the window
    _seed(sessions, "10-Q", TARGETED, created=AFTER)  # after it
    _seed(sessions, "10-Q", TARGETED, created=IN_WINDOW, updated=AFTER)  # rewritten since: last write after
    _seed(sessions, "10-Q", None, created=IN_WINDOW)  # no excerpt stored
    return selected


def _run(sessions, *, apply, generate=None, emit=None):
    reports = []
    code = rebuild.run(argparse.Namespace(apply=apply), (emit or reports.append),
                       session_factory=sessions, generate=generate or _never, env={})
    return code, reports


async def _never(*_args, **_kwargs):
    raise AssertionError("no rebuild may run")


# Every key the one line may carry: counts, the window's two marks and two flags, never a filing id or text.
REPORT_KEYS = {"mode", "window", "expected", "cohort", "by_form", "by_builder", "with_summary", "durable_generation"}


def test_the_window_and_the_regex_openings_are_the_cohort_sqls():
    sql = SQL.read_text()
    assert "timestamptz '2026-10-04 09:29:00+00' AS last_native_report" in sql
    assert "timestamptz '2026-10-16 04:10:00+00' AS fix_deployed" in sql
    assert rebuild.WINDOW_START == datetime(2026, 10, 4, 9, 29, tzinfo=timezone.utc)
    assert rebuild.WINDOW_END == datetime(2026, 10, 16, 4, 10, tzinfo=timezone.utc)
    assert "WHEN substr(c.critical_excerpt, 1, 52) = E'\\n\\n' || repeat('=', 50) THEN 'regex_targeted'" in sql
    assert len(rebuild.REGEX_TARGETED_OPENING) == 52
    recovered = [text.replace("''", "'") + "\n" for text in re.findall(r"LIKE '((?:[^']|'')*)' \|\| E'\\n%'\n", sql)]
    assert sorted(recovered) == sorted(rebuild.REGEX_RECOVERED_OPENINGS)
    assert "COALESCE(c.updated_at, c.created_at) AS last_write" in sql, "the cohort counts by last write"


@pytest.mark.parametrize("opening, expected", [
    (None, "none"), ("", "none"), (TARGETED, "regex_targeted"), (RECOVERED, "regex_recovered"),
    ("RISK & NARRATIVE CONTEXT (recovered from filing):\nrisk", "regex_recovered"), (NATIVE, "other"),
    ("\n\n" + "=" * 49 + "-", "other"), ("FINANCIAL & MD&A CONTEXT (recovered from filing): no newline", "other"),
])
def test_the_builder_reads_an_excerpts_opening_as_the_sql_does(opening, expected):
    assert rebuild.builder(opening) == expected


def test_the_selection_is_the_windows_regex_built_10k_and_10q_rows_by_last_write(sessions):
    selected = _window_cohort(sessions)
    with sessions() as db:
        cohort = rebuild.select_cohort(db)
    assert [filing_id for filing_id, _, _ in cohort] == sorted(selected)
    assert {form for _, form, _ in cohort} == {"10-Q", "10-K", "10-K/A"}


def test_the_dry_run_reports_counts_and_writes_nothing(sessions, monkeypatch):
    _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 5)
    code, [report] = _run(sessions, apply=False)
    assert code == 0
    assert report == {"mode": "dry_run", "window": ["2026-10-04T09:29:00+00:00", "2026-10-16T04:10:00+00:00"],
                      "expected": 5, "cohort": 5, "by_form": {"10-K": 1, "10-K/A": 1, "10-Q": 3},
                      "by_builder": {"regex_recovered": 1, "regex_targeted": 4}, "with_summary": 5,
                      "durable_generation": False}


@pytest.mark.parametrize("apply", [False, True])
def test_any_other_count_than_the_reviewed_one_is_refused(sessions, apply):
    _window_cohort(sessions)  # 5 rows, against the reviewed 15
    code, [report] = _run(sessions, apply=apply)
    assert code == 2 and report["cohort"] == 5 and report["expected"] == 15
    assert report["refused"] == "cohort_differs_from_expected" and "outcomes" not in report


def test_the_apply_refuses_while_durable_generation_is_on(sessions, monkeypatch):
    from app.config import settings
    _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 5)
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    code, [report] = _run(sessions, apply=True)
    assert code == 2 and report["refused"] == "durable_generation_enabled" and report["durable_generation"] is True


def test_the_apply_rebuilds_each_filing_in_place_and_reports_outcome_classes_only(sessions, monkeypatch):
    selected = _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 5)
    calls = []
    plan = dict(zip(selected, ["native", "regex", "cleared", "kept", "error"]))

    async def orchestrator(filing_id, user_id, **flags):
        calls.append((filing_id, user_id, flags))
        what = plan[filing_id]
        if what == "error":
            return {"type": "error"}
        if what != "kept":
            with sessions() as db:
                db.query(Summary).filter(Summary.filing_id == filing_id).update(
                    {"updated_at": datetime(2026, 11, 2, tzinfo=timezone.utc), "business_overview": "rebuilt"})
                excerpt = {"native": NATIVE, "regex": TARGETED, "cleared": None}[what]
                db.query(FilingContentCache).filter(FilingContentCache.filing_id == filing_id).update(
                    {"critical_excerpt": excerpt})
                db.commit()
        return {"type": "complete"}

    before = {}
    with sessions() as db:
        for filing_id in selected:
            before[filing_id] = db.query(Summary.id).filter(Summary.filing_id == filing_id).scalar()
    code, [report] = _run(sessions, apply=True, generate=orchestrator)
    assert code == 1, "a failed rebuild fails the run"
    assert calls == [(filing_id, None, {"force_regenerate": True, "rebuild_excerpt": True}) for filing_id in sorted(selected)]
    assert report["outcomes"] == {"replaced": 1, "replaced_regex": 1, "replaced_without_excerpt": 1, "kept": 1, "failed": 1}
    assert set(report) == REPORT_KEYS | {"outcomes"}, "the apply line adds the outcome counts and nothing else"
    with sessions() as db:
        for filing_id in selected:  # every summary survives under its id, the bookmarked one included
            assert db.query(Summary.id).filter(Summary.filing_id == filing_id).scalar() == before[filing_id]
        assert db.query(SavedSummary).count() == 1


def test_an_exception_counts_as_failed_and_its_text_is_withheld(sessions, monkeypatch):
    selected = _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 5)
    secret = "accession e28b-0 at https://sec.example/e28b-0.htm"

    async def orchestrator(*_args, **_kwargs):
        raise RuntimeError(secret)

    lines = []
    code = rebuild.run(argparse.Namespace(apply=True), lambda report: lines.append(json.dumps(report)),
                       session_factory=sessions, generate=orchestrator, env={})
    report = json.loads(lines[0])
    assert code == 1 and report["outcomes"]["failed"] == len(selected)
    assert set(report) == REPORT_KEYS | {"outcomes"} and secret not in lines[0] and "e28b-" not in lines[0]


def test_main_prints_one_counts_only_line(sessions, monkeypatch, capsys):
    _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 5)
    real_run = rebuild.run
    monkeypatch.setattr(rebuild, "run", lambda args, emit, env: real_run(args, emit, session_factory=sessions,
                                                                         generate=_never, env=env))
    assert rebuild.main([], env={"CLOUD_RUN_TASK_ATTEMPT": "0"}) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].startswith("E28_REBUILD {")
    report = json.loads(out[0].removeprefix("E28_REBUILD "))
    assert set(report) == REPORT_KEYS
    assert "e28b-" not in out[0] and "E28B" not in out[0], "no accession or ticker"


@pytest.mark.parametrize("attempt, first", [(None, True), ("0", True), ("1", False), ("3", False), ("", False),
                                            ("00", False), ("x", False)])
def test_only_a_tasks_first_attempt_runs(attempt, first):
    env = {} if attempt is None else {"CLOUD_RUN_TASK_ATTEMPT": attempt}
    assert rebuild.first_attempt(env) is first


@pytest.mark.parametrize("apply", [False, True])
def test_a_cloud_run_retry_reads_and_writes_nothing(apply):
    """A failed first attempt (a refusal, a failed rebuild, a timeout) makes Cloud Run retry the task. The retry
    must not re-run the paid rebuilds under the same approval: it refuses before it opens a session."""
    def no_session():
        raise AssertionError("a retry opens no session")

    reports = []
    code = rebuild.run(argparse.Namespace(apply=apply), reports.append, session_factory=no_session, generate=_never,
                       env={"CLOUD_RUN_TASK_ATTEMPT": "1"})
    assert code == 2
    assert reports == [{"mode": "apply" if apply else "dry_run", "expected": 15, "refused": "retry_attempt"}]


def test_main_passes_the_task_attempt_through(monkeypatch, capsys):
    monkeypatch.setattr(rebuild, "run", lambda args, emit, env: (emit({"attempt": env["CLOUD_RUN_TASK_ATTEMPT"]}), 7)[1])
    assert rebuild.main(["--apply"], env={"CLOUD_RUN_TASK_ATTEMPT": "2"}) == 7
    assert capsys.readouterr().out == 'E28_REBUILD {"attempt": "2"}\n'
