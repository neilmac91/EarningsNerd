"""Each pytest process owns a private, Postgres-like SQLite database (gates for the parallel suite).

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
"""
import os
import stat
import subprocess  # nosec B404 - runs this repo's own pytest on one node of this file
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Company

BACKEND_DIR = Path(__file__).resolve().parents[2]


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
    # Run on its own in a fresh process by the next test. Creates nothing: it passes only if
    # conftest gave this process's new database the schema before the first test.
    with SessionLocal() as db:
        assert db.query(Company).filter(Company.cik == "probe-never-seeded").count() == 0


def test_a_fresh_process_has_the_schema_before_its_first_test():
    probe = f"{Path(__file__).relative_to(BACKEND_DIR)}::test_probe_reads_the_schema_without_creating_it"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "DATABASE_URL"))}
    result = subprocess.run(  # nosec B603 - fixed argv: this interpreter running pytest on one node
        [sys.executable, "-m", "pytest", "-q", "-n", "0", "-p", "no:cacheprovider", "-p", "no:randomly", probe],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]


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
