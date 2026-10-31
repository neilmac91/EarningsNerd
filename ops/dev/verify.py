"""Serialize cooperative local suites/builds across one user's checkouts (Linux/macOS).

Run from the command's usual directory: python3 ../ops/dev/verify.py -- python -m pytest
See README.md beside this file for the process-group and filesystem contract.
"""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import time
from types import FrameType

ACTIVE = "EARNINGSNERD_VERIFY_ACTIVE"
POLL_SECONDS = 0.1
GRACE_SECONDS = 5.0
SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)


class Cancellation:
    def __init__(self) -> None:
        self.signum = 0
        self.count = 0

    def receive(self, signum: int, _frame: FrameType | None) -> None:
        # Never raise through Popen: a signal can arrive after fork, before its return.
        if not self.signum:
            self.signum = signum
        self.count += 1


def report(message: str) -> None:
    if sys.stderr is None:
        return  # print(file=None) would otherwise send diagnostics to command stdout.
    try:
        print(f"verify: {message}", file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass  # A closed diagnostics pipe must not interrupt child cleanup.


def process_rows(pid: int | None = None) -> list[tuple[int, int, str]]:
    """Read IDs/states only, never argv. Linux -L includes live threads of a zombie leader."""
    command = ["/bin/ps"]
    command += ["-p", str(pid)] if pid is not None else ["-A"]
    if sys.platform == "linux":
        command.append("-L")
    command += ["-o", "pid=,pgid=,stat="]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, timeout=5, check=True)
    rows = []
    for line in result.stdout.splitlines():
        process, group, state = line.split()
        rows.append((int(process), int(group), state))
    if not rows:
        raise RuntimeError("empty process snapshot")
    return rows


def leader_exited(pid: int) -> bool:
    # Do not reap the leader yet: its reserved PID prevents reuse of our process-group ID.
    if sys.platform == "linux":
        return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    # Python's waitid is unavailable on macOS. Its ps reports process (not Linux task) state.
    rows = process_rows(pid)
    if not any(process == pid for process, _, _ in rows):
        raise RuntimeError("command leader disappeared before reaping")
    return all(state.startswith(("Z", "X")) for _, _, state in rows)


def group_alive(pgid: int) -> bool:
    return any(group == pgid and not state.startswith(("Z", "X"))
               for _, group, state in process_rows())


def finish_group(pgid: int, cancel: Cancellation) -> None:
    """Hold ownership until no same-group thread can run, including after the leader exits."""
    signalled_at: float | None = None
    sent = False
    cancellation_seen = False
    warned = False
    while True:
        try:
            if not group_alive(pgid):
                return
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            if not warned:
                report("cannot verify child cleanup; retaining the slot and retrying")
                warned = True
        if cancel.signum and not cancellation_seen:
            # A user can cancel after normal leader exit already began automatic TERM cleanup.
            # Forward that first cancellation too, with its own grace period.
            sent = False
            signalled_at = None
            cancellation_seen = True
        signum = cancel.signum or signal.SIGTERM
        if cancel.count > 1 or (signalled_at is not None and time.monotonic() - signalled_at >= GRACE_SECONDS):
            signum = signal.SIGKILL
        if not sent or signum == signal.SIGKILL:
            try:
                os.killpg(pgid, signum)
            except ProcessLookupError:
                pass
            except PermissionError:
                if not warned:
                    report("cannot signal a child; retaining the slot until cleanup is verified")
                    warned = True
            if signalled_at is None:
                signalled_at = time.monotonic()
            sent = True
        time.sleep(POLL_SECONDS)


def run_command(command: list[str], cancel: Cancellation) -> int:
    # SIG_IGN inherited from a shell would auto-reap the leader and lose the PID reservation.
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    process_rows()  # Fail before starting work if the cleanup observer is unavailable.
    if cancel.signum:
        return -cancel.signum
    environment = os.environ.copy()
    environment[ACTIVE] = str(os.getpid())  # A refusal marker, never permission to bypass locking.
    try:
        process = subprocess.Popen(command, start_new_session=True, env=environment)
    except FileNotFoundError:
        report("command not found")
        return 127
    except OSError as exc:
        report(f"cannot start command: {exc.strerror}")
        return 126
    try:
        while not cancel.signum and not leader_exited(process.pid):
            time.sleep(POLL_SECONDS)
    finally:
        # Also runs on observer errors. Never release the lock just because the direct child died.
        finish_group(process.pid, cancel)
        result = process.wait()
    return -cancel.signum if cancel.signum else result


def run_locked(command: list[str], lock_path: Path, cancel: Cancellation) -> int:
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    # Closing releases the OS lock; never unlink this inode (owners and waiters may still hold it).
    with os.fdopen(fd, "rb") as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("lock must be a regular file owned by the current user")
        queued_at = time.monotonic()
        waiting = False
        while not cancel.signum:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not waiting:
                    report("waiting for the local verification slot")
                    waiting = True
                time.sleep(POLL_SECONDS)
        queue_seconds = time.monotonic() - queued_at
        if cancel.signum:
            report(f"cancelled while waiting queue_seconds={queue_seconds:.3f}")
            return -cancel.signum
        report(f"acquired queue_seconds={queue_seconds:.3f}")
        started = time.monotonic()
        try:
            return run_command(command, cancel)
        finally:
            report(f"finished run_seconds={time.monotonic() - started:.3f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock-file", type=Path, help="absolute lock path for an isolated test namespace")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("supply a command after --")
    if sys.platform not in ("linux", "darwin"):
        parser.error("supported platforms are Linux and macOS")
    if ACTIVE in os.environ:
        parser.error("nested verification is unsupported; wrap each stage once")
    # Use the account home, not per-shell HOME/XDG/TMP settings or a checkout-relative directory.
    lock_path = args.lock_file or Path(pwd.getpwuid(os.getuid()).pw_dir) / ".cache/earningsnerd/verification.lock"
    if not lock_path.is_absolute():
        parser.error("--lock-file must be absolute")
    cancel = Cancellation()
    for signum in SIGNALS:
        signal.signal(signum, cancel.receive)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, SIGNALS)
    try:
        result = run_locked(command, lock_path, cancel)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        report(f"launcher failed ({type(exc).__name__})")
        result = -cancel.signum if cancel.signum else 1
    if result < 0:
        # Preserve signal termination for callers, after cleanup and lock release.
        signum = -result
        if signum != signal.SIGKILL:
            signal.signal(signum, signal.SIG_DFL)
            signal.pthread_sigmask(signal.SIG_UNBLOCK, {signum})
        os.kill(os.getpid(), signum)
        return 128 + signum
    return result


if __name__ == "__main__":
    raise SystemExit(main())
