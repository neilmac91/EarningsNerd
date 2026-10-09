"""The outbound-network gate (tests/support/network_gate.py) proves itself (CLAUDE.md rule 12).

In-process: the gate is wired into THIS session by tests/conftest.py and blocks + reports an
attempt. Subprocess (pytester): a swallowed attempt FAILS the test that made it -- from the main
thread, through httpx, from an executor worker and from an asyncio task; loopback, AF_UNIX and the
in-process ASGI transport still pass; a thread that outlives its test fails the session; and a
configured loopback proxy is neutralised and caught. Every target is a reserved name
(``.invalid``) or a documentation address (192.0.2.0/24), and the gate blocks before any query.
"""

import socket
from pathlib import Path

import pytest

pytest_plugins = ("pytester",)

GATE_SOURCE = (Path(__file__).resolve().parents[1] / "support" / "network_gate.py").read_text()

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
        result = pytester.runpytest_subprocess("-p", "no:cacheprovider", "-rf")
    result.assert_outcomes(passed=3, failed=7)
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
    ])
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_attempt_from_a_thread_that_outlived_its_test_fails_the_session(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(GATE_SOURCE)
    pytester.makepyfile(test_stray=STRAY_TESTS)
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    result.assert_outcomes(passed=2)  # neither test is blamed for the other's thread ...
    result.stdout.fnmatch_lines([
        "*network gate: 1 outbound attempt(s) outside their test -- session FAILED*",
        "*dns gate-selftest-stray.invalid:443 x1 [[]thread late-worker]*",
        "*owner: test_stray.py::test_starts_a_thread_that_outlives_it; running: test_stray.py::test_runs_while_the_stray_fires*",
    ])
    assert result.ret == pytest.ExitCode.TESTS_FAILED  # ... but the session fails
