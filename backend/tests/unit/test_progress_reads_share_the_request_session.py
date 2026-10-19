"""Gate for lessons/ops-one-connection-per-request-unit.md: a request unit reads everything through
its own session, so it never needs a second pooled connection while it holds one.

The dashboard feed and the watchlist insights read each filing's generation progress through
``summary_generation_service.get_generation_progress_snapshot``, which opens a session of its own.
Each request then held its session's connection and waited for a second one: on main, eight
requests on a four-slot pool answered 500 at the pool timeout, all eight, on both routes, and one
request on a one-slot pool could not finish. Both now read the progress rows in the request's own
session, in one query.

- Behaviour: each route answers one request on a one-slot pool, and eight requests on four slots,
  with the summary statuses the summaries and progress rows imply; the feed's unit leaves nothing
  for the dependency's finalizer.
- Structure: no code under ``app/`` calls ``get_generation_progress_snapshot`` again.
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

    # The progress helper binds SessionLocal at import; both point at this pool, as in production.
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


# ── Structure: the own-session progress helper stays uncalled ─────────────────────────────

APP_DIR = Path(__file__).resolve().parents[2] / "app"
_HELPER = "get_generation_progress_snapshot"


def test_no_code_reads_progress_through_its_own_session():
    """``get_generation_progress_snapshot`` opens a session of its own, so a request unit that calls it
    while its session holds a connection needs two. Read the progress rows in the caller's session
    instead (``SummaryGenerationProgress`` and ``progress_as_dict``)."""
    callers = []
    for path in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == _HELPER:
                callers.append(f"{path.relative_to(APP_DIR.parent)}:{node.lineno}")
            elif isinstance(node, ast.Attribute) and node.attr == _HELPER:
                callers.append(f"{path.relative_to(APP_DIR.parent)}:{node.lineno}")
            elif isinstance(node, ast.alias) and node.name == _HELPER:
                callers.append(f"{path.relative_to(APP_DIR.parent)}:import")
    assert callers == [], (
        f"{_HELPER} opens its own session; these sites use it: {callers}. Read SummaryGenerationProgress "
        "in the caller's session (lessons/ops-one-connection-per-request-unit.md)."
    )
