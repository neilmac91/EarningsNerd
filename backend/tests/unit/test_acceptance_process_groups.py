"""The acceptance runners end their CLI's whole process group, not just the child.

Both runners start the CLI with ``start_new_session=True``, so the child leads a process group that its own
children join. A grandchild still handling SIGTERM, or ignoring it, used to outlive ``_terminate_group``: the runner
then fsynced and hashed streams the grandchild could still write to, and the delivery test that read the
grandchild's state right after the timeout raced it (CI run 38076411964). Each case runs against both runners'
copies, which must stay identical: the judge runner's guardian imports no repository module.
"""
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
    "slow": (  # still handling SIGTERM when the child has already died of it
        "import signal, sys, time\n"
        "def stop(*_):\n"
        "    time.sleep(0.5)\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGTERM, stop)\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)\n"
    ),
    "deaf": (  # ignores SIGTERM: only SIGKILL ends it
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)\n"
    ),
}


def _running(pid: int) -> bool:
    """Whether the pid can still run: a zombie, which a reaper-less container leaves behind, cannot."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return False
    return state not in ("Z", "X")


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


def test_a_zombie_is_no_live_member(tmp_path: Path) -> None:
    """``/proc`` is read where it exists: a member counts by its process group (not its session) unless it is a
    zombie (state Z), and any process's name may hold ")" or bytes that are not UTF-8. Elsewhere signal 0 answers."""
    def stat(pid: int, name: bytes, state: str, pgid: int, session: int = 9999) -> None:
        (tmp_path / str(pid)).mkdir()
        (tmp_path / str(pid) / "stat").write_bytes(b"%d (%s) %s 1 %d %d 0 -1\n" % (pid, name, state.encode(), pgid, session))

    stat(100, b"sh", "Z", 4242)
    stat(101, b"odd) S 1 4242 x", "Z", 4242)
    stat(102, b"app-\xd0", "S", 7, session=4242)  # not UTF-8, and its session (not its group) is 4242
    assert not delivery._group_alive(4242, tmp_path)
    stat(103, b"sleep", "S", 4242)
    assert delivery._group_alive(4242, tmp_path)
    assert not delivery._group_alive(4243, tmp_path)

    gone = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    gone.wait()
    missing = tmp_path / "absent"
    assert delivery._group_alive(os.getpgrp(), missing)
    assert not delivery._group_alive(gone.pid, missing)


def test_both_runners_hold_the_same_group_termination() -> None:
    """The judge runner's guardian runs its file as a script and imports no repository module, so the code is held
    twice; a fix to one copy must reach the other."""
    for name in ("_group_alive", "_drain_group", "_terminate_group"):
        assert inspect.getsource(getattr(delivery, name)) == inspect.getsource(getattr(judge_runner, name)), name
    for name in ("_GROUP_GRACE_SECONDS", "_GROUP_POLL_SECONDS"):
        assert getattr(delivery, name) == getattr(judge_runner, name), name


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
        + "pathlib.Path('writer.pid').write_text(str(os.getpid()))\n"
        "while True:\n"
        "    sys.stdout.write('x'); sys.stdout.flush(); time.sleep(0.02)\n"
    )


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
    leader = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {_writer(ignore_sigterm=True)!r}])\n"
        "while not os.path.exists('writer.pid'):\n"
        "    time.sleep(0.01)\n"
        "time.sleep(60)\n"
    )
    result = _route(tmp_path, leader, timeout_seconds=2)  # ample time for the writer to set SIGTERM aside
    assert result.timed_out and result.kill_signal == "SIGKILL"
    assert not _running(int((tmp_path / "writer.pid").read_text()))
    _assert_stream_final(tmp_path)


def test_nothing_writes_to_the_delivery_streams_after_the_child_exits(tmp_path: Path, writer_cleanup) -> None:
    """The child exits on its own and leaves a grandchild writing: the runner ends the group before the fsync too,
    and the receipt's kill_signal says it did."""
    leader = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {_writer(ignore_sigterm=False)!r}])\n"
        "while not os.path.exists('writer.pid'):\n"
        "    time.sleep(0.01)\n"
        "time.sleep(0.1)\n"
    )
    result = _route(tmp_path, leader, timeout_seconds=30)
    assert (result.exit_code, result.timed_out, result.kill_signal) == (0, False, "SIGTERM")
    assert not _running(int((tmp_path / "writer.pid").read_text()))
    _assert_stream_final(tmp_path)
