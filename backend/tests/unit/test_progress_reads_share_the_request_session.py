"""Gate for lessons/ops-one-connection-per-request-unit.md: a request unit reads everything through
its own session, so it never needs a second pooled connection while it holds one.

The dashboard feed and the watchlist insights read each filing's generation progress through
``summary_generation_service.get_generation_progress_snapshot``, which opened a session of its own.
Each request then held its session's connection and waited for a second one: on main, eight
requests on a four-slot pool answered 500 at the pool timeout, all eight, on both routes, and one
request on a one-slot pool could not finish. Both now read the progress rows in the request's own
session, in one query.

- Behaviour: each route answers one request on a one-slot pool, and eight requests on four slots,
  with the summary statuses the summaries and progress rows imply; the feed's unit leaves nothing
  for the dependency's finalizer.
- Structure: ``get_generation_progress_snapshot`` is gone since E124. A scan of every module under ``app/``
  and the backend's top-level modules (``main.py``, ``task_worker_main.py``) fails a ``def``, ``async def`` or
  ``class`` of that name at any depth, a method included, and each use of the name: a name, an attribute, or
  an import of it or under it. ``test_the_scan_reads_each_form_it_claims`` scores those forms, and the
  look-alikes it passes, on planted source.

Out of reach, so review holds them: a definition or reference through a string or a namespace
(``setattr``, ``globals()``, ``exec``, ``getattr``, ``operator.attrgetter``, ``importlib``, a module's
``__dict__`` or ``__all__``).
"""

import ast
import asyncio
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.database import Base
from app.models import Company, Filing, Summary, SummaryGenerationProgress, User, Watchlist
from app.services import summary_generation_service
from app.utils.datetimes import utcnow
from main import app

# Reader i watches one company with one filing, which by i % 4 has: a progress row at "analyzing",
# one at "error", nothing, or a ready summary beside a progress row at "summarizing".
_VARIANTS = (("analyzing", False), ("error", False), (None, False), ("summarizing", True))
_STATUS = {"analyzing": "generating:analyzing", "error": "error", None: "missing"}


def _expected_status(i: int) -> str:
    stage, summarized = _VARIANTS[i % 4]
    return "ready" if summarized else _STATUS[stage]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/dashboard/feed", "/api/watchlist/insights"])
@pytest.mark.parametrize("slots,readers", [(1, 1), (4, 8)])
async def test_progress_reads_need_no_second_connection(monkeypatch, tmp_path, path, slots, readers):
    from app.routers import auth

    engine = create_engine(
        f"sqlite:///{tmp_path / 'progress-reads.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=slots,
        max_overflow=0,
        pool_timeout=1.0,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        for i in range(readers):
            company = Company(cik=f"{i + 1:010d}", ticker=f"PRG{i}", name=f"Progress {i}",
                              history_backfilled_at=utcnow())
            db.add(company)
            db.flush()
            filing = Filing(company_id=company.id, accession_number=f"{i + 1:010d}-26-000001",
                            filing_type="10-K", filing_date=utcnow(),
                            sec_url="https://example.test/filing/", document_url="https://example.test/filing.htm")
            db.add(filing)
            reader = User(email=f"progress-reader-{i}@example.com", is_active=True)
            db.add(reader)
            db.flush()
            db.add(Watchlist(user_id=reader.id, company_id=company.id))
            stage, summarized = _VARIANTS[i % 4]
            if summarized:
                db.add(Summary(filing_id=filing.id, business_overview="## Overview", raw_summary={}))
            if stage:
                db.add(SummaryGenerationProgress(filing_id=filing.id, stage=stage, started_at=utcnow(),
                                                 updated_at=utcnow(), error="boom" if stage == "error" else None))
        db.commit()

    request_sessions: list[Session] = []

    class RequestSession(Session):
        """Records, at each close, whether the session still held a transaction (a pooled connection)."""

        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self.open_at_close: list[bool] = []
            request_sessions.append(self)

        def close(self) -> None:
            self.open_at_close.append(self.in_transaction())
            super().close()

    # summary_generation_service binds SessionLocal at import (``_prepare_background_generation``). Point it
    # at this pool too, so a read through a session of its own inside either route's unit would need a
    # second slot here, as it would in production.
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=RequestSession))
    monkeypatch.setattr(summary_generation_service, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async def read(i: int) -> httpx.Response:
        token = auth.create_access_token({"sub": f"progress-reader-{i}@example.com"})
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            return await client.get(path)

    try:
        responses = await asyncio.gather(*[read(i) for i in range(readers)])
        assert [response.status_code for response in responses] == [200] * readers
        for i, response in enumerate(responses):
            stage = _VARIANTS[i % 4][0]
            if path == "/api/dashboard/feed":
                [item] = response.json()["items"]
                assert (item["company"]["ticker"], item["summary_status"]) == (f"PRG{i}", _expected_status(i))
            else:
                [insight] = response.json()
                latest = insight["latest_filing"]
                assert (insight["company"]["ticker"], latest["summary_status"]) == (f"PRG{i}", _expected_status(i))
                # Every latest filing carries its progress, a summarized one included.
                assert (latest["progress"] or {}).get("stage") == stage
        assert engine.pool.checkedout() == 0
        if path == "/api/dashboard/feed":
            # The feed's unit released its session; the dependency's finalizer found nothing open.
            assert [session.open_at_close[-1:] for session in request_sessions] == [[False]] * readers
    finally:
        engine.dispose()


# ── Structure: the own-session progress helper stays deleted and unused ─────────────────

BACKEND_DIR = Path(__file__).resolve().parents[2]
_HELPER = "get_generation_progress_snapshot"


def helper_sites(source: str, file: str = "probe.py") -> list[str]:
    """Each site in ``source`` that defines ``get_generation_progress_snapshot`` (a ``def``, ``async def`` or
    ``class`` of the name, at any depth) or uses the name (a name, an attribute, or an import of it or under
    it), in line order."""
    found = []
    for node in ast.walk(ast.parse(source, filename=file)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == _HELPER:
            found.append((node.lineno, "its definition"))
        elif (isinstance(node, ast.Name) and node.id == _HELPER) or (
                isinstance(node, ast.Attribute) and node.attr == _HELPER):
            found.append((node.lineno, "a use"))
        elif isinstance(node, ast.alias) and _HELPER in (node.name, node.asname):
            found.append((node.lineno, "an import"))
    return [f"{file}:{line} ({kind})" for line, kind in sorted(found)]


def test_no_code_reads_progress_through_its_own_session():
    """``get_generation_progress_snapshot`` opened a session of its own, so a request unit that called it
    while its session held a connection needed two. E124 deleted it. Read the progress rows in the caller's
    session instead (``SummaryGenerationProgress`` and ``progress_as_dict``)."""
    paths = sorted((BACKEND_DIR / "app").rglob("*.py")) + sorted(BACKEND_DIR.glob("*.py"))
    # A walk that reads nothing would pass with the helper restored, so it must read the module it lived in.
    assert BACKEND_DIR / "app" / "services" / "summary_generation_service.py" in paths
    sites = [site for path in paths
             for site in helper_sites(path.read_text(encoding="utf-8"), path.relative_to(BACKEND_DIR).as_posix())]
    assert sites == [], (
        f"{_HELPER} opened its own session; these sites define or use it: {sites}. Read SummaryGenerationProgress "
        "in the caller's session (lessons/ops-one-connection-per-request-unit.md)."
    )


def test_the_scan_reads_each_form_it_claims():
    """The scan's fixture: each form it fails, the look-alikes it passes, and a reference through a string,
    which the header names as out of its reach."""
    probe = '''
from app.services.summary_generation_service import get_generation_progress_snapshot
from app.services.summary_generation_service import get_generation_progress_snapshot as read_progress
from app.services import summary_generation_service as service
import json as get_generation_progress_snapshot

def get_generation_progress_snapshot(filing_id):
    return None

async def get_generation_progress_snapshot(filing_id):
    return None

class get_generation_progress_snapshot:
    pass

class Reader:
    def get_generation_progress_snapshot(self, filing_id):
        def get_generation_progress_snapshot():
            return None

def uses(filing_id):
    get_generation_progress_snapshot(filing_id)
    service.get_generation_progress_snapshot(filing_id)
    reader = get_generation_progress_snapshot

def look_alikes(filing_id):
    """get_generation_progress_snapshot, named in a docstring."""
    get_generation_progress(filing_id)
    progress_snapshot(filing_id)
    record(get_generation_progress_snapshot=filing_id)
    return {"get_generation_progress_snapshot": filing_id}

def out_of_reach(filing_id):
    return getattr(service, "get_generation_progress_snapshot")(filing_id)
'''
    assert helper_sites(probe) == [
        "probe.py:2 (an import)",
        "probe.py:3 (an import)",
        "probe.py:5 (an import)",
        "probe.py:7 (its definition)",
        "probe.py:10 (its definition)",
        "probe.py:13 (its definition)",
        "probe.py:17 (its definition)",
        "probe.py:18 (its definition)",
        "probe.py:22 (a use)",
        "probe.py:23 (a use)",
        "probe.py:24 (a use)",
    ]
