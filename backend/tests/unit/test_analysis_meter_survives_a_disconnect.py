"""A Multi-Period Analysis generation whose narrative was sent is metered, whenever its client leaves (E301).

uvicorn speaks ASGI 2.3, so Starlette cancels a streaming response's task when its client disconnects. The narrative
writes its cache row in a thread-pool unit after the ``token`` frame. A disconnect taken while the write runs in its
thread was delivered at the router's meter, an await of its own (round 1 of #1990's review). One taken while the write
waited for a worker thread, or at its unit's entry, both before the unit's own shield, cancelled the write itself
(round 2). Either way a client that read the narrative and closed went uncounted, its lease given back. The write is
shielded now once the token is out, the completion follows it with no await between, and the meter is shielded like
the release beside it. The write stays after the token: behind the app's ``BaseHTTPMiddleware`` layers a frame's send
is a checkpoint too (``lessons/arch-shield-a-streams-meter-and-await-nothing-before-it.md``).

Each case drives the real app (its middleware included), the router, the narrative, the admission and the meter over a
SQLite database, with only the model faked, and the client leaves at one step:
- while the model runs: no row is written, nothing is counted, and the lease is given back;
- while the cache write waits for a worker thread, every token of anyio's default limiter held, after the client read
  the narrative: the row is written once a thread frees, counted once, and the lease converted;
- while the cache row is written, after the client read the narrative: the same.
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import date
from typing import Any, Callable

import anyio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.responses import StreamingResponse

from app import database
from app.models import Company, FinancialFact, TrendAnalysis, UsageReservation, User, UserUsage
from app.services.rate_limiter import RateLimiter
from app.utils.datetimes import utcnow
from main import app

_EMAIL = "meter-reader@example.com"
_PATH = "/api/analysis/METER/stream"


def _database(tmp_path):
    """One company with two fiscal years of revenue and net income, one Pro reader, and no saved analysis, so the
    run is a first-time generation: never meter-exempt."""
    engine = create_engine(f"sqlite:///{tmp_path / 'meter.db'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        company = Company(cik="0000000001", ticker="METER", name="Meter fixture",
                          history_backfilled_at=utcnow(), facts_synced_at=utcnow())
        db.add(company)
        db.flush()
        for year, revenue, net_income in ((2024, 100, 10), (2025, 120, 15)):
            for concept, value in (("revenue", revenue), ("net_income", net_income)):
                db.add(FinancialFact(
                    company_id=company.id, concept=concept, unit="USD", period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31), fiscal_year=year, fiscal_period="FY", value=value,
                    form="10-K", accession=f"0000000001-{year % 100:02d}-000001", reconciled=True,
                ))
        db.add(User(email=_EMAIL, is_active=True, is_pro=True))
        db.commit()
    return engine, sessions


def _scope(token: str, body: bytes) -> dict[str, Any]:
    return {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": _PATH, "raw_path": _PATH.encode(), "root_path": "",
        "query_string": b"", "client": ("127.0.0.1", 1234), "server": ("testserver", 80),
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()), (b"authorization", f"Bearer {token}".encode())],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("leaves_while", ["the_model_runs", "the_write_waits_for_a_thread", "the_cache_row_is_written"])
async def test_a_sent_analysis_is_counted_whenever_its_client_leaves(monkeypatch, tmp_path, leaves_while):
    from app.routers import analysis, auth
    from app.services import openai_service as oa
    from app.services.trend_analysis import narrative
    from app.services.trend_analysis.observations import ANALYSIS_SECTIONS

    engine, sessions = _database(tmp_path)
    loop = asyncio.get_running_loop()
    limiter = anyio.to_thread.current_default_thread_limiter()  # what run_in_threadpool, and so the write, waits on
    held: list[object] = []  # borrowers holding the limiter's tokens
    watcher: list[asyncio.Task] = []
    leave = asyncio.Event()  # the client closes the connection
    read_the_narrative = threading.Event()  # the token frame reached the client
    stream_cancelled = threading.Event()  # the route's response took the disconnect
    write_saw: dict[str, bool] = {}
    real_listen = StreamingResponse.listen_for_disconnect
    real_persist = narrative._persist_analysis
    selection = json.dumps({key: [] for key, _ in ANALYSIS_SECTIONS}, separators=(",", ":"))

    async def listen(self, receive):  # the route's response; the middleware's responses are another class
        await real_listen(self, receive)
        stream_cancelled.set()  # its cancel of the stream follows in this step, before the loop resumes the stream

    def release_the_threads() -> None:
        while held:
            limiter.release_on_behalf_of(held.pop())

    async def wait_until(condition: Callable[[], Any], failure: str) -> None:
        async def poll() -> None:
            while not condition():
                await asyncio.sleep(0)

        try:
            await asyncio.wait_for(poll(), 5.0)  # a hang guard; a passing run waits a few loop turns
        except TimeoutError as exc:
            raise AssertionError(failure) from exc

    async def leave_while_the_write_waits() -> None:  # on the loop, beside the stream
        try:
            await wait_until(lambda: limiter.statistics().tasks_waiting and read_the_narrative.is_set(),
                             "the write never waited for a thread after the token")
            leave.set()
            await wait_until(stream_cancelled.is_set, "the route never took the disconnect")
            write_saw["the write waited for a thread"] = True
        finally:
            release_the_threads()  # always, or a shielded write would wait for a thread forever

    async def stream_chat(_messages: Any, **kwargs: Any):
        kwargs["usage_sink"].update({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        if leaves_while == "the_model_runs":
            leave.set()
            await asyncio.Event().wait()  # the disconnect's cancel lands here
        if leaves_while == "the_write_waits_for_a_thread":  # every worker thread taken, as a full pool's units do
            while limiter.available_tokens:
                held.append(object())
                limiter.acquire_on_behalf_of_nowait(held[-1])
            watcher.append(asyncio.ensure_future(leave_while_the_write_waits()))
        yield selection

    def persist(**kwargs: Any) -> Any:  # the cache write, in its thread-pool unit
        if leaves_while == "the_cache_row_is_written":
            write_saw["the narrative read first"] = read_the_narrative.wait(timeout=5)  # a hang guard only
            loop.call_soon_threadsafe(leave.set)
            write_saw["the stream cancelled"] = stream_cancelled.wait(timeout=5)  # a hang guard only
        return real_persist(**kwargs)

    monkeypatch.setattr(StreamingResponse, "listen_for_disconnect", listen)
    monkeypatch.setattr(narrative, "_persist_analysis", persist)
    monkeypatch.setattr(oa.openai_service, "stream_chat", stream_chat)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(app, "dependency_overrides", {})
    monkeypatch.setattr(auth, "sentry_sdk", None)
    monkeypatch.setattr(analysis, "STREAM_LIMITER", RateLimiter(limit=100, window_seconds=60))
    monkeypatch.setattr(analysis, "_emit_analysis_cost_best_effort", lambda *_a, **_k: None)
    body = json.dumps({"mode": "annual", "start_period": "FY2024", "end_period": "FY2025"}).encode()
    requests = [{"type": "http.request", "body": body, "more_body": False}]
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        if requests:
            return requests.pop(0)
        await leave.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)
        if message["type"] == "http.response.body" and b'"type": "token"' in message.get("body", b""):
            read_the_narrative.set()

    def stored() -> tuple[int, int, int]:
        with sessions() as db:
            counted = sum(usage.analysis_count or 0 for usage in db.query(UserUsage))
            return db.query(TrendAnalysis).count(), counted, db.query(UsageReservation).count()

    try:
        await asyncio.wait_for(app(_scope(auth.create_access_token({"sub": _EMAIL}), body), receive, send), 15)
        for task in watcher:
            await asyncio.wait_for(task, 5)  # surfaces its assertions
        # Starlette leaves a cancelled stream's generators suspended, for the collector to close as a server's would.
        # Close them now, so each ``finally`` has run before the rows are read and no worker thread outlives the loop.
        await loop.shutdown_asyncgens()
        assert sent[0]["status"] == 200
        assert stream_cancelled.is_set()
        if leaves_while == "the_model_runs":
            assert not read_the_narrative.is_set()
            assert stored() == (0, 0, 0)  # nothing written, nothing counted, the lease given back
        else:
            assert read_the_narrative.is_set()
            assert write_saw == ({"the write waited for a thread": True} if leaves_while == "the_write_waits_for_a_thread"
                                 else {"the narrative read first": True, "the stream cancelled": True})
            assert stored() == (1, 1, 0)  # written, counted once, the lease converted
    finally:
        release_the_threads()
        engine.dispose()
