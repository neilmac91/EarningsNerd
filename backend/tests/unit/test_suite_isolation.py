"""Each pytest process owns a private, PostgreSQL-like SQLite database, and process state set by one
test never reaches the next (gates for the parallel, order-independent suite).

``backend/tests/conftest.py`` points ``DATABASE_URL`` at a fresh temp directory before any app import:
one per session, and one per pytest-xdist worker, because every worker is its own process. Without it
the suite shares the CWD-relative default ``sqlite:///./earningsnerd.db`` (``backend/earningsnerd.db``):
parallel workers, or a second run in the same worktree, read and rewrite one file, and that file
outlives every schema change (lessons/ops-one-test-process-per-worktree.md). Because that database
starts empty, conftest also creates the schema once per process: no test may depend on an earlier
test (or the app lifespan of an earlier ``TestClient``) having created its tables.

The same conftest gives SQLite tables AUTOINCREMENT ids. PostgreSQL never hands out a sequence value
twice; SQLite's default max(rowid)+1 re-issues a deleted test's id to the next test, where a child row
the first test left behind (SQLite here enforces no foreign keys) silently joins the new parent.

Conftest's autouse resets are pinned by probe pairs: one test leaves the state dirty, the next asserts
the clean default. Under ``-n auto`` and random order a pair can land on two workers or run reversed,
which proves nothing, so ``test_isolation_probes_hold_in_a_fresh_serial_process`` runs every probe in
a fixed order in one fresh process.
"""
import os
import stat
import subprocess  # nosec B404 - runs this repo's own pytest on fixed nodes of the suite
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Company
from tests.support.summary_stream_harness import CANONICAL_PAYLOAD

BACKEND_DIR = Path(__file__).resolve().parents[2]
_THIS = Path(__file__).relative_to(BACKEND_DIR).as_posix()
_AI_METRICS = "tests/unit/test_ai_metrics.py"
# Order matters: the schema probe must be the process's first test; each dirtying probe precedes
# the probe that asserts the reset.
_ORDERED_PROBES = [
    f"{_THIS}::test_probe_reads_the_schema_without_creating_it",
    f"{_THIS}::test_probe_mutates_the_canonical_payload_like_the_pipeline",
    f"{_THIS}::test_probe_next_test_sees_the_pristine_canonical_payload",
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


def test_isolation_probes_hold_in_a_fresh_serial_process():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "DATABASE_URL"))}
    result = subprocess.run(  # nosec B603 - fixed argv: this interpreter running pytest on fixed nodes
        [sys.executable, "-m", "pytest", "-q", "-n", "0", "-p", "no:cacheprovider", "-p", "no:randomly",
         *_ORDERED_PROBES],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0 and f"{len(_ORDERED_PROBES)} passed" in result.stdout, (
        result.stdout[-3000:] + result.stderr[-2000:]
    )


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
