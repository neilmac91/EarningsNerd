"""Each pytest process owns a private, PostgreSQL-like SQLite database, and process state set by one
test never reaches the next (gates for the parallel, order-independent suite).

``backend/tests/conftest.py`` points ``DATABASE_URL`` at a fresh temp directory before any app import:
one per session, and one per pytest-xdist worker, because every worker is its own process. Without it
the suite shares the CWD-relative default ``sqlite:///./earningsnerd.db`` (``backend/earningsnerd.db``):
parallel workers, or a second run in the same worktree, read and rewrite one file, and that file
outlives every schema change (lessons/ops-one-test-process-per-worktree.md). Because that database
starts empty, conftest also creates the schema once per process: no test may depend on an earlier
test (or the app lifespan of an earlier ``TestClient``) having created its tables.

EdgarTools' data and cache directories go in that temp directory too, unless set before pytest starts:
by default they live under the home directory, where every run and worker would share the pickled
anchors TOC extraction reuses, and a sandbox's read-only home turns a cache write into an incomplete
TOC (lessons/test-conftest-hermetic-env.md).

The same conftest gives SQLite tables AUTOINCREMENT ids. PostgreSQL never hands out a sequence value
twice; SQLite's default max(rowid)+1 re-issues a deleted test's id to the next test, where a child row
the first test left behind (SQLite here enforces no foreign keys) silently joins the new parent.

Conftest's autouse resets are pinned by probe pairs: one test leaves the state dirty, the next asserts
the clean default (the mock-leak guard instead by a child run that leaks a mock, and the null-device check by a
child run that replaces a stand-in for /dev/null). Under ``-n auto`` and random order a pair can land on two workers or run reversed,
which proves nothing, so ``test_ordered_probes_hold_in_a_fresh_serial_process`` runs every probe in
a fixed order in one fresh process.
"""
import ast
import json
import os
import platform
import datetime
import stat
import subprocess  # nosec B404 - runs this repo's own pytest on fixed nodes of the suite
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Company
from tests.support.summary_stream_harness import CANONICAL_PAYLOAD

BACKEND_DIR = Path(__file__).resolve().parents[2]
_THIS = Path(__file__).relative_to(BACKEND_DIR).as_posix()
_AI_METRICS = "tests/unit/test_ai_metrics.py"
# Order matters: the first two probes must run before any other test in the process; each dirtying
# probe precedes the probe that asserts the reset.
_ORDERED_PROBES = [
    f"{_THIS}::test_probe_the_sdk_request_path_is_warm_before_the_first_test",
    f"{_THIS}::test_probe_reads_the_schema_without_creating_it",
    f"{_THIS}::test_probe_mutates_the_canonical_payload_like_the_pipeline",
    f"{_THIS}::test_probe_next_test_sees_the_pristine_canonical_payload",
    f"{_THIS}::test_probe_exhausts_a_shared_summary_account",
    f"{_THIS}::test_probe_next_test_starts_with_an_empty_summary_limiter",
    f"{_THIS}::test_probe_leaves_delivery_and_lease_rows_behind",
    f"{_THIS}::test_probe_next_test_finds_no_delivery_or_lease_rows",
    f"{_THIS}::test_probe_pins_a_singleton_method_like_monkeypatch",
    f"{_THIS}::test_probe_next_test_finds_no_pinned_singleton_method",
    f"{_AI_METRICS}::test_isolation_probe_leaves_the_trigger_set_like_a_script_entrypoint",
    f"{_AI_METRICS}::test_isolation_next_test_starts_from_the_default_trigger",
]


def test_the_suite_database_is_a_private_temp_file_per_process():
    assert engine.url.get_backend_name() == "sqlite"
    assert make_url(settings.DATABASE_URL).database == engine.url.database
    db = Path(engine.url.database).resolve()
    assert db != BACKEND_DIR / "earningsnerd.db" and BACKEND_DIR not in db.parents, (
        f"the suite database {db} is inside backend/: tests would share one file across runs and workers"
    )
    assert db.parent.parent == Path(tempfile.gettempdir()).resolve(), db
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    assert db.parent.name.startswith(f"earningsnerd-tests-{worker}-"), db
    # mkdtemp creates an owner-only directory; a fixed shared path would not be 0o700.
    assert stat.S_IMODE(db.parent.stat().st_mode) == 0o700, db.parent


def test_probe_the_sdk_request_path_is_warm_before_the_first_test():
    # As a fresh process's first test this passes only if conftest made an SDK request first: a
    # client's first request probes the platform, and nothing else here fills platform's cache.
    # Without the warm-up, whichever test made the process's first request paid ~60 ms inside its
    # own real-time budget.
    assert platform._platform_cache


def test_probe_reads_the_schema_without_creating_it():
    # Creates nothing: as a fresh process's first test it passes only if conftest gave the new
    # database the schema before any test ran.
    with SessionLocal() as db:
        assert db.query(Company).filter(Company.cik == "probe-never-seeded").count() == 0


def test_probe_mutates_the_canonical_payload_like_the_pipeline():
    # The pipeline finalizes the provider's payload in place; with the harness that is this dict.
    CANONICAL_PAYLOAD["raw_summary"]["quality"] = {"tier": "probe"}
    CANONICAL_PAYLOAD["status"] = "probe"


def test_probe_next_test_sees_the_pristine_canonical_payload():
    assert CANONICAL_PAYLOAD["status"] == "complete"
    assert "quality" not in CANONICAL_PAYLOAD["raw_summary"]


def test_probe_exhausts_a_shared_summary_account():
    from app.routers.summaries import SUMMARY_LIMITER

    key = "summary:987654321"
    for _ in range(SUMMARY_LIMITER.limit):
        assert SUMMARY_LIMITER.allow(key)
    assert not SUMMARY_LIMITER.allow(key)


def test_probe_next_test_starts_with_an_empty_summary_limiter():
    from app.routers.summaries import SUMMARY_LIMITER

    assert not SUMMARY_LIMITER._hits


# The tables conftest's _reset_delivery_ownership empties before every test: rows keyed by user and filing
# ids that a scenario deleting its users leaves behind (SQLite here enforces no foreign keys).
_OWNERSHIP_TABLES = ("earningsnerd_delivery_batches", "earningsnerd_delivery_items", "earningsnerd_usage_reservations")
_FILLERS = {int: 1, str: "probe", bool: False, datetime.datetime: datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)}


def test_probe_leaves_delivery_and_lease_rows_behind():
    # One row per table, every required column filled from its type (a new type needs a _FILLERS entry).
    with engine.begin() as conn:
        for name in _OWNERSHIP_TABLES:
            table = Base.metadata.tables[name]
            conn.execute(table.insert().values({
                column.name: _FILLERS[column.type.python_type] for column in table.columns
                if not (column.primary_key or column.nullable or column.default is not None
                        or column.server_default is not None)
            }))
        counts = {name: conn.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar_one()
                  for name in _OWNERSHIP_TABLES}
    assert counts == dict.fromkeys(_OWNERSHIP_TABLES, 1)


def test_probe_next_test_finds_no_delivery_or_lease_rows():
    with engine.connect() as conn:
        counts = {name: conn.execute(select(func.count()).select_from(Base.metadata.tables[name])).scalar_one()
                  for name in _OWNERSHIP_TABLES}
    assert counts == dict.fromkeys(_OWNERSHIP_TABLES, 0)


def _fresh_pytest(*args, environ=None, extra_env=None):
    env = {k: v for k, v in (os.environ if environ is None else environ).items()
           if not k.startswith(("PYTEST_", "DATABASE_URL"))}
    env.update(extra_env or {})  # after the filter: a child can be handed a DATABASE_URL on purpose
    return subprocess.run(  # nosec B603 - fixed argv: this interpreter running pytest on fixed nodes
        [sys.executable, "-m", "pytest", "-q", "-n", "0", "-p", "no:cacheprovider", "-p", "no:randomly", *args],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
    )


def _pinned_methods():
    """Instance attributes on the generation singletons that are their own class's method, bound."""
    from app.services import summary_pipeline

    targets = (summary_pipeline.sec_edgar_service, summary_pipeline.xbrl_service, summary_pipeline.openai_service)
    return sorted(
        f"{type(target).__name__}.{name}" for target in targets for name, value in vars(target).items()
        if getattr(value, "__self__", None) is target and getattr(value, "__func__", None) is getattr(type(target), name, None)
    )


def test_probe_pins_a_singleton_method_like_monkeypatch(monkeypatch):
    # Undoing monkeypatch.setattr of a method on an instance sets the bound method it saved back on the
    # instance. Pin one method on each singleton; conftest must clear all three.
    from app.services import summary_pipeline

    assert _pinned_methods() == []
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "search_company", AsyncMock(return_value=[]))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.openai_service, "stream_chat", AsyncMock())
    monkeypatch.undo()
    assert _pinned_methods() == [
        "OpenAIService.stream_chat", "SECEdgarServiceCompat.search_company", "XBRLServiceCompat.get_xbrl_data",
    ]


def test_probe_next_test_finds_no_pinned_singleton_method():
    assert _pinned_methods() == []


def test_pinned_methods_are_cleared_without_the_pipeline(request, monkeypatch):
    # test_eval_measurement reaches xbrl_service through app.services.edgar.compat and never imports
    # summary_pipeline, so conftest finds the singletons where they live and clears them from there. A
    # bound method stored under another name is not a pin and stays.
    from app.services import openai_service as ai
    from app.services.edgar import compat

    conftest = request.config.pluginmanager.get_plugin(str(BACKEND_DIR / "tests" / "conftest.py"))
    monkeypatch.delitem(sys.modules, "app.services.summary_pipeline", raising=False)
    found = conftest._service_singletons()
    expected = [compat.sec_edgar_service, compat.xbrl_service, ai.openai_service]
    assert len(found) == 3 and all(a is b for a, b in zip(found, expected)), found
    service = compat.xbrl_service
    try:
        service.get_xbrl_data = service.get_xbrl_data  # a pin, as monkeypatch's undo leaves it
        service.xbrl_alias = service.get_xbrl_data  # the same bound method under a name the class lacks
        conftest._clear_pinned_methods()
        assert "get_xbrl_data" not in vars(service) and "xbrl_alias" in vars(service), sorted(vars(service))
    finally:
        vars(service).pop("get_xbrl_data", None)
        vars(service).pop("xbrl_alias", None)


def test_ordered_probes_hold_in_a_fresh_serial_process():
    result = _fresh_pytest(*_ORDERED_PROBES)
    assert result.returncode == 0 and f"{len(_ORDERED_PROBES)} passed" in result.stdout, (
        result.stdout[-3000:] + result.stderr[-2000:]
    )


def test_a_developers_database_url_never_reaches_the_suite(tmp_path):
    # conftest sets DATABASE_URL unconditionally. CI sets none, so a setdefault would pass every other test
    # there while handing a developer's own database to the whole suite.
    developer = tmp_path / "developer.db"
    result = _fresh_pytest(f"{_THIS}::test_the_suite_database_is_a_private_temp_file_per_process",
                           extra_env={"DATABASE_URL": f"sqlite:///{developer}"})
    assert result.returncode == 0 and "1 passed" in result.stdout, result.stdout[-3000:] + result.stderr[-2000:]
    assert not developer.exists()


_PROBE_PREFIXES = ("test_probe_", "test_isolation_")  # both halves of a pair


def _probe_ids(body: list[ast.stmt], prefix: str) -> set[str]:
    """The probes defined in a module or class body, as pytest node ids (Class::method in a class)."""
    found = set()
    for node in body:
        if isinstance(node, ast.ClassDef):
            found |= _probe_ids(node.body, f"{prefix}::{node.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(_PROBE_PREFIXES):
            found.add(f"{prefix}::{node.name}")
    return found


def test_every_isolation_probe_runs_in_the_ordered_process():
    # Under -n auto a probe pair outside _ORDERED_PROBES holds only when xdist keeps it together.
    probes = set()
    for path in sorted((BACKEND_DIR / "tests").rglob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if any(prefix in source for prefix in _PROBE_PREFIXES):
            probes |= _probe_ids(ast.parse(source).body, path.relative_to(BACKEND_DIR).as_posix())
    assert probes and probes <= set(_ORDERED_PROBES), sorted(probes - set(_ORDERED_PROBES))


def test_the_probe_scan_reads_class_methods_and_both_prefixes():
    source = (
        "def test_isolation_next_test_sees_it():\n    pass\n"
        "class TestPair:\n    def test_probe_dirties(self):\n        pass\n    def test_other(self):\n        pass\n"
    )
    assert _probe_ids(ast.parse(source).body, "t.py") == {
        "t.py::test_isolation_next_test_sees_it", "t.py::TestPair::test_probe_dirties",
    }


def test_a_mock_left_on_a_generation_singleton_fails_the_leaking_test(tmp_path):
    # The leak this guards: the function-scoped monkeypatch re-installing a stream_boundaries mock
    # after the harness exited. conftest loads as a plugin because the probe lives outside tests/.
    probe = tmp_path / "test_leak_probe.py"
    probe.write_text(
        "from unittest.mock import AsyncMock\n"
        "from app.services import summary_pipeline\n\n"
        "def test_leaves_a_mock_behind():\n"
        "    summary_pipeline.sec_edgar_service.get_filing_document = AsyncMock()\n\n"
        "def test_the_next_test_gets_the_real_method_back():\n"
        "    assert not isinstance(summary_pipeline.sec_edgar_service.get_filing_document, AsyncMock)\n",
        encoding="utf-8",
    )
    result = _fresh_pytest("-c", "pytest.ini", "-p", "tests.conftest", str(probe))
    summary = result.stdout.strip().splitlines()[-1]
    assert result.returncode == 1 and "2 passed" in summary and "1 error" in summary, result.stdout[-3000:]
    assert "mock left on a shared generation singleton after the test: " in result.stdout
    assert "get_filing_document" in result.stdout


# The child watches a symlink to the null device in place of /dev/null, and the probe replaces only that
# symlink, so the real /dev/null is never at stake, whether the run is root or not.
_NULL_DEVICE_PROBE = (
    "import os\n"
    "from pathlib import Path\n\n"
    "STAND_IN = Path(os.environ['NULL_STAND_IN'])\n"
    "assert STAND_IN.is_symlink() and STAND_IN.parent == Path(__file__).parent, STAND_IN\n"
    "os.devnull = str(STAND_IN)  # the null device conftest's check watches in this process\n\n"
    "def test_writes_into_the_null_device():\n"
    "    with open(os.devnull, 'w', encoding='utf-8') as sink:\n"
    "        sink.write('discarded')\n\n"
    "def test_renames_a_lock_file_over_it_like_a_git_config_write():\n"
    "    lock = STAND_IN.with_name(STAND_IN.name + '.lock')\n"
    "    lock.write_text('[probe]\\n\\tkey = value\\n', encoding='utf-8')\n"
    "    os.replace(lock, STAND_IN)\n"
)


def test_a_test_that_replaces_the_null_device_fails(tmp_path):
    # As root, a git config write through GIT_CONFIG_GLOBAL=/dev/null renames its lock file over the device.
    real = os.stat(os.devnull)
    assert stat.S_ISCHR(real.st_mode), f"{os.devnull} is not the null device before this test: restore it first"
    stand_in = tmp_path / "null"
    stand_in.symlink_to(os.devnull)
    probe = tmp_path / "test_null_device_probe.py"
    probe.write_text(_NULL_DEVICE_PROBE, encoding="utf-8")
    result = _fresh_pytest("-c", "pytest.ini", "-p", "tests.conftest", str(probe),
                           extra_env={"NULL_STAND_IN": str(stand_in)})
    summary = result.stdout.strip().splitlines()[-1]
    assert result.returncode == 1 and "2 passed" in summary and "1 error" in summary, result.stdout[-3000:]
    [error] = [line for line in result.stdout.splitlines() if line.startswith("ERROR ")]
    assert "::test_renames_a_lock_file_over_it_like_a_git_config_write" in error, error
    assert f"{stand_in} stopped being the null device during this test" in result.stdout
    assert not stand_in.is_symlink() and stand_in.read_text(encoding="utf-8").startswith("[probe]")
    now = os.stat(os.devnull)
    assert (now.st_ino, now.st_mode, now.st_rdev) == (real.st_ino, real.st_mode, real.st_rdev)


_EDGAR_DIRS = ("EDGAR_LOCAL_DATA_DIR", "EDGAR_CACHE_DIR")
# Each test appends where its process's EdgarTools reads and writes, to a file, because xdist keeps a
# worker's output.
_EDGAR_PROBE = (
    "import json, os\n"
    "from edgar.httpclient import get_cache_directory\n"
    "from edgar.paths import get_anchor_cache_directory, get_data_directory\n\n"
    "def _report():\n"
    "    with open(os.environ['EDGAR_PROBE_REPORT'], 'a', encoding='utf-8') as out:\n"
    "        out.write(json.dumps({'worker': os.environ.get('PYTEST_XDIST_WORKER', 'main'), 'db': os.environ['DATABASE_URL'],\n"
    "                              'dirs': [str(get_data_directory()), get_cache_directory(),\n"
    "                                       str(get_anchor_cache_directory())]}) + '\\n')\n\n"
    "def test_report_once():\n    _report()\n\n"
    "def test_report_twice():\n    _report()\n"
)


def _edgar_probe(tmp_path, *args, **edgar_env):
    """Each probe process's temp directory and EdgarTools' directories, by xdist worker ("main" if none)."""
    # HOME (USERPROFILE on Windows) is a fresh directory, so anything EdgarTools wrote to its home
    # defaults would show there. The temp root is fresh too, so a directory any process of the run left
    # behind (the xdist controller's included) shows there, unmixed with other runs on the machine.
    home, temp, report = tmp_path / "home", tmp_path / "temp", tmp_path / "report.jsonl"
    home.mkdir()
    temp.mkdir()
    probe = tmp_path / "test_edgar_dirs_probe.py"
    probe.write_text(_EDGAR_PROBE, encoding="utf-8")
    environ = {k: v for k, v in os.environ.items() if k not in _EDGAR_DIRS}
    result = _fresh_pytest("-c", "pytest.ini", "-p", "tests.conftest", *args, str(probe),
                           environ={**environ, **edgar_env, "HOME": str(home), "USERPROFILE": str(home),
                                    "TMPDIR": str(temp), "TEMP": str(temp), "TMP": str(temp),
                                    "EDGAR_PROBE_REPORT": str(report)})
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
    assert not any(home.iterdir()), sorted(home.rglob("*"))
    # Every process removed its directory when it ended: the serial run, each worker and the controller.
    assert not sorted(temp.glob("earningsnerd-tests-*")), sorted(temp.glob("earningsnerd-tests-*"))
    seen = {}
    for row in map(json.loads, report.read_text(encoding="utf-8").splitlines()):
        # Resolved, as EdgarTools resolves its own: macOS reaches the temp directory through a symlink.
        private = Path(make_url(row["db"]).database).resolve().parent
        seen.setdefault(row["worker"], set()).add((private, tuple(Path(d) for d in row["dirs"])))
    assert all(len(places) == 1 for places in seen.values()), seen  # one process, one set of directories
    return {worker: places.pop() for worker, places in seen.items()}


def test_edgartools_writes_only_to_the_processs_temp_directory(tmp_path):
    # This process: both set, so EdgarTools never falls back to ~/.edgar or ~/.edgar_cache.
    assert all(os.environ.get(name) for name in _EDGAR_DIRS), {n: os.environ.get(n) for n in _EDGAR_DIRS}
    ((private, dirs),) = _edgar_probe(tmp_path).values()
    assert private.name.startswith("earningsnerd-tests-main-"), private
    assert all(private in d.parents for d in dirs), (private, dirs)
    assert not private.exists()  # removed with the database when the process ended


def test_offline_enrichment_stubs_exactly_its_listed_files(request):
    # conftest's _offline_stream_enrichment picks its files by "<parent>/<name>". Drive it with each listed
    # file's real path and with paths that share one part with a listed file (a sibling in its directory,
    # its name in another directory), so a moved file, or a key on the directory or the name alone, fails
    # here by name instead of as an outbound request the network gate blocks in a stream test.
    from app.services import summary_pipeline

    conftest = request.config.pluginmanager.get_plugin(str(BACKEND_DIR / "tests" / "conftest.py"))
    stub = conftest._offline_stream_enrichment.__wrapped__
    service, seams = summary_pipeline.xbrl_service, ("get_xbrl_data", "get_filing_sections")
    real = {seam: getattr(service, seam) for seam in seams}
    listed = sorted(conftest._OFFLINE_ENRICHMENT_FILES)
    assert all((BACKEND_DIR / "tests" / rel).is_file() for rel in listed), listed
    directory, name = listed[0].split("/")
    unlisted = [f"{directory}/test_not_on_the_list.py", f"unit/{name}", _THIS.removeprefix("tests/")]
    assert not set(seams) & vars(service).keys()  # the seams start as the class's methods
    stubbed = {}
    for rel in [*listed, *unlisted]:
        steps = stub(SimpleNamespace(path=BACKEND_DIR / "tests" / rel))
        next(steps)
        stubbed[rel] = [seam for seam in seams if isinstance(getattr(service, seam), AsyncMock)]
        with pytest.raises(StopIteration):
            next(steps)
        # Restored on exit, with nothing left on the shared instance to shadow a later class-level patch.
        assert {seam: getattr(service, seam) for seam in seams} == real, rel
        assert not set(seams) & vars(service).keys(), rel
    assert stubbed == {**{rel: list(seams) for rel in listed}, **{rel: [] for rel in unlisted}}


def test_each_xdist_worker_keeps_edgartools_in_its_own_temp_directory(tmp_path):
    # The controller assigns its directories before it starts the workers, which inherit its environment.
    runs = _edgar_probe(tmp_path, "-n", "2", "--dist", "each")
    assert set(runs) == {"gw0", "gw1"}, runs
    for worker, (private, dirs) in runs.items():
        assert private.name.startswith(f"earningsnerd-tests-{worker}-"), (worker, private)
        assert all(private in d.parents for d in dirs), (worker, private, dirs)


def test_an_edgartools_directory_set_before_pytest_starts_is_kept(tmp_path):
    data, cache = tmp_path / "data", tmp_path / "cache"
    ((_, dirs),) = _edgar_probe(tmp_path, EDGAR_LOCAL_DATA_DIR=str(data), EDGAR_CACHE_DIR=str(cache)).values()
    assert dirs == (data.resolve(), data.resolve() / "_tcache", cache.resolve() / "anchors"), dirs
    assert all(d.is_dir() for d in dirs)  # a developer's directories outlive the run


def test_an_empty_edgartools_directory_gets_a_private_one_beside_a_kept_one(tmp_path):
    data = tmp_path / "data"
    ((private, dirs),) = _edgar_probe(tmp_path, EDGAR_LOCAL_DATA_DIR=str(data), EDGAR_CACHE_DIR="").values()
    assert dirs[:2] == (data.resolve(), data.resolve() / "_tcache"), dirs
    assert private in dirs[2].parents, (private, dirs)  # EdgarTools reads "" as unset: the home default


def test_sqlite_never_reissues_a_deleted_id():
    probe = create_engine("sqlite://")
    Base.metadata.create_all(probe)
    with Session(probe) as db:
        first = Company(cik="0000000001", ticker="IDREUSEA", name="Id Reuse A")
        db.add(first)
        db.commit()
        first_id = first.id
        db.delete(first)
        db.commit()
        second = Company(cik="0000000002", ticker="IDREUSEB", name="Id Reuse B")
        db.add(second)
        db.commit()
        assert second.id != first_id
    probe.dispose()
