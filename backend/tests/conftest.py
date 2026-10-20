"""
Pytest configuration for EarningsNerd backend tests.

Makes every pytest process hermetic and order-independent: a private temp database and EdgarTools
directory per process (each xdist worker is one), pinned environment, the network gate, autouse
resets of process-wide state, and checks that no process the run starts gives git /dev/null as a file it
writes and that nothing in the run destroys /dev/null. Markers live in
backend/pytest.ini; gates for all of this are in tests/unit/test_suite_isolation.py
(lessons/ops-one-test-process-per-worktree.md).
"""

import atexit
import inspect
import os
import re
import shlex
import shutil
import stat
import subprocess
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


def _cleanup_test_database():
    # Windows cannot remove SQLite files while pooled connections still hold them open. Look up
    # an already-loaded module: a usage error can exit before app.database was ever imported.
    database = sys.modules.get("app.database")
    engine = getattr(database, "engine", None)
    if engine is not None:
        engine.dispose()
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


atexit.register(_cleanup_test_database)
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TEST_DB_DIR, "earningsnerd.db")

# EdgarTools keeps its data (EDGAR_LOCAL_DATA_DIR, default ~/.edgar: the HTTP cache and the markers of
# the cache migrations that importing it runs) and its caches (EDGAR_CACHE_DIR, default ~/.edgar_cache:
# the pickled anchors TOC extraction reuses) under the home directory, which every run and worker would
# share, and which a sandbox with a read-only home cannot write: TOC extraction then swallows the error
# and picks an incomplete fallback (lessons/test-conftest-hermetic-env.md). So each process gets its own,
# in the temp directory above, before any app import, and they go with it. A value set before pytest
# started (a developer's) is kept. A value a parent test process assigned is not: xdist's controller and a
# pytest started from a test pass theirs down in the environment, and EARNINGSNERD_TEST_EDGAR_DIRS names
# what this file assigned, so each worker and child takes its own. Gate: test_suite_isolation.py.
_INHERITED_EDGAR_DIRS = os.environ.get("EARNINGSNERD_TEST_EDGAR_DIRS", "").split(os.pathsep)
_ASSIGNED_EDGAR_DIRS = []
for _name, _subdir in (("EDGAR_LOCAL_DATA_DIR", "edgar"), ("EDGAR_CACHE_DIR", "edgar-cache")):
    if not os.environ.get(_name) or os.environ[_name] in _INHERITED_EDGAR_DIRS:
        os.environ[_name] = os.path.join(_TEST_DB_DIR, _subdir)
        _ASSIGNED_EDGAR_DIRS.append(os.environ[_name])
os.environ["EARNINGSNERD_TEST_EDGAR_DIRS"] = os.pathsep.join(_ASSIGNED_EDGAR_DIRS)

# Set mock environment variables for all tests at module level to avoid Pydantic validation errors at import time
os.environ["SECRET_KEY"] = "test-secret-key-must-be-long-enough-123"
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-mocking"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_mock_stripe_key_12345"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_mock_stripe_webhook_12345"

# Skip Redis initialization in tests - prevents 3+ second timeout per test
os.environ["SKIP_REDIS_INIT"] = "true"

# Disable the HaveIBeenPwned network call in tests so the suite stays hermetic and offline.
os.environ["PWNED_PASSWORD_CHECK_ENABLED"] = "false"

# A developer's backend/.env can carry live provider keys (telemetry, email, market data, bot checks);
# pinned empty here (env beats .env in Settings), Sentry's sender, PostHog, Resend, Alpha Vantage and
# Turnstile stay off in tests and never trip the network gate below or fail a request on a real key. A
# test that needs a key patches `settings`, as before. The list is kept by hand: pin a key here when a
# development .env value changes a test's outcome.
os.environ["SENTRY_DSN"] = ""
os.environ["POSTHOG_API_KEY"] = ""
os.environ["RESEND_API_KEY"] = ""
os.environ["ALPHA_VANTAGE_API_KEY"] = ""
os.environ["TURNSTILE_SECRET_KEY"] = ""

# Outbound-network gate (rule 12): any attempt to reach a non-loopback host fails the test that
# made it, or the session when no running test owns it. Pinned by tests/unit/test_network_gate.py.
pytest_plugins = ("tests.support.network_gate",)

# NOTE: custom markers are registered in backend/pytest.ini (single source of test config).
# The characterization anchors' shared helpers live in tests/support/summary_stream_harness.py.



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
    _cleanup_test_database()


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
def _isolate_summary_limiter():
    """Request allowances belong to one test, even when tests reuse a stand-in account id.

    Avoid importing a router for tests that do not use it. Check again at teardown because the
    running test may be the first to import it. The ordered probes in test_suite_isolation.py
    exhaust one account's allowance, then require an empty limiter in the next test.
    """
    def clear_loaded_limiter():
        summaries = sys.modules.get("app.routers.summaries")
        limiter = getattr(summaries, "SUMMARY_LIMITER", None)
        if limiter is not None:
            with limiter._lock:
                limiter._hits.clear()

    clear_loaded_limiter()
    yield
    clear_loaded_limiter()


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
    restored; ``tests/unit/test_suite_isolation.py`` runs a leaking probe to prove it. A method that
    monkeypatch's undo left pinned on a singleton is cleared too, covered by an ordered probe pair there.
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
    _clear_pinned_methods()
    if leaked:
        pytest.fail(f"mock left on a shared generation singleton after the test: {', '.join(leaked)}", pytrace=False)


def _generation_singletons():
    pipeline = sys.modules.get("app.services.summary_pipeline")
    if pipeline is None:
        return []
    return [pipeline, pipeline.sec_edgar_service, pipeline.xbrl_service, pipeline.openai_service]


def _service_singletons():
    """The shared service instances, looked up where they live: a test that imports them from
    ``app.services.edgar.compat`` never imports ``summary_pipeline``."""
    compat = sys.modules.get("app.services.edgar.compat")
    ai = sys.modules.get("app.services.openai_service")
    found = (getattr(compat, "sec_edgar_service", None), getattr(compat, "xbrl_service", None),
             getattr(ai, "openai_service", None))
    return [target for target in found if target is not None and not isinstance(target, NonCallableMock)]


def _clear_pinned_methods():
    # monkeypatch.setattr on an instance saves the old attribute with getattr, which returns a bound
    # method, and its undo sets that back on the instance: the class's own method, pinned there, where
    # it would shadow a later class-level patch in whichever tests ran after it; tests patch these
    # singletons this way across dozens of files. A pin behaves exactly like the class's method, so it
    # is cleared silently rather than failing the test.
    for target in _service_singletons():
        for name, value in list(vars(target).items()):
            if getattr(value, "__self__", None) is target and getattr(value, "__func__", None) is getattr(type(target), name, None):
                delattr(target, name)


# Whether /dev/null was the null device as the running test's current phase began.
_NULL_DEVICE_BEFORE = pytest.StashKey[bool]()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    item.stash[_NULL_DEVICE_BEFORE] = _is_character_device(os.devnull)  # read at each check: a child run swaps in a stand-in
    return (yield)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """A test must leave ``/dev/null`` the null device, through its setup, its body and its teardown.

    A session that runs as root (cloud sessions do) lets a tool given /dev/null as a file it writes replace
    it: a git config write through a ``GIT_CONFIG_GLOBAL`` naming it renames its lock file over it, and once
    it is an ordinary file every failed ``ld -o /dev/null`` (``ctypes.util.find_library``'s last fallback,
    which importing WeasyPrint reaches) unlinks it. Git and ``subprocess.DEVNULL`` then fail across the
    container. Each phase of a test whose span saw it stop being a character device fails here, a fixture of
    any scope included: pytest sets one up in the setup of the first test that uses it and tears it down in the
    teardown of the last. An ``xfail`` mark or a skip cannot absorb the failure (the network gate treats an
    attempt the same way). Under ``-n auto`` a test in another worker may share the blame, and
    ``pytest_sessionfinish`` fails the run for a loss outside every test (a module's import). Two child runs in
    ``tests/unit/test_suite_isolation.py`` replace a stand-in in each place to prove it
    (lessons/test-never-point-a-written-file-at-dev-null.md).
    """
    report = yield
    was_device = item.stash.get(_NULL_DEVICE_BEFORE, False)
    item.stash[_NULL_DEVICE_BEFORE] = _is_character_device(os.devnull)
    if was_device and not item.stash[_NULL_DEVICE_BEFORE]:
        text = (f"{os.devnull} stopped being the null device during this test ({call.when}) or in another worker: "
                "a tool replaced or removed it. Restore it before trusting this run; see "
                "lessons/test-never-point-a-written-file-at-dev-null.md")
        if report.failed:
            report.sections.append(("null device", text))
        else:  # passed, skipped or an xfail: losing the device is never an expected outcome
            try:
                pytest.fail(text, pytrace=False)
            except pytest.fail.Exception:  # a raised Failed gives the report a one-line reprcrash
                report.outcome, report.longrepr = "failed", item.repr_failure(pytest.ExceptionInfo.from_current())
            if hasattr(report, "wasxfail"):
                del report.wasxfail
    return report


def _is_character_device(path):
    try:
        return stat.S_ISCHR(os.stat(path).st_mode)
    except OSError:
        return False


_RUN_STARTED_WITH_THE_DEVICE = _is_character_device(os.devnull)


def pytest_sessionfinish(session):
    """The run fails when /dev/null is not the null device: when it started broken, which no check of a test can
    see, or when it stopped being the device during the run, wherever that happened: in a test (whose phase
    failed above), at a module's import, or in another worker."""
    if _null_device_fault() and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
    fault = _null_device_fault()
    if fault:
        terminalreporter.section(f"{os.devnull} {fault} -- session FAILED", sep="=", red=True, bold=True)
        terminalreporter.line("A tool replaced or removed it. Restore it before trusting this run; see "
                              "lessons/test-never-point-a-written-file-at-dev-null.md")


def _null_device_fault():
    if not _RUN_STARTED_WITH_THE_DEVICE:
        return "was not the null device when this run started"
    if not _is_character_device(os.devnull):
        return "stopped being the null device during this run"
    return None


# The variables that name a file git writes through a lock file it renames over the target.
_GIT_WRITE_TARGETS = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG", "GIT_INDEX_FILE")
# git config's file option as git's option parser reads it: `--file` or its abbreviation `--fil`, the file
# after `=` or in the next word; `-f`, alone or after other short options (`-zf`), the file attached or in the
# next word. tests/unit/test_null_device_write_targets.py reads source with the same pattern.
_CONFIG_FILE_OPTION = re.compile(r"--fil(?:e)?(?:=(?P<long>.*))?|-[a-eg-zA-Z]*f(?P<short>.*)")


def _install_git_null_guard():
    """No process this pytest process starts may give git the null device as a file it writes.

    ``tests/unit/test_null_device_write_targets.py`` reads the source; this sees each start, however its
    environment or arguments were built, on any runner: an environment whose ``GIT_CONFIG_GLOBAL``,
    ``GIT_CONFIG_SYSTEM``, ``GIT_CONFIG`` or ``GIT_INDEX_FILE`` names the device, a ``NAME=/dev/null`` word in
    a shell line, or git config's file option naming it (``--file``, ``-f``, attached or not; ``git config`` or
    the ``git-config`` program git runs for it), or, in a shell line, a word there that the shell expands as
    the line runs (``"$TARGET"``, a substitution), which may name it, in strings or
    byte strings, given by keyword or by position, a shell line alone or in a list. A path is read
    from the test's own directory; one that reaches the device only from another (a ``cwd=``, ``git -C``) is
    outside it. It is installed when conftest is imported, so a fixture of any
    scope is covered, and it wraps every way the standard library starts a program but fork and exec:
    ``subprocess.Popen`` (``subprocess.run``, ``os.popen`` and asyncio's subprocesses go through it),
    ``os.system``, ``os.posix_spawn``, ``os.posix_spawnp`` and ``os.spawnv`` with its siblings, and
    ``os.putenv``, which sets the environment later starts inherit without ``os.environ`` seeing it. The start
    (or the setting) fails before it happens. A process that
    a started process starts in turn is outside it, as are ``os.fork`` with an ``exec``, a git alias
    (``-c alias.x=config``) and a start this cannot read; the source gate and the null-device checks above stand
    behind them. A child run in
    ``tests/unit/test_suite_isolation.py`` proves each start (lessons/test-never-point-a-written-file-at-dev-null.md).
    """
    popen_init = subprocess.Popen.__init__
    if getattr(popen_init, "checks_git_null_targets", False):
        return  # installed already in this process

    parameters = inspect.signature(popen_init)

    def popen(self, *given, **options):
        start = parameters.bind(self, *given, **options).arguments  # env or shell given by position too
        _refuse_git_null_target(start["args"], start.get("env"), start.get("shell", False))
        popen_init(self, *given, **options)

    popen.checks_git_null_targets = True
    subprocess.Popen.__init__ = popen
    system = os.system

    def checked_system(command):
        _refuse_git_null_target(command, None)
        return system(command)

    os.system = checked_system
    putenv = os.putenv

    def checked_putenv(key, value):  # os.environ's own writes come through here too
        _refuse_git_null_target([], {key: value}, what="the environment set here")
        putenv(key, value)

    os.putenv = checked_putenv
    for name in ("posix_spawn", "posix_spawnp"):
        spawn = getattr(os, name, None)
        if spawn is not None:
            setattr(os, name, _checked_spawn(spawn))
    for name in ("spawnv", "spawnve", "spawnvp", "spawnvpe"):  # os.spawnl and its siblings call these
        spawn = getattr(os, name, None)
        if spawn is not None:
            setattr(os, name, _checked_os_spawn(spawn))


def _checked_spawn(spawn):
    def checked(path, argv, env, *more, **options):
        _refuse_git_null_target(argv, env)
        return spawn(path, argv, env, *more, **options)

    return checked


def _checked_os_spawn(spawn):
    def checked(mode, file, args, *env):  # the spawnv*e forms take an environment
        _refuse_git_null_target(args, env[0] if env else None)
        return spawn(mode, file, args, *env)

    return checked


def _names_git_config(word):
    """Whether a word of a start is git's config command: `config` after git, or the `git-config` program git
    keeps in its exec path for it."""
    return word == "config" or os.path.basename(word) == "git-config"


def _expands(word):
    """Whether a shell expands this word as its line runs (a variable, a substitution), so that it may name any
    file, the device included."""
    return bool(word) and ("$" in word or "`" in word)


def _refuse_git_null_target(args, env, shell=False, what="a process started here"):
    given = _git_null_target(args, env, shell)
    if given:
        pytest.fail(f"{what} would give git the null device to write ({given}): as root, git "
                    "renames its lock file over the device. Give git an empty file in the test's temp directory "
                    "instead (lessons/test-never-point-a-written-file-at-dev-null.md)", pytrace=False)


def _git_null_target(args, env, shell=False):
    """What in a process's start gives git the null device to write, or None."""
    try:
        null = os.path.realpath(os.devnull)

        def names_null(value):
            return bool(value) and os.path.realpath(os.fsdecode(value)) == null

        for key, value in (os.environ if env is None else env).items():
            name = os.fsdecode(key)  # a byte-string key names the same variable
            if name in _GIT_WRITE_TARGETS and names_null(value):
                return f"{name}={os.fsdecode(value)} in its environment"
        items = [args] if isinstance(args, (str, bytes)) else list(args)
        shell_lines = shell or isinstance(args, (str, bytes))  # with shell=True a list's words are shell lines
        words = [word for item in items
                 for word in (shlex.split(os.fsdecode(item)) if shell_lines else [os.fsdecode(item)])]
        for index, word in enumerate(words):
            name, equals, value = word.partition("=")
            if equals and name in _GIT_WRITE_TARGETS and (names_null(value) or shell_lines and _expands(value)):
                return word
            option = _CONFIG_FILE_OPTION.fullmatch(word) if any(map(_names_git_config, words[:index])) else None
            if option:
                attached = option["long"] or option["short"]
                given = attached or (words[index + 1] if index + 1 < len(words) else None)
                if names_null(given) or shell_lines and _expands(given):
                    return f"config {word}" + ("" if attached else f" {given}")
    except (TypeError, ValueError, OSError):
        return None
    return None


_install_git_null_guard()


# Stream tests that drive the real ``stream_filing_summary`` with a mocked 10-K (CIK 1234567890)
# but patch only the document fetch and the AI call. The pipeline also starts its two
# edgartools-backed enrichment seams, and offline those reached data.sec.gov / www.sec.gov
# (submissions JSON, companyfacts fallback). These tests time heartbeats and fetch latency, not
# enrichment, so stub exactly those seams, as tests/support/summary_stream_harness.py does for the
# anchors. The list is explicit so no test that exercises enrichment is silently stubbed; the files
# themselves stay unedited.
_OFFLINE_ENRICHMENT_FILES = frozenset({
    "integration/test_summary_stream_heartbeat.py",
    "integration/test_stream_latency.py",
    "performance/test_concurrent_streams.py",
})


@pytest.fixture(autouse=True)
def _offline_stream_enrichment(request):
    if f"{request.path.parent.name}/{request.path.name}" not in _OFFLINE_ENRICHMENT_FILES:
        yield
        return
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, patch

    from app.services import summary_pipeline

    with ExitStack() as stack:
        for seam in ("get_xbrl_data", "get_filing_sections"):
            # patch.object (not monkeypatch) deletes the instance attribute on exit, so nothing
            # is left behind on the shared xbrl_service singleton.
            stack.enter_context(patch.object(summary_pipeline.xbrl_service, seam, AsyncMock(return_value=None)))
        yield
