"""
Pytest configuration for EarningsNerd backend tests.

Provides shared fixtures and markers for all test suites.
"""

import atexit
import os
import shutil
import sys
import tempfile
from copy import deepcopy
from unittest.mock import NonCallableMock

# Every pytest process owns a private SQLite database in a fresh temp directory: one per session,
# and under pytest-xdist one per worker (each worker is its own process and imports this file).
# Set before any app import, so Settings reads it and app.database binds its engine to it. No test
# touches backend/earningsnerd.db (the dev server's default), two runs in one worktree never share
# a file, and every run starts from the current schema (create_all never ALTERs a stale file).
# Unconditional like the keys below: a developer's own DATABASE_URL must never reach the suite.
# Removed in pytest_unconfigure, or at exit when pytest stops before configuring (a usage error).
# Gate: tests/unit/test_suite_isolation.py.
_TEST_DB_DIR = tempfile.mkdtemp(prefix=f"earningsnerd-tests-{os.environ.get('PYTEST_XDIST_WORKER', 'main')}-")
atexit.register(shutil.rmtree, _TEST_DB_DIR, ignore_errors=True)
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TEST_DB_DIR, "earningsnerd.db")

# Set mock environment variables for all tests at module level to avoid Pydantic validation errors at import time
os.environ["SECRET_KEY"] = "test-secret-key-must-be-long-enough-123"
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_mock_stripe_key_12345"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_mock_stripe_webhook_12345"

# Skip Redis initialization in tests - prevents 3+ second timeout per test
os.environ["SKIP_REDIS_INIT"] = "true"

# Disable the HaveIBeenPwned network call in tests so the suite stays hermetic and offline.
os.environ["PWNED_PASSWORD_CHECK_ENABLED"] = "false"

# NOTE: custom markers are registered in backend/pytest.ini (single source of test config).
# Shared fixtures are added below as the Wave 0 characterization anchors are written and a
# fixture is repeated across ≥2 of them.



import pytest  # noqa: E402
from sqlalchemy import Table, event  # noqa: E402

from tests.support.summary_stream_harness import CANONICAL_PAYLOAD  # noqa: E402

_PRISTINE_CANONICAL_PAYLOAD = deepcopy(CANONICAL_PAYLOAD)


@event.listens_for(Table, "before_create")
def _sqlite_never_reuses_ids(table, connection, **kw):
    """Every SQLite table the suite creates gets AUTOINCREMENT ids, as PostgreSQL sequences behave.

    Without it SQLite hands out max(rowid)+1, so deleting a test's newest parent frees its id for the
    next test. SQLite here enforces no foreign keys, so a child row the first test left behind (a
    ``filing_content_cache`` row for its filing, say) then belongs to the next test's new filing and
    silently reroutes that test. Covers the shared engine and every engine a test creates. Only a
    single-column key SQLite renders as INTEGER qualifies (SQLite rejects AUTOINCREMENT on BIGINT
    or SMALLINT keys); composite and other keys keep SQLite's default.
    """
    if connection.dialect.name != "sqlite":
        return
    key = list(table.primary_key.columns)
    if len(key) == 1 and key[0].type.compile(dialect=connection.dialect) == "INTEGER":
        table.dialect_options["sqlite"]["autoincrement"] = True


def pytest_unconfigure(config):
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def _warm_openai_sdk():
    """Pay the OpenAI SDK's first-request cost before any test, not inside one.

    A process's first SDK request costs about 60-70 ms on a quiet machine (lazy imports, response
    model setup, a platform probe in a thread) and about 2 ms afterwards, for any client. Whichever
    test made the first request paid it inside its own real-time budget, so tight provider deadlines
    passed or failed by test order. One offline plain and one streamed completion warm the process;
    the first probe in ``tests/unit/test_suite_isolation.py`` checks it ran.
    """
    import asyncio
    import json

    import httpx2
    from openai import AsyncOpenAI

    base = {"id": "warm", "created": 1, "model": "warm"}
    chunk = {**base, "object": "chat.completion.chunk",
             "choices": [{"index": 0, "delta": {"content": "w"}, "finish_reason": None}]}
    completion = {**base, "object": "chat.completion",
                  "choices": [{"index": 0, "message": {"role": "assistant", "content": "w"}, "finish_reason": "stop"}]}

    def respond(request):
        if json.loads(request.content).get("stream"):
            body = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body)
        return httpx2.Response(200, json=completion)

    async def warm():
        async with AsyncOpenAI(api_key="offline-warm", base_url="https://warm.invalid/v1", max_retries=0,
                               http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond))) as client:
            await client.chat.completions.create(model="warm", messages=[])
            stream = await client.chat.completions.create(model="warm", messages=[], stream=True)
            async for _ in stream:
                pass

    asyncio.run(warm())


@pytest.fixture(scope="session", autouse=True)
def _suite_schema():
    """Each process's fresh database starts with the current schema, as the app's startup gives it.

    Tests that write through ``SessionLocal`` without creating tables (``test_copilot_tools.py``,
    and every file that relies on ``TestClient(app)`` running the lifespan first) otherwise depend
    on an earlier test in the same process having created them.
    """
    import app.models  # noqa: F401 — registers every table on Base.metadata
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _reset_delivery_ownership():
    """Durable delivery ownership rows (E11b-1) must not leak between tests.

    SQLite enforces no foreign keys here, while several existing scenarios bulk-delete their users
    and filings in teardown; before ``_sqlite_never_reuses_ids`` SQLite also re-issued their ids, so
    an orphaned ``earningsnerd_delivery_items`` row claimed ownership of the next test's user/filing
    pair. PostgreSQL cascades these rows, so this is a test-isolation concern only.
    """
    from sqlalchemy import inspect, text

    from app.database import engine

    names = ("earningsnerd_delivery_items", "earningsnerd_delivery_batches", "earningsnerd_usage_reservations")
    present = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        for name in names:  # admission leases (E07b) are keyed by reused user ids too
            if name in present:
                conn.execute(text(f"DELETE FROM {name}"))  # nosec B608 - fixed table names
    yield


@pytest.fixture(autouse=True)
def _isolate_ai_call_trigger():
    """The ``ai_call`` trigger label must not leak between tests.

    Script entrypoints (``python -m evals.runner``, the weekly readouts, the Cloud Run job scripts)
    set it for their whole process and never reset it, and some tests execute those entrypoints
    in-process. Without this, every later test's calls log as ``eval``/``job``, and tests that
    assert the default pass or fail by collection order. Each test starts from the default and
    nothing it sets survives; the probe pair in ``tests/unit/test_ai_metrics.py`` pins this (run in
    order, in a fresh process, by ``tests/unit/test_suite_isolation.py``).
    """
    from app.services import ai_metrics

    token = ai_metrics.set_trigger("user")
    yield
    ai_metrics.reset_trigger(token)


@pytest.fixture(autouse=True)
def _pristine_canonical_payload():
    """``CANONICAL_PAYLOAD`` must not carry one test's pipeline output into the next.

    ``stream_boundaries`` and several tests (locked anchors among them) hand the module-level dict,
    or a shallow copy that shares its nested ``raw_summary``, to the pipeline, which finalizes the
    payload in place (``quality``, ``schema_version``, ``status`` ...). Every later generation in the
    process then started from that output instead of the canonical input. Restored after each test;
    the probe pair in ``tests/unit/test_suite_isolation.py`` pins this.
    """
    yield
    if CANONICAL_PAYLOAD != _PRISTINE_CANONICAL_PAYLOAD:
        _restore_in_place(CANONICAL_PAYLOAD, _PRISTINE_CANONICAL_PAYLOAD)


def _restore_in_place(live, pristine):
    """Put ``pristine``'s content back into ``live`` without replacing its nested containers, which
    module-level shallow copies (``{**CANONICAL_PAYLOAD, ...}``) still share."""
    if isinstance(live, list):
        live[:] = deepcopy(pristine)
        return
    for key in [key for key in live if key not in pristine]:
        del live[key]
    for key, value in pristine.items():
        if isinstance(value, (dict, list)) and type(live.get(key)) is type(value):
            _restore_in_place(live[key], value)
        else:
            live[key] = deepcopy(value)


@pytest.fixture(autouse=True)
def _no_mock_left_on_generation_singletons():
    """A test must not leave a mock on the generation pipeline's shared singletons.

    ``stream_boundaries`` patches seams on ``summary_pipeline``'s service singletons. Overriding one
    again with the function-scoped ``monkeypatch`` inside the block makes monkeypatch's teardown put
    the harness mock back after the harness restored production, for the rest of the process
    (``test_sec_rate_limiter`` then read the mock's canned text). Undo such overrides first, with
    ``monkeypatch.context()`` inside the block. A leak fails the leaking test's teardown and is
    restored; ``tests/unit/test_suite_isolation.py`` runs a leaking probe to prove it.
    """
    before = [(target, dict(vars(target))) for target in _generation_singletons()]
    seen = {id(target) for target, _ in before}
    yield
    # A module first imported during this test had no mocks before it.
    before += [(target, {}) for target in _generation_singletons() if id(target) not in seen]
    leaked = []
    for target, snapshot in before:
        for name, value in list(vars(target).items()):
            if isinstance(value, NonCallableMock) and snapshot.get(name) is not value:
                leaked.append(f"{getattr(target, '__name__', type(target).__name__)}.{name}")
                if name in snapshot:
                    setattr(target, name, snapshot[name])
                else:
                    delattr(target, name)
    if leaked:
        pytest.fail(f"mock left on a shared generation singleton after the test: {', '.join(leaked)}", pytrace=False)


def _generation_singletons():
    pipeline = sys.modules.get("app.services.summary_pipeline")
    if pipeline is None:
        return []
    return [pipeline, pipeline.sec_edgar_service, pipeline.xbrl_service, pipeline.openai_service]
