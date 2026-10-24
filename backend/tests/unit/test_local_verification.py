"""The local verification slot covers the command's process group across checkouts.

Every launcher here uses a private temporary lock and drops the inherited nesting
marker: this suite can itself run under verify.py. Readiness and signal handshakes
order the cases; deadlines only stop a broken test from hanging the suite.
"""

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest


VERIFY = Path(__file__).resolve().parents[3] / "ops/dev/verify.py"
ACTIVE = "EARNINGSNERD_VERIFY_ACTIVE"
pytestmark = pytest.mark.skipif(sys.platform not in ("linux", "darwin"), reason="POSIX launcher")

# SIGUSR1 releases a cooperative owner. Block it before publishing readiness, so
# it cannot arrive between the readiness write and the wait.
OWNER = """
import json, os, signal, sys
from pathlib import Path
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid()}))
signal.sigwait({signal.SIGUSR1})
"""
MARK = "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('started')"
LOAD = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location('local_verify', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.argv = sys.argv[1:]
"""


def wait_until(predicate, description):
    deadline = time.monotonic() + 30
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail(f"timed out waiting for {description}")
        time.sleep(0.02)


def read_ready(path):
    def complete():
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    wait_until(complete, f"readiness in {path.name}")
    return complete()


def running(pid):
    """Independent observer: zombies cannot work, but a leader's live threads can."""
    if sys.platform == "linux":
        try:
            tasks = list(Path(f"/proc/{pid}/task").iterdir())
        except FileNotFoundError:
            return False
        for task in tasks:
            try:
                state = (task / "stat").read_bytes().rpartition(b")")[2].split()[0]
            except FileNotFoundError:
                continue
            if state not in (b"Z", b"X"):
                return True
        return False
    result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "stat="],
                            capture_output=True, text=True, timeout=10, check=False)
    return any(not line.strip().startswith(("Z", "X")) for line in result.stdout.splitlines())


@pytest.fixture
def launch(tmp_path):
    processes = []
    lock = tmp_path / "verification.lock"

    def start(command, *, cwd=None, source=VERIFY, driver="", environment=None,
              stdin=subprocess.DEVNULL, default_lock=False):
        env = os.environ.copy()
        env.pop(ACTIVE, None)
        env.update(environment or {})
        log = tmp_path / f"launcher-{len(processes)}.stderr"
        args = [sys.executable, str(source)]
        if driver:
            args = [sys.executable, "-c", LOAD + driver, str(source)]
        if not default_lock:
            args += ["--lock-file", str(lock)]
        args += ["--", *command]
        with log.open("w") as stderr:
            process = subprocess.Popen(args, cwd=cwd or tmp_path, env=env, stdin=stdin,
                                       stdout=subprocess.PIPE, stderr=stderr, text=True,
                                       start_new_session=True)
        processes.append(process)
        return process, log

    start.lock = lock
    yield start
    for process in processes:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                # In a failing launcher, kill the still-owned command groups before
                # its PID reservation disappears. Only this launcher's children.
                rows = subprocess.run(["/bin/ps", "-A", "-o", "pid=,ppid=,pgid="],
                                      capture_output=True, text=True, timeout=10, check=True)
                for row in rows.stdout.splitlines():
                    pid, parent, group = map(int, row.split())
                    if parent == process.pid and pid == group:
                        try:
                            os.killpg(group, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                process.kill()
                process.wait(timeout=10)
        if process.stdout:
            process.stdout.close()
        if process.stdin:
            process.stdin.close()


def queued(process, log, command_started):
    # With a broken shared lock the contender runs and writes its marker instead
    # of waiting. Observe either result before releasing the legitimate owner.
    wait_until(lambda: "waiting for" in log.read_text() or command_started.exists() or process.poll() is not None,
               "contender to queue or incorrectly start")
    assert "waiting for" in log.read_text(), log.read_text()
    assert not command_started.exists()


def test_checkouts_share_one_slot_and_keep_the_lock_inode(launch, tmp_path):
    checkouts = [tmp_path / "first-checkout", tmp_path / "second-checkout"]
    for checkout in checkouts:
        checkout.mkdir()
        (checkout / "verify.py").write_bytes(VERIFY.read_bytes())
    ready, admitted = tmp_path / "owner.json", tmp_path / "admitted"
    owner, _ = launch([sys.executable, "-c", OWNER, str(ready)], cwd=checkouts[0],
                      source=checkouts[0] / "verify.py")
    leader = read_ready(ready)["pid"]
    inode = launch.lock.stat().st_ino
    contender, log = launch([sys.executable, "-c", MARK, str(admitted)], cwd=checkouts[1],
                            source=checkouts[1] / "verify.py")
    queued(contender, log, admitted)
    assert owner.poll() is None and running(leader)
    os.kill(leader, signal.SIGUSR1)
    assert owner.wait(timeout=30) == 0
    assert contender.wait(timeout=30) == 0
    assert admitted.read_text() == "started"
    assert launch.lock.stat().st_ino == inode


def test_command_receives_exact_argv_cwd_and_streams_and_returns_its_status(launch, tmp_path):
    cwd = tmp_path / "working directory"
    cwd.mkdir()
    arguments = ["", "a b", "line\nbreak", "$(not-a-command)", "--flag", "£"]
    command = """
import json, os, sys
print(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'stdin': sys.stdin.read()}))
print('command stderr', file=sys.stderr)
raise SystemExit(23)
"""
    process, log = launch([sys.executable, "-c", command, *arguments], cwd=cwd, stdin=subprocess.PIPE)
    stdout, _ = process.communicate("input\nwith two lines\n", timeout=30)
    assert process.returncode == 23
    assert json.loads(stdout) == {"argv": arguments, "cwd": str(cwd), "stdin": "input\nwith two lines\n"}
    assert "command stderr\n" in log.read_text()
    assert "acquired queue_seconds=" in log.read_text() and "finished run_seconds=" in log.read_text()


def test_cancelling_a_waiter_does_not_signal_the_owner(launch, tmp_path):
    ready, admitted = tmp_path / "owner.json", tmp_path / "admitted"
    owner, _ = launch([sys.executable, "-c", OWNER, str(ready)])
    leader = read_ready(ready)["pid"]
    waiter, log = launch([sys.executable, "-c", MARK, str(admitted)])
    queued(waiter, log, admitted)
    waiter.send_signal(signal.SIGTERM)
    assert waiter.wait(timeout=30) == -signal.SIGTERM
    assert owner.poll() is None and running(leader)
    assert not admitted.exists()
    os.kill(leader, signal.SIGUSR1)
    assert owner.wait(timeout=30) == 0


@pytest.mark.parametrize("marker", ["", "not-a-pid", "1"])
def test_inherited_nesting_marker_refuses_instead_of_bypassing_lock(launch, tmp_path, marker):
    admitted = tmp_path / "admitted"
    process, log = launch([sys.executable, "-c", MARK, str(admitted)], environment={ACTIVE: marker})
    assert process.wait(timeout=30) == 2
    assert "nested verification is unsupported" in log.read_text()
    assert not admitted.exists() and not launch.lock.exists()


def test_a_wrapped_command_cannot_acquire_another_slot(launch, tmp_path):
    admitted = tmp_path / "admitted"
    process, log = launch([sys.executable, str(VERIFY), "--lock-file", str(tmp_path / "nested.lock"),
                           "--", sys.executable, "-c", MARK, str(admitted)])
    assert process.wait(timeout=30) == 2
    assert "nested verification is unsupported" in log.read_text()
    assert not admitted.exists() and not (tmp_path / "nested.lock").exists()


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT])
def test_cancellation_signals_the_command_then_terminates_the_launcher_by_that_signal(launch, tmp_path, signum):
    ready, received = tmp_path / "ready.json", tmp_path / "received"
    command = """
import json, os, signal, sys
from pathlib import Path
signals = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT}
signal.pthread_sigmask(signal.SIG_BLOCK, signals)
Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid()}))
Path(sys.argv[2]).write_text(str(signal.sigwait(signals)))
"""
    process, _ = launch([sys.executable, "-c", command, str(ready), str(received)])
    leader = read_ready(ready)["pid"]
    process.send_signal(signum)
    assert process.wait(timeout=30) == -signum
    assert received.read_text() == str(signum)
    assert not running(leader)


@pytest.mark.parametrize("deaf", [False, True], ids=["cooperative", "ignores-term"])
def test_a_successful_leader_does_not_leave_its_descendant_running(launch, tmp_path, deaf):
    ready = tmp_path / "ready.json"
    child = """
import signal, sys
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGUSR1})
if sys.argv[1] == 'deaf':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
print('ready', flush=True)
signal.sigwait({signal.SIGUSR1} if sys.argv[1] == 'deaf' else {signal.SIGTERM})
"""
    leader = """
import json, os, subprocess, sys
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[3]], stdout=subprocess.PIPE)
assert child.stdout.readline() == b'ready\\n'
Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid(), 'child': child.pid}))
"""
    process, _ = launch([sys.executable, "-c", leader, str(ready), child, "deaf" if deaf else "cooperative"])
    members = read_ready(ready)
    assert process.wait(timeout=30) == 0
    assert not running(members["pid"]) and not running(members["child"])


@pytest.mark.parametrize("diagnostics", ["normal", "none", "closed"])
def test_contender_waits_through_descendant_cleanup_even_without_diagnostics(launch, tmp_path, diagnostics):
    ready, received, admitted = [tmp_path / name for name in ("ready.json", "term-received", "admitted")]
    child = """
import signal, sys
from pathlib import Path
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGUSR1})
print('ready', flush=True)
signal.sigwait({signal.SIGTERM})
Path(sys.argv[1]).write_text('received TERM')
signal.sigwait({signal.SIGUSR1})
"""
    leader = """
import json, os, subprocess, sys
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[3]], stdout=subprocess.PIPE)
assert child.stdout.readline() == b'ready\\n'
Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid(), 'child': child.pid}))
"""
    driver = f"""
if {diagnostics!r} == 'none':
    module.sys.stderr = None
elif {diagnostics!r} == 'closed':
    module.sys.stderr.close()
# Keep this handshake independent of the real five-second grace, tested separately.
module.GRACE_SECONDS = 120
original = module.group_alive
first_snapshot = True
def snapshot(pgid):
    global first_snapshot
    if first_snapshot:
        first_snapshot = False
        raise PermissionError('one unreadable cleanup snapshot')
    return original(pgid)
module.group_alive = snapshot
raise SystemExit(module.main())
"""
    owner, _ = launch([sys.executable, "-c", leader, str(ready), child, str(received)], driver=driver)
    members = read_ready(ready)
    wait_until(received.exists, "descendant to receive automatic cleanup TERM")
    contender, log = launch([sys.executable, "-c", MARK, str(admitted)])
    queued(contender, log, admitted)
    assert owner.poll() is None and running(members["child"])
    os.kill(members["child"], signal.SIGUSR1)
    stdout, _ = owner.communicate(timeout=30)
    assert owner.returncode == 0 and stdout == ""
    assert contender.wait(timeout=30) == 0 and admitted.exists()
    assert not running(members["pid"]) and not running(members["child"])


def test_ignored_inherited_sigchld_does_not_lose_the_command_status(launch):
    driver = "import signal\nsignal.signal(signal.SIGCHLD, signal.SIG_IGN)\nraise SystemExit(module.main())\n"
    process, _ = launch([sys.executable, "-c", "raise SystemExit(29)"], driver=driver)
    assert process.wait(timeout=30) == 29


@pytest.mark.parametrize("signum", [signal.SIGKILL, signal.SIGUSR1])
def test_command_signal_status_is_preserved_even_with_an_inherited_blocked_mask(launch, signum):
    driver = """
import signal
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
raise SystemExit(module.main())
"""
    command = """
import os, signal, sys
signum = int(sys.argv[1])
signal.pthread_sigmask(signal.SIG_UNBLOCK, {signum})
os.kill(os.getpid(), signum)
"""
    process, log = launch([sys.executable, "-c", command, str(signum)], driver=driver)
    assert process.wait(timeout=30) == -signum, log.read_text()


def test_macos_observer_fallback_reaps_the_command_and_keeps_its_status(launch):
    driver = """
if hasattr(module.os, 'waitid'):
    del module.os.waitid
module.sys.platform = 'darwin'
raise SystemExit(module.main())
"""
    process, log = launch([sys.executable, "-c", "raise SystemExit(19)"], driver=driver)
    assert process.wait(timeout=30) == 19, log.read_text()


def test_unreadable_cleanup_snapshot_keeps_the_slot_until_observation_recovers(launch, tmp_path):
    ready, denied, allow, admitted = [tmp_path / name for name in ("ready", "denied", "allow", "admitted")]
    driver = f"""
from pathlib import Path
original = module.process_rows
def snapshot(pid=None):
    if Path({str(ready)!r}).exists() and not Path({str(allow)!r}).exists():
        Path({str(denied)!r}).touch()
        raise PermissionError('injected unreadable process table')
    return original(pid)
module.process_rows = snapshot
raise SystemExit(module.main())
"""
    owner, log = launch([sys.executable, "-c", MARK, str(ready)], driver=driver)
    wait_until(denied.exists, "cleanup observer refusal")
    waiter, waiting_log = launch([sys.executable, "-c", MARK, str(admitted)])
    queued(waiter, waiting_log, admitted)
    assert owner.poll() is None
    assert "retaining the slot" in log.read_text()
    allow.touch()
    assert owner.wait(timeout=30) == 0
    assert waiter.wait(timeout=30) == 0 and admitted.exists()


@pytest.mark.parametrize("unreadable", [False, True], ids=["slow-snapshot", "failed-snapshot"])
def test_cleanup_grace_starts_when_the_first_signal_is_sent(monkeypatch, unreadable):
    spec = importlib.util.spec_from_file_location("local_verification_clock_test", VERIFY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clock, sent = [0], []

    def snapshot(_pgid):
        if clock[0] == 0:
            clock[0] = 100  # An observer delay longer than the cleanup grace.
            if unreadable:
                raise PermissionError("injected unreadable process table")
        return clock[0] <= 105

    def advance(_seconds):
        clock[0] += 1

    monkeypatch.setattr(module, "group_alive", snapshot)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=advance))
    monkeypatch.setattr(module, "os", SimpleNamespace(killpg=lambda pid, sig: sent.append((pid, sig, clock[0]))))
    cancel = module.Cancellation()
    cancel.receive(signal.SIGINT, None)
    module.finish_group(123, cancel)
    assert sent == [(123, signal.SIGINT, 100), (123, signal.SIGKILL, 105)]


@pytest.mark.parametrize("second_cancel", [False, True], ids=["first-cancel-grace", "second-cancel-kills"])
def test_user_cancellation_during_automatic_cleanup_is_forwarded_with_its_own_grace(monkeypatch, second_cancel):
    spec = importlib.util.spec_from_file_location("local_verification_cancellation_test", VERIFY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clock, sent = [0], []
    cancel = module.Cancellation()
    kill_at = 2 if second_cancel else 6

    def snapshot(_pgid):
        if clock[0] == 1 or (second_cancel and clock[0] == 2):
            cancel.receive(signal.SIGINT, None)
        return clock[0] <= kill_at

    def advance(_seconds):
        clock[0] += 1

    monkeypatch.setattr(module, "group_alive", snapshot)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=advance))
    monkeypatch.setattr(module, "os", SimpleNamespace(killpg=lambda pid, sig: sent.append((pid, sig, clock[0]))))
    module.finish_group(123, cancel)
    assert sent == [(123, signal.SIGTERM, 0), (123, signal.SIGINT, 1), (123, signal.SIGKILL, kill_at)]


@pytest.mark.skipif(sys.platform != "linux", reason="Linux thread-state behavior")
def test_live_thread_of_zombie_leader_is_cleaned_before_releasing_slot(launch, tmp_path):
    ready = tmp_path / "ready.json"
    child = """
import ctypes, json, os, sys, threading, time
from pathlib import Path
threading.Thread(target=time.sleep, args=(120,)).start()
Path(sys.argv[1]).write_text(json.dumps({'pid': os.getpid()}))
ctypes.CDLL(None).pthread_exit(None)
"""
    process, _ = launch([sys.executable, "-c", child, str(ready)])
    leader = read_ready(ready)["pid"]
    wait_until(lambda: Path(f"/proc/{leader}/stat").read_bytes().rpartition(b")")[2].split()[0] == b"Z",
               "leader thread to exit while another remains alive")
    assert running(leader)
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=30) == -signal.SIGTERM
    assert not running(leader)


def test_signal_between_spawn_and_its_return_still_cleans_the_spawned_group(launch, tmp_path):
    ready = tmp_path / "ready.json"
    driver = f"""
import os, signal, time
from pathlib import Path
original = module.subprocess.Popen
def spawn(*args, **kwargs):
    process = original(*args, **kwargs)
    if kwargs.get('start_new_session'):
        deadline = time.monotonic() + 30
        while not Path({str(ready)!r}).exists():
            if time.monotonic() >= deadline:
                raise RuntimeError('command never became ready')
            time.sleep(0.02)
        os.kill(os.getpid(), signal.SIGTERM)
    return process
module.subprocess.Popen = spawn
raise SystemExit(module.main())
"""
    process, _ = launch([sys.executable, "-c", OWNER, str(ready)], driver=driver)
    leader = read_ready(ready)["pid"]
    assert process.wait(timeout=30) == -signal.SIGTERM
    assert not running(leader)


def test_default_lock_uses_the_account_home_across_working_directories(launch, tmp_path):
    account = tmp_path / "account"
    driver = f"""
from types import SimpleNamespace
module.pwd.getpwuid = lambda uid: SimpleNamespace(pw_dir={str(account)!r})
raise SystemExit(module.main())
"""
    ready, admitted = tmp_path / "owner.json", tmp_path / "admitted"
    other = tmp_path / "other-checkout"
    other.mkdir()
    environments = []
    for name in ("first", "second"):
        temp, cache = tmp_path / f"{name}-temp", tmp_path / f"{name}-cache"
        temp.mkdir()
        cache.mkdir()
        environments.append({"TMPDIR": str(temp), "XDG_CACHE_HOME": str(cache)})
    owner, _ = launch([sys.executable, "-c", OWNER, str(ready)], driver=driver, default_lock=True,
                      environment=environments[0])
    leader = read_ready(ready)["pid"]
    contender, log = launch([sys.executable, "-c", MARK, str(admitted)], cwd=other, driver=driver, default_lock=True,
                            environment=environments[1])
    queued(contender, log, admitted)
    assert (account / ".cache/earningsnerd/verification.lock").is_file()
    os.kill(leader, signal.SIGUSR1)
    assert owner.wait(timeout=30) == 0 and contender.wait(timeout=30) == 0
