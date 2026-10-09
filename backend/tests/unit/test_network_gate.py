"""The outbound-network gate (tests/support/network_gate.py) proves itself (CLAUDE.md rule 12).

In-process: the gate is wired into THIS session by tests/conftest.py and blocks + reports an
attempt. Subprocess (pytester): a swallowed attempt FAILS the test that made it -- from the main
thread, through httpx, from an executor worker, from an asyncio task (also one scheduled on a loop
another test started), in fixture setup and teardown, and despite a skip or an xfail; loopback,
AF_UNIX and the in-process ASGI transport still pass; a thread that outlives its test, and an
attempt made after a test's last report, fail the session; and a configured loopback proxy is
neutralised and caught. Every target is a reserved name (``.invalid``) or a documentation address
(192.0.2.0/24), and the gate blocks before any query.
"""

import ast
import socket
from pathlib import Path

import pytest

pytest_plugins = ("pytester",)

TESTS = Path(__file__).resolve().parents[1]
GATE_SOURCE = (TESTS / "support" / "network_gate.py").read_text()
# The children rely on in-file order (a pool warmed, a loop started, a thread left running).
CHILD_ARGS = ("-p", "no:cacheprovider", "-p", "no:randomly")
# Rule-6 anchors (lessons/test-contract-tests-are-locked.md, tasks/architecture-refactor-plan.md).
LOCKED_ANCHORS = {
    "integration/test_summary_stream_contract.py", "unit/test_background_generation_characterization.py",
    "unit/test_auth_flow.py", "unit/test_stripe_webhook.py", "unit/test_subscription_webhook_sync.py",
    "unit/test_generation_requires_account.py", "unit/test_expired_trial_gating.py", "unit/test_filing_scan.py",
    "unit/test_refresh_replay.py", "unit/test_companyfacts_fixture.py",
}

INNER_TESTS = '''
import asyncio, os, socket, threading, time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

POOL = ThreadPoolExecutor(max_workers=1)


def test_dns_swallowed_fails():
    try:
        socket.getaddrinfo("gate-selftest-dns.invalid", 443)
    except OSError:
        pass


def test_ip_connect_swallowed_fails():
    try:
        socket.create_connection(("192.0.2.1", 443), timeout=0.05).close()
    except OSError:
        pass


def test_httpx_swallowed_fails():
    try:
        httpx.get("https://gate-selftest-httpx.invalid/", timeout=0.5)
    except httpx.HTTPError:
        pass


def test_udp_sendmsg_swallowed_fails():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        try:
            udp.sendmsg([b"x"], [], 0, ("192.0.2.1", 9))
        except OSError:
            pass


def test_pool_warm_passes():
    assert POOL.submit(lambda: 1).result() == 1  # the worker thread is created by THIS test


def test_pool_work_from_later_test_fails():
    def lookup():
        try:
            socket.getaddrinfo("gate-selftest-pool.invalid", 443)
        except OSError:
            pass
    POOL.submit(lookup).result()


@pytest.mark.asyncio
async def test_asyncio_lookup_swallowed_fails():
    try:
        await asyncio.get_running_loop().getaddrinfo("gate-selftest-asyncio.invalid", 443)
    except OSError:
        pass


@pytest.fixture
def setup_attempt():
    try:
        socket.getaddrinfo("gate-selftest-setup.invalid", 443)
    except OSError:
        pass
    yield


@pytest.fixture
def teardown_attempt():
    yield
    try:
        socket.getaddrinfo("gate-selftest-teardown.invalid", 443)
    except OSError:
        pass


def test_setup_attempt_errors(setup_attempt):
    pass


def test_teardown_attempt_errors(teardown_attempt):
    pass


def test_skip_after_attempt_fails():
    try:
        socket.getaddrinfo("gate-selftest-skip.invalid", 443)
    except OSError:
        pytest.skip("offline")


@pytest.mark.xfail(reason="an attempt is never an expected outcome")
def test_xfail_with_attempt_fails():
    try:
        socket.getaddrinfo("gate-selftest-xfail.invalid", 443)
    except OSError:
        pass
    assert False


@pytest.fixture(scope="module")
def background_loop():
    loop, pool = asyncio.new_event_loop(), ThreadPoolExecutor(max_workers=1)
    pool.submit(loop.run_forever)  # the loop thread carries the executor tag of the test that set it up
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    pool.shutdown(wait=True)
    loop.close()


def test_loop_started_here_passes(background_loop):
    assert asyncio.run_coroutine_threadsafe(asyncio.sleep(0, result=1), background_loop).result(5) == 1


def test_task_on_another_tests_loop_fails(background_loop):
    async def lookup():
        try:
            socket.getaddrinfo("gate-selftest-portal.invalid", 443)
        except OSError:
            pass
    asyncio.run_coroutine_threadsafe(lookup(), background_loop).result(5)


def test_loopback_and_unix_pass(tmp_path):
    server = socket.create_server(("127.0.0.1", 0))
    with server, socket.create_connection(server.getsockname(), timeout=2):
        pass
    left, right = socket.socketpair()
    with left, right:
        left.sendall(b"ok")
        assert right.recv(2) == b"ok"
    socket.getaddrinfo("localhost", 80)


def test_in_process_asgi_passes():
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    app = Starlette(routes=[Route("/", lambda request: PlainTextResponse("ok"))])
    assert TestClient(app).get("/").text == "ok"


def test_proxy_is_neutralised_and_caught():
    assert not any(k.lower() in ("https_proxy", "http_proxy", "all_proxy") for k in os.environ)
    assert os.environ["NO_PROXY"] == "*"
    port = int(os.environ["GATE_SELFTEST_PROXY_PORT"])
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
    except OSError:
        pass
'''

LATE_HOOK = '''

def pytest_runtest_logfinish(nodeid, location):  # after the test's last report, while it is running
    if nodeid.endswith("::test_late"):
        try:
            socket.getaddrinfo("gate-selftest-late.invalid", 443)
        except OSError:
            pass
'''

STRAY_TESTS = '''
import socket, threading

GO, DONE = threading.Event(), threading.Event()  # the stray fires exactly while the second test runs


def test_starts_a_thread_that_outlives_it():
    def late():
        GO.wait(10)
        try:
            socket.getaddrinfo("gate-selftest-stray.invalid", 443)
        except OSError:
            pass
        DONE.set()
    threading.Thread(target=late, name="late-worker", daemon=True).start()


def test_runs_while_the_stray_fires():
    GO.set()
    assert DONE.wait(10)


def test_late():
    pass
'''


def test_gate_is_wired_into_this_session(request: pytest.FixtureRequest) -> None:
    gate = request.config.pluginmanager.get_plugin("tests.support.network_gate")
    assert gate is not None, "tests/conftest.py must register tests.support.network_gate"
    with gate.expect_blocked() as caught:
        with pytest.raises(OSError, match="network gate: blocked DNS lookup"):
            socket.getaddrinfo("gate-selftest-inprocess.invalid", 443)
    assert [(a.kind, a.target, a.owner) for a in caught] == [
        ("dns", "gate-selftest-inprocess.invalid:443", request.node.nodeid)
    ]
    with gate.expect_blocked() as caught:  # a reverse lookup of a non-local address is a query too
        with pytest.raises(OSError, match="network gate: blocked DNS lookup of reverse 192.0.2.1"):
            socket.getnameinfo(("192.0.2.1", 443), 0)
    numeric = socket.NI_NUMERICHOST | socket.NI_NUMERICSERV  # asks for no query, so it passes
    assert socket.getnameinfo(("192.0.2.1", 443), numeric) == ("192.0.2.1", "443")


def test_swallowed_attempts_fail_their_test_and_local_traffic_passes(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytester.makeconftest(GATE_SOURCE)
    pytester.makepyfile(test_inner=INNER_TESTS)
    listener = socket.create_server(("127.0.0.1", 0))  # stands in for a local HTTPS proxy
    with listener:
        port = listener.getsockname()[1]
        monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{port}")
        monkeypatch.setenv("GATE_SELFTEST_PROXY_PORT", str(port))
        result = pytester.runpytest_subprocess(*CHILD_ARGS, "-rfE")
    # The teardown test's call passes and its teardown errors, so it counts once in each.
    result.assert_outcomes(passed=5, failed=10, errors=2)
    result.stdout.fnmatch_lines_random([
        "FAILED test_inner.py::test_dns_swallowed_fails - Failed: network gate*",
        "network gate: this test tried to reach the network (1 attempt(s), all blocked):",
        "*dns gate-selftest-dns.invalid:443 x1 [[]thread MainThread]",
        "*at test_inner.py:12 in test_dns_swallowed_fails",
        "*connect 192.0.2.1:443 x1*",
        "*sendto 192.0.2.1:9 x1*",
        "*dns gate-selftest-httpx.invalid:443 x1*",
        "*dns gate-selftest-pool.invalid:443 x1 [[]thread ThreadPoolExecutor-*",
        "*dns gate-selftest-asyncio.invalid:443 x1 [[]thread asyncio_0]",
        "*(submitted from) test_inner.py:* in test_asyncio_lookup_swallowed_fails",
        f"*connect 127.0.0.1:{port} (configured proxy HTTPS_PROXY=http://127.0.0.1:{port})*",
        "FAILED test_inner.py::test_pool_work_from_later_test_fails*",
        "FAILED test_inner.py::test_proxy_is_neutralised_and_caught*",
        "*dns gate-selftest-setup.invalid:443 x1*",
        "*dns gate-selftest-teardown.invalid:443 x1*",
        "*dns gate-selftest-skip.invalid:443 x1*",
        "*dns gate-selftest-xfail.invalid:443 x1*",
        "*dns gate-selftest-portal.invalid:443 x1*",
        "ERROR test_inner.py::test_setup_attempt_errors*",
        "ERROR test_inner.py::test_teardown_attempt_errors*",
        "FAILED test_inner.py::test_skip_after_attempt_fails*",
        "FAILED test_inner.py::test_xfail_with_attempt_fails*",
        "FAILED test_inner.py::test_task_on_another_tests_loop_fails*",
    ])
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_attempt_from_a_thread_that_outlived_its_test_fails_the_session(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(GATE_SOURCE + LATE_HOOK)
    pytester.makepyfile(test_stray=STRAY_TESTS)
    result = pytester.runpytest_subprocess(*CHILD_ARGS)
    result.assert_outcomes(passed=3)  # neither test is blamed for the other's thread ...
    result.stdout.fnmatch_lines_random([
        "*network gate: 2 outbound attempt(s) outside their test -- session FAILED*",
        "*dns gate-selftest-stray.invalid:443 x1 [[]thread late-worker]*",
        "*owner: test_stray.py::test_starts_a_thread_that_outlives_it; running: test_stray.py::test_runs_while_the_stray_fires*",
        "*dns gate-selftest-late.invalid:443 x1*",  # made after test_late's last report
        "*owner: test_stray.py::test_late; running: test_stray.py::test_late*",
    ])
    assert result.ret == pytest.ExitCode.TESTS_FAILED  # ... but the session fails


def test_offline_enrichment_allowlist_stays_off_the_locked_anchors() -> None:
    """tests/conftest.py's allowlist changes a file's runtime seams without touching its bytes, so a
    locked rule-6 anchor must never join it (that would change the anchor behind a byte-identity check)."""
    tree = ast.parse((TESTS / "conftest.py").read_text())
    allow = next(
        ast.literal_eval(node.value.args[0]) for node in tree.body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "_OFFLINE_ENRICHMENT_FILES"
    )
    assert allow and all((TESTS / rel).is_file() for rel in allow | LOCKED_ANCHORS)
    assert not allow & LOCKED_ANCHORS
