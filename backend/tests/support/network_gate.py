"""Outbound-network gate for the backend test suite (CLAUDE.md rule 12).

The suite must never reach the network: a live SEC/Yahoo call makes a test slow, flaky and
dependent on third-party state, and spends the SEC rate budget from the runner's IP. This pytest
plugin (registered by ``tests/conftest.py``) turns that rule into a gate.

An *attempt* is any of:
  * a DNS lookup of a name that is not local -- ``socket.getaddrinfo``, ``gethostbyname``,
    ``gethostbyname_ex``, ``gethostbyaddr`` or a reverse ``getnameinfo`` of a non-local address (the
    paths requests/urllib3, httpx/httpcore, anyio and asyncio take);
  * ``connect``/``connect_ex``/``sendto``/``sendmsg`` on an AF_INET/AF_INET6 socket to a non-loopback address,
    to a name that is not local, to port 53 anywhere (a DNS query to a local stub resolver), or to
    a loopback proxy endpoint that was configured when the session started.

Each attempt is BLOCKED (it raises ``OSError``, like an offline host) and RECORDED. Blocking alone
is not a gate -- code under test routinely swallows network errors, so the test would still pass --
so every attempt is charged to an owner:
  * made on behalf of the running test (its own thread; an asyncio task or anyio worker carrying
    its context, even on a loop another test started; a thread it started; work it submitted to a
    ``ThreadPoolExecutor``, asyncio's default executor included) -> that test's report is FAILED,
    in whichever phase made it (setup and teardown included; a skip or an xfail does not hide it);
  * anything else (a thread or task that outlived the test that started it, collection-time
    imports, session-scoped fixtures) -> a *stray*: listed in the terminal summary with its owner
    and the test running at the time, and the session exits non-zero. A long-lived worker thread
    stays charged to the test that started it, so for a stray the running test is often the
    better lead.

Unaffected: loopback/unspecified addresses (127.0.0.0/8, ::1, 0.0.0.0, ::), AF_UNIX sockets, the
in-process ASGI/TestClient transport (opens no socket) and libpq/psycopg2 (connects in C, below
this gate; CI's PostgreSQL URLs are loopback). Outside the gate: subprocesses, C-level resolvers
(uvloop, c-ares, libpq), sockets made from the C-level ``_socket.socket`` class, a client given an
explicit ``proxy=`` argument, an env proxy re-added after import with ``NO_PROXY`` removed, names
under ``.localhost`` and this machine's own hostname (treated as local, so they reach the system
resolver, which normally answers them without a query), and attempts made after the session
finished.

Proxies: an ``HTTPS_PROXY`` pointing at a loopback proxy would carry a request out through an
allowed loopback connect. At import the gate records every configured proxy endpoint, removes
the ``*_proxy`` variables and sets ``NO_PROXY=*``, so clients connect directly (and the gate names
the real host); a connect to a recorded loopback proxy endpoint is still an attempt.
"""

from __future__ import annotations

import contextlib
import contextvars
import errno
import ipaddress
import os
import socket
import sys
import sysconfig
import threading
import traceback
import urllib.request
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlsplit

import pytest

_DNS_PORT = 53
_INET = (socket.AF_INET, socket.AF_INET6)
_LOCAL_NAMES = frozenset(
    {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback", socket.gethostname().lower()}
)
_STDLIB = sysconfig.get_paths()["stdlib"]
_HINT = (
    "Fake the boundary instead (monkeypatch the client or service call; patch settings, not env "
    "vars); a provider key that arrives from backend/.env gets an empty pin in tests/conftest.py, "
    "not an edit to the test. The attempt was blocked with OSError, which the code under test may "
    "have swallowed -- without this gate the test could pass while reaching for the network."
)


class NetworkGateDNSBlocked(socket.gaierror):
    """Raised in place of a DNS lookup of a non-local name."""


class NetworkGateConnectBlocked(ConnectionRefusedError):
    """Raised in place of a connect/sendto to a non-loopback endpoint."""


@dataclass
class Attempt:
    kind: str  # "dns" | "connect" | "sendto"
    target: str
    owner: str | None  # the test the attempt was made for, when known
    during: str | None  # the test running at the time (None: collection, between tests)
    thread: str
    where: tuple[str, ...]
    count: int = 1


_OWNER: contextvars.ContextVar[str | None] = contextvars.ContextVar("network_gate_owner", default=None)
_TLS = threading.local()
_LOCK = threading.Lock()
_running: str | None = None
_per_test: dict[str, dict[tuple, Attempt]] = {}
_strays: dict[tuple, Attempt] = {}


def _owner() -> str | None:
    # A carried context wins: an asyncio task scheduled by this test on a loop another test started
    # (whose thread carries that test's executor tag) still belongs to this test.
    owner = _OWNER.get()  # main thread, asyncio tasks, anyio/to_thread workers
    if owner is None:
        owner = getattr(_TLS, "owner", None)  # executor work: the test that submitted it
    if owner is None:
        owner = getattr(threading.current_thread(), "_network_gate_owner", None)  # thread start
    return owner


def _stack(limit: int = 4) -> tuple[str, ...]:
    """The innermost project frames (not stdlib, site-packages or this file) of the caller's stack."""
    frames = traceback.StackSummary.extract(traceback.walk_stack(sys._getframe(1)), lookup_lines=False)
    own = [
        f for f in reversed(frames)
        if f.filename != __file__ and not f.filename.startswith((_STDLIB, "<")) and "site-packages" not in f.filename
    ]
    try:  # runs on every executor submit: a test that removed its cwd must not break submit()
        cwd = os.getcwd() + os.sep
    except OSError:
        cwd = os.sep
    return tuple(f"{f.filename.removeprefix(cwd)}:{f.lineno} in {f.name}" for f in own[-limit:])


def _where() -> tuple[str, ...]:
    # Executor work runs on a pool thread whose stack is stdlib only; the submitter's frames say who.
    submitted = tuple(f"(submitted from) {w}" for w in getattr(_TLS, "origin", ()))
    return _stack() or submitted or ("(no project frame on the stack)",)


def _record(kind: str, target: str) -> None:
    attempt = Attempt(kind, target, _owner(), _running, threading.current_thread().name, _where())
    capture = getattr(_TLS, "capture", None)
    if capture is not None:
        capture.append(attempt)
        return
    with _LOCK:
        if attempt.owner is not None and attempt.owner == _running:
            bucket, key = _per_test.setdefault(attempt.owner, {}), (kind, target, attempt.thread)
        else:
            bucket, key = _strays, (kind, target, attempt.thread, attempt.owner, attempt.during)
        if key in bucket:
            bucket[key].count += 1
        else:
            bucket[key] = attempt


def _text(host: object) -> str:
    if isinstance(host, (bytes, bytearray)):
        host = bytes(host).decode("ascii", "replace")
    return str(host).strip().strip("[]").rstrip(".").lower()


def _ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return None
    return getattr(ip, "ipv4_mapped", None) or ip


def _is_local_name(host: str) -> bool:
    return host == "" or host in _LOCAL_NAMES or host.endswith(".localhost")


def _is_local_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_loopback or ip.is_unspecified


def _snapshot_and_clear_proxies() -> dict[tuple[str, int], str]:
    """Record loopback proxy endpoints, then make every client connect directly."""
    names = [k for k in os.environ if k.lower().endswith("_proxy") and k.lower() != "no_proxy"]
    configured = {k: os.environ[k] for k in names if os.environ[k]}
    try:  # also the platform's system proxies (macOS/Windows), which env clearing alone keeps
        system = urllib.request.getproxies().items()
        configured.update({f"system {s}_proxy": u for s, u in system if s != "no" and u not in configured.values()})
    except Exception:  # best effort: the env proxies are already recorded
        pass
    endpoints: dict[tuple[str, int], str] = {}
    for source, url in configured.items():
        parts = urlsplit(url if "://" in url else f"http://{url}")
        try:
            port = parts.port or {"https": 443, "socks5": 1080, "socks5h": 1080, "socks4": 1080}.get(parts.scheme, 80)
        except ValueError:
            continue
        host = _text(parts.hostname or "")
        ip = _ip(host)
        addresses = ("127.0.0.1", "::1") if _is_local_name(host) else (str(ip),) if ip and _is_local_ip(ip) else ()
        for address in addresses:
            endpoints[(address, port)] = f"{source}={url}"
    for name in names:
        del os.environ[name]
    os.environ["NO_PROXY"] = os.environ["no_proxy"] = "*"
    return endpoints


_PROXY_ENDPOINTS = _snapshot_and_clear_proxies()


def _lookup_target(host: object, port: object = None) -> str | None:
    """The name a lookup would send to a resolver, or None when it stays on this machine."""
    if host is None:
        return None
    name = _text(host)
    if _is_local_name(name) or _ip(name) is not None:  # an IP literal sends no query
        return None
    return f"{name}:{port}" if port not in (None, 0, "") else name


def _endpoint_target(sock: socket.socket, address: object) -> str | None:
    """The outbound endpoint a connect/sendto would reach, or None when it stays local."""
    if sock.family not in _INET or not isinstance(address, tuple) or len(address) < 2:
        return None  # AF_UNIX, netlink, ...
    host, port = _text(address[0]), address[1]
    target = f"{host}:{port}"
    if port == _DNS_PORT:
        return f"{target} (DNS query)"
    ip = _ip(host)
    if ip is None and not _is_local_name(host):
        return target
    if ip is not None and not _is_local_ip(ip):
        return target
    for candidate in ("127.0.0.1", "::1") if ip is None else (str(ip),):
        proxy = _PROXY_ENDPOINTS.get((candidate, port))
        if proxy:
            return f"{target} (configured proxy {proxy})"
    return None


def _block_lookup(target: str) -> None:
    _record("dns", target)
    raise NetworkGateDNSBlocked(socket.EAI_NONAME, f"network gate: blocked DNS lookup of {target}")


def _block_endpoint(kind: str, target: str) -> None:
    _record(kind, target)
    raise NetworkGateConnectBlocked(errno.ECONNREFUSED, f"network gate: blocked {kind} to {target}")


def _install() -> None:
    if getattr(socket, "_network_gate_installed", False):
        return  # imported twice under two module names: the first install stands
    socket._network_gate_installed = True  # type: ignore[attr-defined]

    real_getaddrinfo, real_byname = socket.getaddrinfo, socket.gethostbyname
    real_byname_ex, real_byaddr = socket.gethostbyname_ex, socket.gethostbyaddr
    real_nameinfo = socket.getnameinfo
    real_connect, real_connect_ex, real_sendto = socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto
    real_sendmsg = getattr(socket.socket, "sendmsg", None)  # absent on Windows
    real_start, real_submit = threading.Thread.start, ThreadPoolExecutor.submit

    def getaddrinfo(host, port, *args, **kwargs):
        if (target := _lookup_target(host, port)) is not None:
            _block_lookup(target)
        return real_getaddrinfo(host, port, *args, **kwargs)

    def gethostbyname(host):
        if (target := _lookup_target(host)) is not None:
            _block_lookup(target)
        return real_byname(host)

    def gethostbyname_ex(host):
        if (target := _lookup_target(host)) is not None:
            _block_lookup(target)
        return real_byname_ex(host)

    def gethostbyaddr(host):  # reverse DNS: a non-local IP literal is a query too
        name = _text(host)
        ip = _ip(name)
        if (ip is not None and not _is_local_ip(ip)) or (ip is None and _lookup_target(name) is not None):
            _block_lookup(f"reverse {name}")
        return real_byaddr(host)

    def getnameinfo(sockaddr, flags):  # reverse DNS, unless the caller asked for the numeric host
        name = _text(sockaddr[0]) if isinstance(sockaddr, tuple) and sockaddr else ""
        ip = _ip(name)
        if ip is not None and not _is_local_ip(ip) and not flags & socket.NI_NUMERICHOST:
            _block_lookup(f"reverse {name}")
        return real_nameinfo(sockaddr, flags)

    def connect(self, address):
        if (target := _endpoint_target(self, address)) is not None:
            _block_endpoint("connect", target)
        return real_connect(self, address)

    def connect_ex(self, address):
        if (target := _endpoint_target(self, address)) is not None:
            _block_endpoint("connect", target)
        return real_connect_ex(self, address)

    def sendto(self, data, *args):
        if args and (target := _endpoint_target(self, args[-1])) is not None:
            _block_endpoint("sendto", target)
        return real_sendto(self, data, *args)

    def sendmsg(self, buffers, *args):  # sendmsg(buffers[, ancdata[, flags[, address]]])
        if len(args) >= 3 and (target := _endpoint_target(self, args[2])) is not None:
            _block_endpoint("sendto", target)
        return real_sendmsg(self, buffers, *args)

    def start(self, *args, **kwargs):
        self._network_gate_owner = _owner()
        return real_start(self, *args, **kwargs)

    def submit(self, fn, /, *args, **kwargs):
        owner, origin = _owner(), _stack()

        def run_for_owner(*a, **kw):
            previous = getattr(_TLS, "owner", None), getattr(_TLS, "origin", ())
            _TLS.owner, _TLS.origin = owner, origin
            try:
                return fn(*a, **kw)
            finally:
                _TLS.owner, _TLS.origin = previous

        return real_submit(self, run_for_owner, *args, **kwargs)

    socket.getaddrinfo, socket.gethostbyname = getaddrinfo, gethostbyname
    socket.gethostbyname_ex, socket.gethostbyaddr = gethostbyname_ex, gethostbyaddr
    socket.getnameinfo = getnameinfo
    socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto = connect, connect_ex, sendto
    if real_sendmsg is not None:
        socket.socket.sendmsg = sendmsg
    threading.Thread.start, ThreadPoolExecutor.submit = start, submit


_install()


def _describe(attempts: Iterable[Attempt], *, strays: bool) -> list[str]:
    lines = []
    for a in sorted(attempts, key=lambda a: (a.owner or "", a.during or "", a.kind, a.target)):
        line = f"  {a.kind} {a.target} x{a.count} [thread {a.thread}]"
        if strays:
            line += f"\n    owner: {a.owner or '<no test: collection/session code>'}; running: {a.during or '<none>'}"
        lines.append(line)
        lines.extend(f"      at {w}" for w in a.where)
    return lines


@contextlib.contextmanager
def expect_blocked() -> Iterator[list[Attempt]]:
    """Self-test helper: collect this thread's attempts inside the block instead of charging them.

    The attempts are still blocked (they raise), and leaving the block without one fails, so it
    can acknowledge an attempt but never permit one.
    """
    caught: list[Attempt] = []
    previous, _TLS.capture = getattr(_TLS, "capture", None), caught
    try:
        yield caught
    finally:
        _TLS.capture = previous
    if not caught:
        raise AssertionError("network gate: expected a blocked outbound attempt, saw none")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    global _running
    _running = item.nodeid
    token = _OWNER.set(item.nodeid)
    try:
        return (yield)
    finally:
        _OWNER.reset(token)
        with _LOCK:
            _running = None
            late = _per_test.pop(item.nodeid, {})  # after the test's last report: a stray now
            for key, attempt in late.items():
                _strays[key + (attempt.owner, attempt.during)] = attempt


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    report = yield
    with _LOCK:
        attempts = _per_test.pop(item.nodeid, {})
    if attempts:
        total = sum(a.count for a in attempts.values())
        text = "\n".join(
            [f"network gate: this test tried to reach the network ({total} attempt(s), all blocked):"]
            + _describe(attempts.values(), strays=False)
            + [_HINT]
        )
        if report.failed:
            report.sections.append(("network gate", text))
        else:  # passed, or an xfail/xpass: a network attempt is never an expected outcome
            try:
                pytest.fail(text, pytrace=False)
            except pytest.fail.Exception:  # a raised Failed gives the report a one-line reprcrash
                report.outcome, report.longrepr = "failed", item.repr_failure(pytest.ExceptionInfo.from_current())
            if hasattr(report, "wasxfail"):
                del report.wasxfail
    return report


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session) -> None:
    with _LOCK:
        if _strays and session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter) -> None:
    with _LOCK:
        strays = list(_strays.values())
    if strays:
        total = sum(a.count for a in strays)
        terminalreporter.section(
            f"network gate: {total} outbound attempt(s) outside their test -- session FAILED",
            sep="=", red=True, bold=True,
        )
        for line in _describe(strays, strays=True) + [_HINT]:
            terminalreporter.line(line)
