"""A Copilot DB lookup waiting for a pool slot must let the request holding that slot finish.

``copilot_tools.run_tool`` opens its own ``SessionLocal()`` and checks out a pooled connection. The
model's numeric tool calls (``stream_chat_with_tools``) and the server's claim-repair lookup
(``_resolve_answer``) both reach it from inside the Copilot's SSE generator, which runs on the event
loop. When every slot is held, a checkout made on the loop thread blocks the whole loop for the pool
timeout, so the request holding the slot cannot run the step that gives it back: the lookup times
out, the tool reports ``tool_failed`` and the figure ships uncited.

Here a one-slot ``QueuePool`` is held by another "request". One holder returns its connection as
soon as the event loop runs one callback (the ``test_auth_pool_progress.py`` shape). The other is
shaped like a password change or reset: it keeps its connection checked out while it awaits bcrypt through
``asyncio.to_thread``, so it needs a default-executor thread before it can give the slot back. The
loop's default executor has one thread here, so a lookup waiting for the slot in that executor would
hold the only thread the holder needs, and neither could move until the pool timed out. The real
``answer_filing_question`` -> ``OpenAIService.stream_chat_with_tools`` -> ``_FactRegistry`` ->
``copilot_tools.run_tool`` path runs; only the SDK client and the engine behind
``copilot_tools.SessionLocal`` are replaced. The assertions are about outcome and ordering, never
wall-clock time: the holder releases before the lookup's checkout succeeds, the figure is cited,
and every lookup ran in a worker thread in its own session, which it closed.
"""
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.models.financial_fact import FinancialFact
from app.services import copilot_service, copilot_tools
from app.services.ai import copilot_chat
from app.services.openai_service import openai_service

ACC = "0000999999-24-000042"
COMPANY_ID = 7
# Generous: the fixed path gets its slot as soon as the loop runs one callback. Only the on-loop
# checkout this test guards against ever waits this long, and it then fails the assertions below.
POOL_TIMEOUT = 2.0
# Hang guards only: a passing run never waits for one. The stalled query and the pool wait outlast the
# guard, so a question left waiting on a stalled lookup fails on the guard.
HANG_GUARD_S = 5.0
STALL_S = 30.0
FOLLOWUPS = '\n===CITATIONS===\n[]\n===FOLLOWUPS===\n["What drove revenue?", "What are the main risks?"]'

# The model calls the numeric tool, then cites the figure it returned.
TOOL_ROUNDS = [
    [{"tool": ("get_financial_fact", '{"concept": "revenue"}')}],
    [{"content": "Total revenue was $100.0 million [F1]." + FOLLOWUPS}],
]
# The model calls no tool; the server's claim repair looks the annual figure up itself.
REPAIR_ROUNDS = [
    [{"content": "Revenue for the fiscal year ended December 31, 2024 was $100.0 million." + FOLLOWUPS}],
]


async def _release_on_the_next_loop_turn() -> None:
    """The holder needs only the event loop to finish."""


async def _release_after_a_default_executor_step() -> None:
    """A password change's shape: ``await asyncio.to_thread(verify_password, ...)`` while its session
    holds the slot."""
    await asyncio.to_thread(lambda: None)


def _chunk(spec: dict) -> SimpleNamespace:
    tool_calls = None
    if "tool" in spec:
        name, arguments = spec["tool"]
        tool_calls = [SimpleNamespace(index=0, id="call_1",
                                      function=SimpleNamespace(name=name, arguments=arguments))]
    return SimpleNamespace(model="fake", system_fingerprint=None, usage=None, choices=[
        SimpleNamespace(delta=SimpleNamespace(content=spec.get("content"), tool_calls=tool_calls)),
    ])


def _fake_client(rounds: list[list[dict]], sent: list[list[dict]]) -> SimpleNamespace:
    async def create(**kwargs):
        sent.append(json.loads(json.dumps(kwargs["messages"], default=str)))
        chunks = [_chunk(spec) for spec in rounds[len(sent) - 1]]

        async def stream():
            for chunk in chunks:
                yield chunk
        return stream()

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def _viewed_filing() -> SimpleNamespace:
    """What the ask-stream route hands the generator: a detached snapshot, never an ORM row."""
    return copilot_service.snapshot_filing(SimpleNamespace(
        accession_number=ACC, period_end_date=datetime(2024, 12, 31), filing_type="10-K",
        filing_date=None, xbrl_data={"reporting_currency": "USD"}, company_id=COMPANY_ID,
        document_url="https://www.sec.gov/Archives/edgar/data/999999/000099999924000042/z.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/999999/000099999924000042/",
        content_cache=SimpleNamespace(critical_excerpt="Zed Corp sells widgets worldwide. " * 10,
                                      markdown_content=None),
        company=SimpleNamespace(cik="0000999999", name="Zed Corp", ticker="ZZZ"),
    ))


@pytest.mark.asyncio
@pytest.mark.parametrize("rounds", [TOOL_ROUNDS, REPAIR_ROUNDS], ids=["model_tool_call", "claim_repair"])
@pytest.mark.parametrize("holder_step", [_release_on_the_next_loop_turn, _release_after_a_default_executor_step],
                         ids=["loop_turn", "default_executor_step"])
async def test_waiting_copilot_lookup_lets_the_slot_holder_finish(monkeypatch, tmp_path, rounds, holder_step):
    engine = _pool_with_revenue(tmp_path, pool_size=1)

    loop = asyncio.get_running_loop()
    # One default-executor thread stands in for a default executor whose threads are all taken: a
    # lookup waiting there would hold the thread a change-shaped holder needs. The test's loop closes
    # this executor at teardown.
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
    loop_thread = threading.get_ident()
    release_holder = asyncio.Event()
    order: list[str] = []
    lookups: list[tuple[int, bool]] = []  # (session, queried on the event-loop thread)
    closed: set[int] = set()

    class ObservedSession(Session):
        def query(self, *args, **kwargs):
            lookups.append((id(self), threading.get_ident() == loop_thread))
            # The lookup is about to wait on the only connection. Its holder can give the slot
            # back as soon as the event loop is free to run this callback.
            loop.call_soon_threadsafe(release_holder.set)
            return super().query(*args, **kwargs)

        def close(self):
            closed.add(id(self))
            super().close()

    monkeypatch.setattr(copilot_tools, "SessionLocal", sessionmaker(bind=engine, class_=ObservedSession))
    sent: list[list[dict]] = []
    monkeypatch.setattr(openai_service, "client", _fake_client(rounds, sent))

    # Another request holds the only pooled connection and finishes once the loop lets it.
    holder_db = sessionmaker(bind=engine)()
    holder_db.connection()
    assert engine.pool.checkedout() == 1
    event.listen(engine, "checkout", lambda *_: order.append("lookup checked out"))

    async def holder():
        await release_holder.wait()
        await holder_step()
        order.append("holder releasing")  # before close(): the waiting lookup may run at once
        holder_db.close()

    hold = asyncio.create_task(holder())
    try:
        events = await asyncio.wait_for(_collect(_viewed_filing()), timeout=30)
        await asyncio.wait_for(hold, timeout=5)
    finally:
        release_holder.set()
        await hold
        holder_db.close()
        engine.dispose()

    complete = next(e for e in events if e["type"] in ("complete", "error"))
    tool_results = [json.loads(m["content"]) for m in sent[-1] if m.get("role") == "tool"]
    assert all("error" not in result for result in tool_results), tool_results
    assert complete["type"] == "complete", complete
    assert [(c["concept"], c["value"]) for c in complete["citations"]] == [("revenue", 100_000_000.0)], (
        complete["answer"], complete["citations"],
    )
    assert complete["uncited_figures"] == 0
    # The loop ran the holder while the lookup waited, so the slot came back before the checkout.
    assert order == ["holder releasing", "lookup checked out"], order
    # Session ownership: every lookup ran in a worker thread, in a session copilot_tools opened
    # for itself and closed again; nothing on the loop shared or reused it.
    assert lookups and not any(on_loop for _, on_loop in lookups), lookups
    assert {session for session, _ in lookups} <= closed


@pytest.mark.asyncio
async def test_copilot_lookup_still_queued_at_the_question_deadline_never_runs(monkeypatch, tmp_path):
    """A lookup queued behind busy lookup threads must not keep its question open past the deadline.

    Another request holds one of the pool's two connections throughout. The first lookup takes the
    other and its query stalls (a slow database); three more wait for that connection, one per
    remaining lookup thread; as many questions again wait for a thread. Once all of them are under way,
    the test expires each question's deadline by rescheduling the real ``asyncio`` timeout its lookup
    wait entered (armed with no deadline, so no real-time budget races the setup). Every question must
    then end with the failure event while the query is still stalled: the lookups still queued are
    dropped and never run, and the ones holding a thread finish after the stall, each closing its own
    session, so the pool is left with only the holder's connection.
    """
    threads = copilot_chat._LOOKUP_THREADS._max_workers
    questions = 2 * threads
    engine = _pool_with_revenue(tmp_path, pool_size=2, pool_timeout=STALL_S)
    stall, stalled = threading.Event(), threading.Event()

    def stalled_query(*_):
        stalled.set()  # this lookup holds its connection until the stall ends
        stall.wait(STALL_S)

    event.listen(engine, "before_cursor_execute", stalled_query)

    opened: list[Session] = []
    closed: set[int] = set()
    running = threading.Event()

    class ObservedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            opened.append(self)  # run_tool opens its session first
            if len(opened) == threads:
                running.set()

        def close(self):
            closed.add(id(self))
            super().close()

    submitted = []
    all_submitted = asyncio.Event()

    class RecordingExecutor(ThreadPoolExecutor):
        def submit(self, fn, /, *args, **kwargs):  # run_in_executor calls it on the loop thread
            submitted.append(super().submit(fn, *args, **kwargs))
            if len(submitted) == questions:
                all_submitted.set()
            return submitted[-1]

    class RecordedTimeout:
        """A real ``asyncio`` timeout armed with no deadline; it keeps the one it was asked for."""

        def __init__(self, when):
            self.when, self.task, self.open = when, asyncio.current_task(), False
            self.timeout = asyncio.timeout_at(None)

        async def __aenter__(self):
            await self.timeout.__aenter__()
            self.open = True

        async def __aexit__(self, *exc_info):
            self.open = False
            return await self.timeout.__aexit__(*exc_info)

    timers: list[RecordedTimeout] = []
    question_deadlines = {}  # question task -> the deadline answer_filing_question computed for it

    def timeout_at(when):
        timers.append(RecordedTimeout(when))
        return timers[-1]

    def chat_deadline():
        question_deadlines[asyncio.current_task()] = copilot_chat.chat_deadline()
        return question_deadlines[asyncio.current_task()]

    # A stand-in of the same size records each lookup's future, so the test sees which ones never ran.
    executor = RecordingExecutor(max_workers=threads)
    monkeypatch.setattr(copilot_chat, "_LOOKUP_THREADS", executor)
    monkeypatch.setattr(copilot_chat, "asyncio", SimpleNamespace(**{**vars(asyncio), "timeout_at": timeout_at}))
    monkeypatch.setattr(copilot_service, "chat_deadline", chat_deadline)
    monkeypatch.setattr(copilot_tools, "SessionLocal", sessionmaker(bind=engine, class_=ObservedSession))
    sent: list[list[dict]] = []
    monkeypatch.setattr(openai_service, "client", _fake_client([TOOL_ROUNDS[0]] * questions, sent))

    loop = asyncio.get_running_loop()
    holder_db = sessionmaker(bind=engine)()
    holder_db.connection()
    try:
        asked = [asyncio.create_task(_collect(_viewed_filing())) for _ in range(questions)]
        try:
            await asyncio.wait_for(all_submitted.wait(), HANG_GUARD_S)
            assert await asyncio.to_thread(running.wait, HANG_GUARD_S), "the running lookups never started"
            assert await asyncio.to_thread(stalled.wait, HANG_GUARD_S), "no lookup reached its query"
            waits = [timer for timer in timers if timer.open]
            for timer in waits:
                timer.timeout.reschedule(loop.time())  # the question's deadline passes
            # The query is still stalled: no question may wait for a lookup that holds a thread.
            answers = await asyncio.wait_for(asyncio.gather(*asked), HANG_GUARD_S)
            checked_out_when_over = engine.pool.checkedout()
        finally:
            for task in asked:
                task.cancel()
            stall.set()  # the database answers: every lookup holding a thread can finish
            await asyncio.gather(*asked, return_exceptions=True)
            await asyncio.to_thread(executor.shutdown)
        checked_out_after = engine.pool.checkedout()
    finally:
        holder_db.close()
        engine.dispose()

    # The production code armed each question's lookup wait with that question's own deadline.
    whens = [timer.when for timer in waits]
    assert len(whens) == len(question_deadlines) == questions
    assert None not in whens and whens == [question_deadlines[timer.task] for timer in waits]
    # (1) No lookup started after the deadline: the ones still queued for a thread were cancelled, and
    # none ran even once the stall freed the threads.
    assert [future.cancelled() for future in submitted].count(True) == questions - threads
    assert len(opened) == threads
    # (2) Every question ended with the failure event without waiting for a stalled lookup, asking the
    # model once: no regeneration, and no round after the abandoned lookup.
    assert [events[-1] for events in answers] == [
        {"type": "error", "message": copilot_service._STREAM_FAILURE}
    ] * questions
    assert len(sent) == questions
    # (3) A running lookup held a connection when the questions ended; it and the lookups waiting for
    # it finished, each closing its own session, and only the holder's connection is still out.
    assert checked_out_when_over == 2
    assert all("error" not in future.result() for future in submitted if not future.cancelled())
    assert {id(session) for session in opened} <= closed
    assert checked_out_after == 1


async def _collect(filing: SimpleNamespace) -> list[dict]:
    return [e async for e in copilot_service.answer_filing_question(filing=filing, question="What was revenue?")]


def _pool_with_revenue(tmp_path, pool_size: int, pool_timeout: float = POOL_TIMEOUT):
    """A ``QueuePool`` engine of ``pool_size`` connections over a database holding the filing's revenue."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'copilot-pool.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout=pool_timeout,
    )
    FinancialFact.__table__.create(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(FinancialFact(
            company_id=COMPANY_ID, concept="revenue", raw_tag="us-gaap:Revenues", unit="USD",
            period_start=date(2024, 1, 1), period_end=date(2024, 12, 31), fiscal_year=2024,
            fiscal_period="FY", value=100_000_000, form="10-K", accession=ACC,
            source="edgar_xbrl", reconciled=True, is_latest=True,
        ))
        db.commit()
    return engine
