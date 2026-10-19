"""Gate for E129 (lessons/ops-release-cached-filing-reads-before-yield.md): the companyfacts sync works
every session on threads of its own.

The coverage route runs ``ingest_companyfacts_by_id`` as a task on the API's event loop. Its
freshness read and its follower's re-read checked a connection out there, and its persist (the
normalize and the bulk upsert of every fact) ran there in full, blocking the loop for the whole run.

- A leader and a follower work no session on the loop: every checkout and every statement runs on
  the sync's own threads (``sync_threads._SYNC_THREADS``).
- Nor in the loop's default executor. A slot holder shaped like login keeps its connection checked
  out while it awaits a default-executor thread, so a sync waiting there for the slot would hold
  the thread the holder needs, and neither could move until the pool timed out
  (``copilot_chat._LOOKUP_THREADS`` keeps the Copilot's lookups off it for the same reason).
- The leader claims the sync before its freshness read, which now waits on a thread, so a request
  arriving meanwhile follows it; read first, a leader finishing during that read would leave it a
  stale stamp and no claim to follow, and it would lead a second fetch.
- A leader cancelled during its persist (the coverage route cancels at its wait budget) keeps its
  claim until the persist thread finishes, so no follower wakes and no second leader starts while
  the facts are still being written. That holds under an anyio cancel scope too, which cancels the
  task again at every loop step, and a persist that fails meanwhile is logged: the route's gather
  swallows the cancellation, the only outcome its caller sees.
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import anyio
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.models import Base, Company
from app.services import facts_service
from app.services.facts import ingest, sync_threads

SYNC_THREAD = "companyfacts_sync"
# Generous: the sync gets its slot as soon as the loop runs the holder. Only a sync waiting in the
# default executor ever waits this long, and it then fails on the pool's timeout.
POOL_TIMEOUT = 2.0
HANG_GUARD_S = 5.0  # a passing run never waits for it


def _payload() -> dict:
    return {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [{
                            "val": 100_000_000, "start": "2024-01-01", "end": "2024-12-31",
                            "accn": "0001326801-25-000001", "fy": 2024, "fp": "FY", "form": "10-K",
                            "filed": "2025-02-01",
                        }]
                    }
                }
            }
        }
    }


@pytest.fixture
def inflight():
    """The per-process in-flight dict, emptied for the test and restored after, in place."""
    saved = dict(facts_service._inflight_syncs)
    facts_service._inflight_syncs.clear()
    yield facts_service._inflight_syncs
    facts_service._inflight_syncs.clear()
    facts_service._inflight_syncs.update(saved)


@pytest.fixture(autouse=True)
def fresh_sync_threads(monkeypatch):
    """The sync's threads, of the production size and name and fresh for each test, so a thread a
    failing test leaves blocked cannot hold up the next one."""
    threads = ThreadPoolExecutor(max_workers=sync_threads._SYNC_THREADS._max_workers, thread_name_prefix=SYNC_THREAD)
    monkeypatch.setattr(sync_threads, "_SYNC_THREADS", threads)
    yield threads
    threads.shutdown(wait=False, cancel_futures=True)


def _engine(tmp_path, *, pool_size: int, pool_timeout: float):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'companyfacts-sync.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout=pool_timeout,
    )
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(Company(cik="0001326801", ticker="META", name="Meta Platforms"))
        db.commit()
    return engine


@pytest.fixture
def engine(tmp_path):
    engine = _engine(tmp_path, pool_size=4, pool_timeout=1.0)
    yield engine
    engine.dispose()


def _sync(engine, fetch):
    return facts_service.ingest_companyfacts_by_id(1, session_factory=sessionmaker(bind=engine), fetcher=fetch)


@pytest.mark.asyncio
async def test_a_sync_and_its_follower_work_every_session_on_the_syncs_threads(engine, inflight):
    seen: list[tuple[str, str]] = []
    event.listen(engine, "checkout", lambda *_: seen.append(("checkout", threading.current_thread().name)))
    event.listen(engine, "before_cursor_execute",
                 lambda *_: seen.append(("statement", threading.current_thread().name)))
    fetching = asyncio.Event()
    release = asyncio.Event()
    fetches = 0

    async def fetch(_cik):
        nonlocal fetches
        fetches += 1
        fetching.set()
        await release.wait()
        return _payload()

    leader = asyncio.create_task(_sync(engine, fetch))
    await asyncio.wait_for(fetching.wait(), timeout=2.0)
    follower = asyncio.create_task(_sync(engine, fetch))
    await asyncio.sleep(0.05)  # the follower's first step: it finds the claim and waits on it
    release.set()
    led, followed = await asyncio.wait_for(asyncio.gather(leader, follower), timeout=5.0)

    assert (led["synced"], led["refreshed"], led["inserted"]) == (True, True, 1)
    assert (followed["synced"], followed.get("waited"), fetches) == (True, True, 1)
    # The leader's read and persist and the follower's re-read each checked out and ran their
    # statements on the sync's threads: none on the loop, none in its default executor.
    assert {kind for kind, _ in seen} == {"checkout", "statement"}
    assert [name.startswith(SYNC_THREAD) for _, name in seen] == [True] * len(seen), seen
    assert engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_a_sync_waiting_for_a_slot_lets_a_login_shaped_holder_finish(tmp_path, inflight):
    """Another request holds the pool's only slot and, like login awaiting bcrypt, needs a
    default-executor thread before it gives the slot back. The loop's default executor has one
    thread here, standing in for one whose threads are all taken: a sync waiting for the slot there
    would hold that thread until the pool timed out. The holder must release first, and the sync
    then check out on its own thread and finish."""
    engine = _engine(tmp_path, pool_size=1, pool_timeout=POOL_TIMEOUT)
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1))  # the test's loop closes it at teardown
    release_holder = asyncio.Event()
    order: list[str] = []

    class ObservedSession(Session):
        def get(self, *args, **kwargs):
            # The sync is about to wait on the only connection. Its holder can give the slot back
            # as soon as the event loop is free to run this callback.
            loop.call_soon_threadsafe(release_holder.set)
            return super().get(*args, **kwargs)

    holder_db = sessionmaker(bind=engine)()
    holder_db.connection()
    assert engine.pool.checkedout() == 1
    event.listen(engine, "checkout", lambda *_: order.append(f"checkout on {threading.current_thread().name}"))

    async def holder():
        await release_holder.wait()
        await asyncio.to_thread(lambda: None)  # login's bcrypt, its connection still checked out
        order.append("holder releasing")  # before close(): the waiting sync may check out at once
        holder_db.close()

    async def fetch(_cik):
        return _payload()

    hold = asyncio.create_task(holder())
    try:
        result = await asyncio.wait_for(facts_service.ingest_companyfacts_by_id(
            1, session_factory=sessionmaker(bind=engine, class_=ObservedSession), fetcher=fetch,
        ), timeout=HANG_GUARD_S)
        await asyncio.wait_for(hold, timeout=HANG_GUARD_S)
    finally:
        release_holder.set()
        await hold
        holder_db.close()
        engine.dispose()

    assert (result["synced"], result["refreshed"], result["inserted"]) == (True, True, 1)
    # The loop ran the holder while the sync waited, so the slot came back before the sync's first
    # checkout. The sync then checked out once for its read and once for its persist, which reads
    # nothing back after its commit, each on the sync's own threads.
    assert order[0] == "holder releasing", order
    assert [entry.startswith(f"checkout on {SYNC_THREAD}") for entry in order[1:]] == [True, True], order


@pytest.mark.asyncio
async def test_a_request_arriving_during_the_leaders_sync_follows_it(engine, inflight, monkeypatch):
    """A second request's freshness read, were it to read first, would block until the leader had
    finished, see the stamp as it was before the leader's persist, find no claim, and lead again."""
    leader_done = threading.Event()
    real_fresh_check = ingest._companyfacts_fresh_result
    fresh_checks = 0

    def fresh_check(*args, **kwargs):
        nonlocal fresh_checks
        fresh_checks += 1
        if fresh_checks > 1:
            leader_done.wait(5)
        return real_fresh_check(*args, **kwargs)

    monkeypatch.setattr(ingest, "_companyfacts_fresh_result", fresh_check)
    fetching = asyncio.Event()
    release = asyncio.Event()
    fetches = 0

    async def fetch(_cik):
        nonlocal fetches
        fetches += 1
        fetching.set()
        await release.wait()
        return _payload()

    leader = asyncio.create_task(_sync(engine, fetch))
    await asyncio.wait_for(fetching.wait(), timeout=2.0)
    second = asyncio.create_task(_sync(engine, fetch))
    await asyncio.sleep(0.05)
    release.set()
    led = await asyncio.wait_for(leader, timeout=5.0)
    leader_done.set()
    followed = await asyncio.wait_for(second, timeout=5.0)

    assert led["refreshed"] is True
    assert (followed["synced"], followed.get("waited"), fetches, fresh_checks) == (True, True, 1, 1)


def _persist_held_until(finish: threading.Event, persisting: threading.Event, *, fail: bool):
    real_persist = ingest._persist_companyfacts_payload

    def held_persist(db, company, payload):
        persisting.set()
        finish.wait(5)
        if fail:
            raise RuntimeError("the bulk upsert failed")
        return real_persist(db, company, payload)

    return held_persist


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", ["task_cancel", "cancel_scope"])
async def test_a_cancelled_leader_keeps_its_claim_until_its_persist_finishes(engine, inflight, monkeypatch, cancel):
    """Cancelled once by ``Task.cancel()``, as the coverage route does, or through an anyio cancel
    scope, which cancels the task again at every loop step until it leaves the scope."""
    persisting, finish = threading.Event(), threading.Event()
    monkeypatch.setattr(ingest, "_persist_companyfacts_payload", _persist_held_until(finish, persisting, fail=False))

    async def fetch(_cik):
        return _payload()

    scope = anyio.CancelScope()

    async def lead_in_scope():
        with scope:
            return await _sync(engine, fetch)

    leader = asyncio.create_task(lead_in_scope() if cancel == "cancel_scope" else _sync(engine, fetch))
    assert await asyncio.wait_for(asyncio.to_thread(persisting.wait, 5), timeout=6.0)
    claim = inflight[1]
    if cancel == "cancel_scope":
        scope.cancel()
    else:
        leader.cancel()
    await asyncio.sleep(0.05)
    # The persist is still writing: the claim holds and is unset, so nothing follows or leads yet.
    assert (inflight.get(1) is claim, claim.is_set(), leader.done()) == (True, False, False)

    finish.set()
    if cancel == "cancel_scope":
        assert await asyncio.wait_for(leader, timeout=5.0) is None  # the scope took its cancellation
    else:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(leader, timeout=5.0)
    assert claim.is_set() and 1 not in inflight
    with sessionmaker(bind=engine)() as db:
        assert db.get(Company, 1).facts_synced_at is not None  # the persist committed
    assert engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_a_persist_failing_after_its_leader_was_cancelled_is_logged(engine, inflight, monkeypatch, caplog):
    persisting, finish = threading.Event(), threading.Event()
    monkeypatch.setattr(ingest, "_persist_companyfacts_payload", _persist_held_until(finish, persisting, fail=True))

    async def fetch(_cik):
        return _payload()

    leader = asyncio.create_task(_sync(engine, fetch))
    assert await asyncio.wait_for(asyncio.to_thread(persisting.wait, 5), timeout=6.0)
    leader.cancel()
    await asyncio.sleep(0.05)
    finish.set()
    with caplog.at_level(logging.ERROR, logger="app.services.facts_service"):
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(leader, timeout=5.0)

    failures = [record for record in caplog.records if "after its caller was cancelled" in record.getMessage()]
    assert [type(record.exc_info[1]) for record in failures] == [RuntimeError]
    assert 1 not in inflight
    with sessionmaker(bind=engine)() as db:
        assert db.get(Company, 1).facts_synced_at is None  # nothing committed, so a retry fetches again
