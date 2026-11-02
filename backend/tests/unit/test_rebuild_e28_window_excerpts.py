"""E28 (b)'s rebuild selects the window's regex-excerpt filings and rebuilds each in place, reporting counts only.

``scripts/rebuild_e28_window_excerpts.py`` reads its window and builder openings as ``ops/excerpts/source_cohort.sql``
does (the excerpt-cohort receipt sized the cohort with that SQL), selects the rows created or last written in the
window, so a regeneration that kept a row's regex excerpt cannot drop it, refuses any count but the reviewed one,
and rebuilds through ``generate_summary_background(filing_id, None, force_regenerate=True, rebuild_excerpt=True)``,
the forced call ``precompute_one`` makes. It deletes and writes nothing itself: the orchestrator keeps or replaces
each summary in place. Only a Cloud Run task's first attempt runs: a retry, which a failed or killed attempt sets
off, reads and writes nothing. Its lines hold counts, one as each filing finishes and the run's last, never a
filing id, accession, ticker or error text. SQLite runs the selection and the outcome classes; the orchestrator is
faked here. Retire this test and the script with source_cohort.sql, whose openings and marks it reads.
"""
from __future__ import annotations

import argparse
import ast
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
UNCLASSIFIED = "UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D.C. 20549 FORM 10-Q"
IN_WINDOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
BEFORE = datetime(2026, 9, 20, tzinfo=timezone.utc)
AFTER = datetime(2026, 10, 20, tzinfo=timezone.utc)
START, END = rebuild.WINDOW_START, rebuild.WINDOW_END


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
    """The receipt's shapes, both window edges, and every row the selection must leave alone. Selected rows are
    seeded first, so their ids ascend in this order."""
    selected = [
        _seed(sessions, "10-Q", TARGETED, created=IN_WINDOW),
        _seed(sessions, "10-K", TARGETED, created=IN_WINDOW, saved=True),  # a bookmark does not exclude it
        _seed(sessions, "10-K/A", RECOVERED, created=IN_WINDOW),
        _seed(sessions, " 10-q ", TARGETED, created=IN_WINDOW),  # the SQL reads upper(btrim(form))
        _seed(sessions, "10-Q", TARGETED, created=BEFORE, updated=IN_WINDOW),  # the receipt's one, by last write
        # Regenerated since with its stored regex excerpt reused (Pro Regenerate, the stale drain): still selected.
        _seed(sessions, "10-Q", TARGETED, created=IN_WINDOW, updated=AFTER),
        _seed(sessions, "10-Q", TARGETED, created=START),  # the window's first instant is in it
    ]
    _seed(sessions, "10-Q", NATIVE, created=IN_WINDOW)  # native: not the regex builders'
    _seed(sessions, "8-K", RECOVERED, created=IN_WINDOW)  # a form with no native sections
    _seed(sessions, "10-Q", TARGETED, created=BEFORE)  # before the window
    _seed(sessions, "10-Q", TARGETED, created=AFTER)  # after it
    _seed(sessions, "10-Q", TARGETED, created=END)  # its end is not in it
    _seed(sessions, "10-Q", TARGETED, created=BEFORE, updated=END)  # last written at the end: not in it either
    _seed(sessions, "10-Q", TARGETED, created=BEFORE, updated=AFTER)  # written in neither (the documented gap)
    _seed(sessions, "10-Q", None, created=IN_WINDOW)  # no excerpt stored
    return selected


def _run(sessions, *, apply, generate=None, emit=None):
    reports = []
    code = rebuild.run(argparse.Namespace(apply=apply), (emit or reports.append),
                       session_factory=sessions, generate=generate or _never, env={})
    return code, reports


async def _never(*_args, **_kwargs):
    raise AssertionError("no rebuild may run")


def _replace(sessions, filing_id, excerpt):
    """What a replacing run commits: the summary updated in place and the rebuilt excerpt stored with it."""
    with sessions() as db:
        db.query(Summary).filter(Summary.filing_id == filing_id).update(
            {"updated_at": datetime(2026, 11, 2, tzinfo=timezone.utc), "business_overview": "rebuilt"})
        db.query(FilingContentCache).filter(FilingContentCache.filing_id == filing_id).update(
            {"critical_excerpt": excerpt})
        db.commit()


# Every key a line may carry: counts, the window's two marks and two flags, never a filing id or text.
REPORT_KEYS = {"mode", "window", "expected", "cohort", "created_in_window", "by_form", "by_builder", "with_summary",
               "durable_generation"}
PROGRESS_KEYS = {"mode", "rebuilt", "of", "outcome"}


def test_the_window_and_the_openings_are_the_cohort_sqls():
    sql = SQL.read_text()
    assert "timestamptz '2026-10-04 09:29:00+00' AS last_native_report" in sql
    assert "timestamptz '2026-10-16 04:10:00+00' AS fix_deployed" in sql
    assert rebuild.WINDOW_START == datetime(2026, 10, 4, 9, 29, tzinfo=timezone.utc)
    assert rebuild.WINDOW_END == datetime(2026, 10, 16, 4, 10, tzinfo=timezone.utc)
    assert "WHEN substr(c.critical_excerpt, 1, 52) = E'\\n\\n' || repeat('=', 50) THEN 'regex_targeted'" in sql
    assert len(rebuild.REGEX_TARGETED_OPENING) == 52
    recovered = [text.replace("''", "'") + "\n" for text in re.findall(r"LIKE '((?:[^']|'')*)' \|\| E'\\n%'\n", sql)]
    assert sorted(recovered) == sorted(rebuild.REGEX_RECOVERED_OPENINGS)
    native = [text.replace("''", "'") + "\n" for text in re.findall(r"^\s+'((?:[^']|'')*)' \|\| E'\\n%',?$", sql, re.M)]
    assert sorted(native) == sorted(rebuild.NATIVE_OPENINGS)
    # The receipt buckets each row by its created_at and by its last write, the two readings the selection takes.
    assert "COALESCE(c.updated_at, c.created_at) AS last_write" in sql
    assert "WHEN o.created_at < m.last_native_report" in sql and "WHEN o.last_write < m.last_native_report" in sql


def test_the_native_openings_are_the_assemblers_labels():
    from app.services.ai.extraction import _ExtractionMixin

    labels = {label for layout in _ExtractionMixin._SECTION_LAYOUT.values() for _, label, _ in layout}
    assert set(rebuild.NATIVE_OPENINGS) == {f"{label}:\n" for label in labels}
    assert len(rebuild.NATIVE_OPENINGS) == len(set(rebuild.NATIVE_OPENINGS))


@pytest.mark.parametrize("opening, expected", [
    (None, "none"), ("", "none"), (TARGETED, "regex_targeted"), (RECOVERED, "regex_recovered"),
    ("RISK & NARRATIVE CONTEXT (recovered from filing):\nrisk", "regex_recovered"), (NATIVE, "native"),
    ("ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA:\nstatements", "native"),
    ("ITEM 3.D - RISK FACTORS:\nrisks", "native"), ("ITEM 2 - MANAGEMENT'S DISCUSSION AND ANALYSIS no colon", "unclassified"),
    (UNCLASSIFIED, "unclassified"), ("\n\n" + "=" * 49 + "-", "unclassified"),
    ("FINANCIAL & MD&A CONTEXT (recovered from filing): no newline", "unclassified"),
])
def test_the_builder_reads_an_excerpts_opening_as_the_sql_does(opening, expected):
    assert rebuild.builder(opening) == expected


def test_the_selection_is_the_windows_regex_built_10k_and_10q_rows_created_or_last_written_in_it(sessions):
    selected = _window_cohort(sessions)
    with sessions() as db:
        cohort = rebuild.select_cohort(db)
    assert [filing_id for filing_id, _, _, _ in cohort] == selected
    assert {form for _, form, _, _ in cohort} == {"10-Q", "10-K", "10-K/A"}
    assert [created_in for *_, created_in in cohort] == [True, True, True, True, False, True, True]


def test_the_dry_run_reports_counts_and_writes_nothing(sessions, monkeypatch):
    _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 7)
    code, [report] = _run(sessions, apply=False)
    assert code == 0
    assert report == {"mode": "dry_run", "window": ["2026-10-04T09:29:00Z", "2026-10-16T04:10:00Z"],
                      "expected": 7, "cohort": 7, "created_in_window": 6,
                      "by_form": {"10-K": 1, "10-K/A": 1, "10-Q": 5},
                      "by_builder": {"regex_recovered": 1, "regex_targeted": 6}, "with_summary": 7,
                      "durable_generation": False}


@pytest.mark.parametrize("apply", [False, True])
def test_any_other_count_than_the_reviewed_one_is_refused(sessions, apply):
    _window_cohort(sessions)  # 7 rows, against the reviewed 15
    code, [report] = _run(sessions, apply=apply)
    assert code == 2 and report["cohort"] == 7 and report["expected"] == 15
    assert report["refused"] == "cohort_differs_from_expected" and "outcomes" not in report


def test_the_apply_refuses_while_durable_generation_is_on(sessions, monkeypatch):
    from app.config import settings
    _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 7)
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    code, [report] = _run(sessions, apply=True)
    assert code == 2 and report["refused"] == "durable_generation_enabled" and report["durable_generation"] is True


def test_the_apply_rebuilds_each_filing_in_place_and_reports_outcome_classes_only(sessions, monkeypatch):
    selected = _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 7)
    calls = []
    plan = dict(zip(selected, ["native", "regex", "unclassified", "cleared", "kept", "error", "native"]))

    async def orchestrator(filing_id, user_id, **flags):
        calls.append((filing_id, user_id, flags))
        what = plan[filing_id]
        if what == "error":
            return {"type": "error"}
        if what != "kept":
            _replace(sessions, filing_id, {"native": NATIVE, "regex": TARGETED, "unclassified": UNCLASSIFIED,
                                           "cleared": None}[what])
        return {"type": "complete"}

    before = {}
    with sessions() as db:
        for filing_id in selected:
            before[filing_id] = db.query(Summary.id).filter(Summary.filing_id == filing_id).scalar()
    code, reports = _run(sessions, apply=True, generate=orchestrator)
    *progress, report = reports
    assert code == 1, "a failed rebuild fails the run"
    assert calls == [(filing_id, None, {"force_regenerate": True, "rebuild_excerpt": True}) for filing_id in selected]
    classes = ["replaced", "replaced_regex", "replaced_unclassified", "replaced_without_excerpt", "kept", "failed",
               "replaced"]
    assert progress == [{"mode": "apply", "rebuilt": done, "of": 7, "outcome": outcome}
                        for done, outcome in enumerate(classes, start=1)], "one counts-only line as each finishes"
    assert report["outcomes"] == {"replaced": 2, "replaced_regex": 1, "replaced_unclassified": 1,
                                  "replaced_without_excerpt": 1, "kept": 1, "failed": 1}
    assert set(report) == REPORT_KEYS | {"outcomes"}, "the apply line adds the outcome counts and nothing else"
    with sessions() as db:
        for filing_id in selected:  # every summary survives under its id, the bookmarked one included
            assert db.query(Summary.id).filter(Summary.filing_id == filing_id).scalar() == before[filing_id]
        assert db.query(SavedSummary).count() == 1


def test_an_exception_counts_as_failed_and_its_text_is_withheld(sessions, monkeypatch):
    selected = _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 7)
    secret = "accession e28b-0 at https://sec.example/e28b-0.htm"

    async def orchestrator(*_args, **_kwargs):
        raise RuntimeError(secret)

    lines = []
    code = rebuild.run(argparse.Namespace(apply=True), lambda report: lines.append(json.dumps(report)),
                       session_factory=sessions, generate=orchestrator, env={})
    *progress, report = [json.loads(line) for line in lines]
    assert code == 1 and report["outcomes"]["failed"] == len(selected) == len(progress)
    assert set(report) == REPORT_KEYS | {"outcomes"} and all(set(line) == PROGRESS_KEYS for line in progress)
    assert not any(secret in line or "e28b-" in line for line in lines)


def test_a_failed_read_of_a_runs_result_counts_as_failed_and_the_run_goes_on(sessions, monkeypatch):
    """Reading the summary's stamp or the stored excerpt sits inside the failure class too: a database error there
    fails that filing, withheld, and the next filing still runs."""
    selected = _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 7)
    secret = "SELECT ... WHERE filing_id = e28b-2"
    real_opening = rebuild._stored_opening

    def opening(session_factory, filing_id):
        if filing_id == selected[2]:
            raise RuntimeError(secret)
        return real_opening(session_factory, filing_id)

    monkeypatch.setattr(rebuild, "_stored_opening", opening)

    async def orchestrator(filing_id, _user_id, **_flags):
        _replace(sessions, filing_id, NATIVE)
        return {"type": "complete"}

    lines = []
    code = rebuild.run(argparse.Namespace(apply=True), lambda report: lines.append(json.dumps(report)),
                       session_factory=sessions, generate=orchestrator, env={})
    report = json.loads(lines[-1])
    assert code == 1 and report["outcomes"]["failed"] == 1 and report["outcomes"]["replaced"] == 6
    assert not any(secret in line or "e28b-" in line for line in lines)


def test_main_prints_one_counts_only_line(sessions, monkeypatch, capsys):
    _window_cohort(sessions)
    monkeypatch.setattr(rebuild, "EXPECTED_COHORT", 7)
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
    """A failed first attempt (a refusal, a failed rebuild, an out-of-memory kill, a timeout) makes Cloud Run retry
    the task. The retry must not re-run the paid rebuilds under the same approval: it refuses before it opens a
    session."""
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


def test_the_entry_point_reads_the_tasks_own_attempt(monkeypatch, capsys):
    """__main__ calls main() with no environment of its own, so the guard must read the process's: a Cloud Run
    retry refuses through the defaults alone."""
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "1")
    assert rebuild.main(["--apply"]) == 2
    assert capsys.readouterr().out == 'E28_REBUILD {"expected": 15, "mode": "apply", "refused": "retry_attempt"}\n'


def test_the_entry_block_starts_as_the_pregenerate_jobs_scripts_do():
    """The job's spend reads as the job's, its INFO lines reach Cloud Run's logs, and Redis is skipped before any
    app import builds the settings (no app import at module level, so the entry block's comes first)."""
    tree = ast.parse(SCRIPT.read_text())
    top_imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not any(isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "app"
                   or isinstance(node, ast.Import) and any(alias.name.split(".")[0] == "app" for alias in node.names)
                   for node in top_imports), "an app import at module level would build the settings first"
    [entry] = [node for node in tree.body if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'"]
    assert [ast.unparse(statement) for statement in entry.body] == [
        "import logging",
        "os.environ.setdefault('SKIP_REDIS_INIT', 'true')",
        "from app.services import ai_metrics",
        "ai_metrics.set_trigger('job')",
        "logging.basicConfig(level=logging.INFO)",
        "sys.exit(main())",
    ]
