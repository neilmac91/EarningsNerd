"""The acceptance runners end their CLI's whole process group, not just the child.

Both runners start the CLI with ``start_new_session=True``, so the child leads a process group that its own
children join. A grandchild still handling SIGTERM, or ignoring it, used to outlive ``_terminate_group``: the runner
then fsynced and hashed streams the grandchild could still write to, and the delivery test that read the
grandchild's state right after the timeout raced it (CI run 38076411964). Each case runs against both runners'
copies, which must stay identical: the judge runner's guardian imports no repository module.
"""
import ast
import inspect
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import evals.acceptance_ai_judge_runner as judge_runner
import evals.acceptance_source_review_delivery as delivery
from evals.acceptance_source_review_delivery import RouteInvocation, run_route_process

RUNNERS = pytest.mark.parametrize("runner", [delivery, judge_runner], ids=["delivery", "judge"])

# The child: starts one grandchild, waits until its SIGTERM handling is in place, reports its pid, then exits or sleeps.
LEADER = (
    "import subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', sys.argv[1]], stdout=subprocess.PIPE)\n"
    "child.stdout.readline()\n"
    "print(child.pid, flush=True)\n"
    "if sys.argv[2] == 'exit':\n"
    "    sys.exit(0)\n"
    "time.sleep(60)\n"
)
GRANDCHILDREN = {
    "plain": "import time\nprint('ready', flush=True)\ntime.sleep(60)\n",
    # Still handling SIGTERM when the child has already died of it. It waits for SIGTERM with sigwait, not a Python
    # handler: CPython runs a handler only at its next check, so a SIGTERM delivered after that check and before
    # time.sleep enters its syscall left the handler waiting out the whole sleep, and the member read deaf
    # (CI run 38186685529). A blocked SIGTERM stays pending until sigwait takes it, whenever it arrives.
    "slow": (
        "import signal, sys, time\n"
        "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})\n"
        "print('ready', flush=True)\n"
        "signal.sigwait({signal.SIGTERM})\n"
        "time.sleep(0.5)\n"
        "sys.exit(0)\n"
    ),
    "deaf": (  # ignores SIGTERM: only SIGKILL ends it
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)\n"
    ),
    "threaded": (  # its main thread leaves through pthread_exit, so /proc reads it Z while another thread runs
        "import ctypes, threading, time\n"
        "threading.Thread(target=time.sleep, args=(60,)).start()\n"
        "print('ready', flush=True)\n"
        "ctypes.CDLL(None).pthread_exit(None)\n"
    ),
}
LINUX_PROC = pytest.mark.skipif(not Path("/proc/self/stat").is_file(), reason="reads Linux's /proc")


def _state(pid: int) -> bytes | None:
    try:
        return Path(f"/proc/{pid}/stat").read_bytes().rpartition(b")")[2].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return None


def _running(pid: int) -> bool:
    """Whether any thread of the pid can still run: a zombie, which a reaper-less container leaves behind, cannot.
    Without /proc, signal 0 answers (a zombie counts there, and an init that reaps clears it)."""
    if not Path("/proc/self/stat").is_file():
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True
    try:
        tids = [int(task.name) for task in Path(f"/proc/{pid}/task").iterdir()]
    except (FileNotFoundError, ProcessLookupError):
        return False
    return any(_state(tid) not in (None, b"Z", b"X") for tid in tids)


@pytest.fixture
def group():
    """Start the child in a session of its own, as the runners do; SIGKILL whatever a failing test leaves."""
    started: list[int] = []

    def start(grandchild: str, then: str = "sleep") -> tuple[subprocess.Popen[bytes], int]:
        proc = subprocess.Popen([sys.executable, "-c", LEADER, GRANDCHILDREN[grandchild], then],
                                stdout=subprocess.PIPE, start_new_session=True)
        grandchild_pid = int(proc.stdout.readline())
        started.extend((proc.pid, grandchild_pid))
        return proc, grandchild_pid

    yield start
    for pid in started:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


@RUNNERS
def test_the_group_gets_the_grace_period_not_just_the_child(runner, group) -> None:
    """The child dies of SIGTERM at once; its grandchild needs half a second to exit, and is waited for."""
    proc, grandchild = group("slow")
    started = time.monotonic()
    assert runner._terminate_group(proc) == "SIGTERM"
    assert time.monotonic() - started >= 0.4
    assert not _running(proc.pid) and not _running(grandchild)


@RUNNERS
def test_a_grandchild_that_outlives_the_grace_period_is_killed(runner, group, monkeypatch) -> None:
    """The child dies of SIGTERM; its grandchild ignores it, so the group is SIGKILLed when the grace period ends."""
    monkeypatch.setattr(runner, "_GROUP_GRACE_SECONDS", 0.5)
    proc, grandchild = group("deaf")
    assert runner._terminate_group(proc) == "SIGKILL"
    assert not _running(proc.pid) and not _running(grandchild)


@RUNNERS
def test_an_exited_child_leaves_its_group_to_be_ended(runner, group) -> None:
    """A child that already exited is reaped; a grandchild of it still running is signalled all the same."""
    proc, grandchild = group("plain", then="exit")
    proc.wait()
    assert runner._terminate_group(proc) == "SIGTERM"
    assert not _running(grandchild)
    assert runner._terminate_group(proc) is None  # nothing of the group is left to signal


@RUNNERS
@LINUX_PROC
def test_a_member_whose_main_thread_left_is_still_ended(runner, group) -> None:
    """A grandchild whose main thread called pthread_exit reads Z in /proc while its other thread runs: it is still a
    member that can write, so it is signalled after the child exits."""
    proc, grandchild = group("threaded", then="exit")
    proc.wait()
    deadline = time.monotonic() + 5
    while _state(grandchild) != b"Z" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert _state(grandchild) == b"Z" and _running(grandchild)
    assert runner._terminate_group(proc) == "SIGTERM"
    assert not _running(grandchild)


def test_a_zombie_is_no_live_member(tmp_path: Path, monkeypatch) -> None:
    """``/proc`` is read where it exists: a member counts by its process group (not its session) unless it is a
    zombie (state Z) whose threads are all zombies too, and any process's name may hold ")" or bytes that are not
    UTF-8. Elsewhere signal 0 answers."""
    def stat(pid: int, name: bytes, state: str, pgid: int, session: int = 9999,
             threads: dict[int, str] | None = None) -> None:
        (tmp_path / str(pid)).mkdir()
        (tmp_path / str(pid) / "stat").write_bytes(b"%d (%s) %s 1 %d %d 0 -1\n" % (pid, name, state.encode(), pgid, session))
        for tid, thread_state in (threads or {}).items():
            (tmp_path / str(pid) / "task" / str(tid)).mkdir(parents=True)
            if thread_state:  # empty: the thread exited while the scan ran
                (tmp_path / str(pid) / "task" / str(tid) / "stat").write_bytes(
                    b"%d (%s) %s 1 %d %d 0 -1\n" % (tid, name, thread_state.encode(), pgid, session))

    class Listed(type(tmp_path)):  # lists entries whose stat is gone first, so a scan must go past them
        def iterdir(self):
            return iter(sorted(super().iterdir(), key=lambda entry: (entry / "stat").is_file()))

    proc = Listed(tmp_path)
    (tmp_path / "self").mkdir()
    (tmp_path / "self" / "stat").write_bytes(b"1 (pytest) S 0 1 1 0 -1\n")  # a mounted /proc
    (tmp_path / "net").mkdir()
    (tmp_path / "net" / "stat").write_bytes(b"0 (net) S 1 4242 4242 0 -1\n")  # not a pid: never a member
    (tmp_path / "104").mkdir()  # exited while the scan ran: its stat is gone
    stat(100, b"sh", "Z", 4242, threads={100: "Z", 106: "", 110: "X"})  # a zombie's threads: zombie, gone, dead
    stat(101, b"odd) S 1 4242 x", "Z", 4242)
    stat(102, b"app-\xd0", "S", 7, session=4242)  # not UTF-8, and its session (not its group) is 4242
    stat(105, b"dead", "X", 4242)
    assert not delivery._group_alive(4242, proc)
    stat(107, b"node", "Z", 4244, threads={107: "Z", 109: "", 108: "S"})  # its main thread left through pthread_exit
    assert delivery._group_alive(4244, proc)
    stat(103, b"sleep", "S", 4242)
    assert delivery._group_alive(4242, proc)
    assert not delivery._group_alive(4243, proc)

    gone = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    gone.wait()
    for elsewhere in (tmp_path / "absent", tmp_path / "net"):  # no /proc, or one with no stat of its own (unmounted)
        assert delivery._group_alive(os.getpgrp(), elsewhere)
        assert not delivery._group_alive(gone.pid, elsewhere)

    def refuse(pgid: int, sig: int) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(delivery.os, "killpg", refuse)  # a member exists that this process may not signal
    assert delivery._group_alive(gone.pid, tmp_path / "absent")


@RUNNERS
def test_a_member_no_signal_reaches_is_not_reported_as_signalled(runner, group, monkeypatch) -> None:
    """killpg fails with EPERM when the child is gone and only another user's member is left: nothing is sent, so
    nothing is reported, and no grace period is spent on it. When only SIGKILL meets EPERM, SIGTERM is what was sent."""
    proc, _ = group("plain", then="exit")
    proc.wait()
    monkeypatch.setattr(runner, "_group_alive", lambda pgid, proc_root=Path("/proc"): True)
    monkeypatch.setattr(runner, "_GROUP_GRACE_SECONDS", 0.2)
    # Grace periods are counted, not timed: an elapsed bound (< 0.1 s) held only on an idle runner.
    drained, real_drain = [], runner._drain_group

    def drain(proc, seconds: float) -> None:
        drained.append(seconds)
        real_drain(proc, seconds)

    monkeypatch.setattr(runner, "_drain_group", drain)

    def refuse(pgid: int, sig: int) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(runner.os, "killpg", refuse)
    assert runner._terminate_group(proc) is None
    assert drained == []  # no signal was sent, so no grace period was given

    def refuse_sigkill(pgid: int, sig: int) -> None:
        if sig == signal.SIGKILL:
            refuse(pgid, sig)

    monkeypatch.setattr(runner.os, "killpg", refuse_sigkill)
    assert runner._terminate_group(proc) == "SIGTERM"
    assert drained == [0.2]  # one grace period after the SIGTERM; none after the refused SIGKILL


def _reached(module, name: str, seen: set[str]) -> None:
    """Every module-level function or constant of ``module`` that ``name`` reaches, through nested code too."""
    if name in seen or not hasattr(module, name):
        return
    value = getattr(module, name)
    if inspect.ismodule(value) or (inspect.isclass(value) and value.__module__ != module.__name__):
        return  # os, signal, Path: shared, not held twice
    seen.add(name)
    if inspect.isfunction(value) and value.__module__ == module.__name__:
        codes = [value.__code__]
        while codes:
            code = codes.pop()
            codes.extend(const for const in code.co_consts if inspect.iscode(const))
            for reached in code.co_names:
                _reached(module, reached, seen)


def test_both_runners_hold_the_same_group_termination() -> None:
    """The judge runner's guardian runs its file as a script and imports no repository module, so the code is held
    twice; a fix to anything ``_terminate_group`` reaches, in one copy, must reach the other."""
    names: set[str] = set()
    _reached(delivery, "_terminate_group", names)
    theirs: set[str] = set()
    _reached(judge_runner, "_terminate_group", theirs)
    assert names == theirs
    assert {"_group_alive", "_can_run", "_drain_group", "_GROUP_GRACE_SECONDS", "_GROUP_POLL_SECONDS"} <= names
    for name in sorted(names):
        ours, theirs = getattr(delivery, name), getattr(judge_runner, name)
        if inspect.isfunction(ours):
            assert inspect.getsource(ours) == inspect.getsource(theirs), name
        else:
            assert ours == theirs, name


def _try_around_fsync(function) -> ast.Try:
    """The ``try`` whose ``finally`` fsyncs the CLI's streams."""
    tree = ast.parse(inspect.getsource(function))
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
                isinstance(call, ast.Call) and ast.unparse(call.func) == "os.fsync"
                for stmt in node.finalbody for call in ast.walk(stmt)):
            return node
    raise AssertionError(f"{function.__name__} fsyncs no stream in a finally")


@pytest.mark.parametrize("function", [delivery.run_route_process, judge_runner._guardian_main],
                         ids=["delivery", "judge"])
def test_the_group_is_ended_before_the_streams_are_fsynced(function) -> None:
    """On every path that reaches the fsync, the group is ended first (a straggler's bytes must not be hashed into the
    receipt unfsynced): the ``try`` whose ``finally`` fsyncs holds one statement, an inner ``try`` around the child's
    ``communicate`` whose ``finally`` is the one call that ends the group. A return, a timeout or any other exception
    out of ``communicate`` passes that call before the outer handlers and the fsync."""
    outer = _try_around_fsync(function)
    assert len(outer.body) == 1 and isinstance(outer.body[0], ast.Try), ast.unparse(outer.body[0])
    inner = outer.body[0]
    calls = [ast.unparse(call.func) for stmt in inner.body for call in ast.walk(stmt) if isinstance(call, ast.Call)]
    assert any(name.endswith("communicate") for name in calls)
    assert len(inner.finalbody) == 1, [ast.unparse(stmt) for stmt in inner.finalbody]
    ends = inner.finalbody[0]
    assert isinstance(ends, (ast.Expr, ast.Assign)) and isinstance(ends.value, ast.Call)
    assert ast.unparse(ends.value.func) == "_terminate_group", ast.unparse(ends)


def _route(tmp_path: Path, leader: str, timeout_seconds: int):
    return run_route_process(RouteInvocation(
        argv=(sys.executable, "-c", leader), stdin_bytes=b"", env=dict(os.environ), cwd=tmp_path,
        timeout_seconds=timeout_seconds, stdout_path=tmp_path / "stdout.raw", stderr_path=tmp_path / "stderr.txt",
    ))


def _writer(ignore_sigterm: bool) -> str:
    """A grandchild that records its pid once its SIGTERM handling is set, then writes to the inherited stdout."""
    return (
        "import os, pathlib, signal, sys, time\n"
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if ignore_sigterm else "")
        + "pathlib.Path('writer.tmp').write_text(str(os.getpid()))\n"
        "os.replace('writer.tmp', 'writer.pid')\n"  # appears whole
        "while True:\n"
        "    sys.stdout.write('x'); sys.stdout.flush(); time.sleep(0.02)\n"
    )


def test_an_interrupted_ending_is_retried_before_the_fsync(tmp_path: Path, monkeypatch, writer_cleanup) -> None:
    """Should the first ending of the group be interrupted (an operator's Ctrl-C in its grace period), the delivery
    runner ends the group again before the fsync, so a grandchild deaf to SIGTERM does not outlive the runner."""
    monkeypatch.setattr(delivery, "_GROUP_GRACE_SECONDS", 0.3)
    real, calls = delivery._terminate_group, []

    def interrupted_once(proc):
        calls.append(proc.pid)
        if len(calls) == 1:
            raise KeyboardInterrupt
        return real(proc)

    monkeypatch.setattr(delivery, "_terminate_group", interrupted_once)
    leader = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {_writer(ignore_sigterm=True)!r}])\n"
        "while not os.path.exists('writer.pid'):\n"
        "    time.sleep(0.01)\n"
    )
    with pytest.raises(KeyboardInterrupt):
        _route(tmp_path, leader, timeout_seconds=30)
    assert len(calls) == 2
    assert not _running(int((tmp_path / "writer.pid").read_text()))


def _assert_stream_final(tmp_path: Path) -> None:
    written = (tmp_path / "stdout.raw").stat().st_size
    assert written > 0  # the grandchild did write while it ran
    time.sleep(0.3)
    assert (tmp_path / "stdout.raw").stat().st_size == written


@pytest.fixture
def writer_cleanup(tmp_path: Path):
    yield
    try:
        os.kill(int((tmp_path / "writer.pid").read_text()), signal.SIGKILL)
    except (FileNotFoundError, ValueError, ProcessLookupError):
        pass


def test_nothing_writes_to_the_delivery_streams_after_a_timeout(tmp_path: Path, monkeypatch, writer_cleanup) -> None:
    """A grandchild that ignores SIGTERM and keeps writing to the inherited stdout is killed before the runner
    fsyncs its streams, so the stdout the receipt hashes is final."""
    monkeypatch.setattr(delivery, "_GROUP_GRACE_SECONDS", 0.5)
    alive_at_fsync: list[bool] = []
    real_fsync = os.fsync

    def fsync(fd: int) -> None:
        pid_file = tmp_path / "writer.pid"
        alive_at_fsync.append(pid_file.exists() and _running(int(pid_file.read_text())))
        real_fsync(fd)

    monkeypatch.setattr(delivery.os, "fsync", fsync)
    leader = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {_writer(ignore_sigterm=True)!r}])\n"
        "while not os.path.exists('writer.pid'):\n"
        "    time.sleep(0.01)\n"
        "time.sleep(60)\n"
    )
    result = _route(tmp_path, leader, timeout_seconds=2)  # ample time for the writer to set SIGTERM aside
    assert result.timed_out and result.kill_signal == "SIGKILL"
    assert alive_at_fsync == [False, False]  # stdout and stderr, each fsynced once the writer is dead
    assert not _running(int((tmp_path / "writer.pid").read_text()))
    _assert_stream_final(tmp_path)


def test_nothing_writes_to_the_delivery_streams_after_the_child_exits(tmp_path: Path, writer_cleanup) -> None:
    """The child exits on its own and leaves a grandchild writing: the runner ends the group before the fsync too,
    and the receipt's kill_signal says it did."""
    leader = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {_writer(ignore_sigterm=False)!r}])\n"
        "while not os.path.exists('writer.pid') or os.path.getsize('stdout.raw') == 0:\n"
        "    time.sleep(0.01)\n"
    )
    result = _route(tmp_path, leader, timeout_seconds=30)
    assert (result.exit_code, result.timed_out, result.kill_signal) == (0, False, "SIGTERM")
    assert not _running(int((tmp_path / "writer.pid").read_text()))
    _assert_stream_final(tmp_path)
