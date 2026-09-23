"""Offline fake-executable probes for E7 admission; never invokes Claude."""

from __future__ import annotations

import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from evals.acceptance_ai_judge_evidence import validate_judge_ledger
from evals.acceptance_ai_judge_runner import SLOTS, export_ledger, initialize, inspect, run_one
from evals.judge import _JUDGE_SYSTEM


_BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def isolated_subscription_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "isolated-subscription-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


def _controller_env() -> dict[str, str]:
    # Only this test subprocess needs package discovery. The guardian executes
    # the runner file directly and imports no repository modules.
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_BACKEND)
    return env


def _fake_cli(path: Path) -> None:
    path.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys, time\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('2.1.278 (Claude Code)')\n"
        "    raise SystemExit(0)\n"
        "pathlib.Path(__file__).with_suffix('.env.json').write_text(json.dumps(dict(os.environ)))\n"
        "text = sys.stdin.read()\n"
        "counter = pathlib.Path(__file__).with_suffix('.count')\n"
        "n = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(n + 1))\n"
        "if text.startswith('SLEEP'):\n"
        "    pathlib.Path(__file__).with_suffix('.pid').write_text(str(os.getpid()))\n"
        "    print('partial raw stdout', flush=True)\n"
        "    time.sleep(30)\n"
        "if text.startswith('RETRY') and n == 0:\n"
        "    print(json.dumps({'is_error': True, 'subtype': 'error', 'result': 'temporary'}))\n"
        "else:\n"
        "    verdict = 'FAIL' if text.startswith('FAIL') else 'PASS'\n"
        "    result = {'gate_failures': [], 'dimensions': dict.fromkeys(\n"
        "        ('faithfulness','insight','clarity','specificity'), 5),\n"
        "        'verdict': verdict, 'notes': 'fake'}\n"
        "    print(json.dumps({'is_error': False, 'subtype': 'success',\n"
        "                      'result': json.dumps(result)}))\n"
    )
    path.chmod(0o700)


def _programme(tmp_path: Path, *, input_text: str = "PASS",
               probe_text: str | None = None) -> tuple[Path, Path]:
    fake = tmp_path / "fake-claude"
    _fake_cli(fake)
    contract = tmp_path / "contract.txt"
    contract.write_text("frozen E7 contract")
    source = tmp_path / "input.txt"
    source.write_text(input_text)
    probe = tmp_path / "probe.txt"
    if probe_text is not None:
        probe.write_text(probe_text)
    root = tmp_path / "programme"
    initialize(root, cli=fake, contract=contract, system_prompt=_JUDGE_SYSTEM,
               input_paths={slot: source for slot in SLOTS},
               probe_input=probe if probe_text is not None else None)
    return root, fake


def _cleanup_recorded_fake_cli(root: Path, fake: Path) -> None:
    """Best effort only for a PID recorded for this test's fake executable."""
    pidfile = fake.with_suffix(".pid")
    if not pidfile.is_file():
        return
    try:
        pid = int(pidfile.read_text())
        with sqlite3.connect(root / "judge.sqlite3") as db:
            recorded = db.execute("SELECT cli_pid FROM calls WHERE cli_pid=?", (pid,)).fetchone()
        if recorded and os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGKILL)
    except (OSError, ValueError, sqlite3.Error):
        pass


def _process_is_terminated(pid: int) -> bool:
    """A killed orphan may remain as an unreaped Linux zombie."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    proc_status = Path(f"/proc/{pid}/status")
    try:
        return proc_status.is_file() and any(
            line.startswith("State:") and line.split()[1] == "Z"
            for line in proc_status.read_text().splitlines()
        )
    except (OSError, IndexError):
        return False


def test_reservation_verdict_and_immutable_export(tmp_path: Path) -> None:
    root, fake = _programme(tmp_path)
    result = run_one(root, "H01-candidate-1", cli=fake)
    assert result["status"] == "verdict"
    assert inspect(root)["calls"] == 1
    with pytest.raises(ValueError, match="no permitted retry"):
        run_one(root, "H01-candidate-1", cli=fake)
    record = export_ledger(root)
    ledger = json.loads((root / record["path"]).read_text())
    assert len(ledger["entries"]) == 1
    assert ledger["entries"][0]["slot_id"] == "H01-candidate-1"
    checked = validate_judge_ledger(root, record, inspect(root)["binding"]["input_sha256"])
    assert not checked["complete"]  # The remaining 120 verdicts have not run.
    assert not any(issue.startswith("entry ") for issue in checked["issues"])
    assert (root / "cli-version.stdout.raw").read_text().strip() == "2.1.278 (Claude Code)"
    assert (root / "cli-version.receipt.json").is_file()


def test_error_only_retry_and_pending_latch(tmp_path: Path) -> None:
    root, fake = _programme(tmp_path, input_text="RETRY")
    first = run_one(root, "H01-candidate-1", cli=fake)
    assert first["status"] == "cli_error"
    second = run_one(root, "H01-candidate-1", cli=fake)
    assert second["status"] == "verdict" and second["attempt"] == 2
    with pytest.raises(ValueError, match="no permitted retry"):
        run_one(root, "H01-candidate-1", cli=fake)
    with sqlite3.connect(root / "judge.sqlite3") as db:
        db.execute("INSERT INTO calls(slot,attempt,kind,status,input_sha,invocation_id) "
                   "VALUES ('H02-candidate-1',1,'substantive','reserved',?, 'fake-pending')",
                   (inspect(root)["binding"]["input_sha256"]["H02-candidate-1"],))
    with pytest.raises(ValueError, match="pending invocation"):
        run_one(root, "H03-candidate-1", cli=fake)


def test_owner_death_guardian_terminates_child_and_preserves_partial_raw(tmp_path: Path) -> None:
    root, fake = _programme(tmp_path, input_text="SLEEP")
    controller = subprocess.Popen(
        [sys.executable, "-c", "from evals.acceptance_ai_judge_runner import run_one; "
         f"run_one({str(root)!r}, 'H01-candidate-1', cli={str(fake)!r})"],
        cwd=Path(__file__).parent, env=_controller_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    pidfile = fake.with_suffix(".pid")
    deadline = time.monotonic() + 10
    try:
        while not pidfile.exists() and time.monotonic() < deadline:
            assert controller.poll() is None, controller.communicate()[1].decode()
            time.sleep(0.05)
        assert pidfile.exists(), "fake CLI did not start"
        cli_pid = int(pidfile.read_text())
        controller.kill()
        controller.wait(timeout=5)
        while time.monotonic() < deadline:
            state = inspect(root)
            if state["stop_reason"] == "owner_died_during_cli":
                break
            time.sleep(0.05)
        assert inspect(root)["stop_reason"] == "owner_died_during_cli"
        assert inspect(root)["pending"] == ["H01-candidate-1"]
        while time.monotonic() < deadline:
            try:
                os.kill(cli_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        with pytest.raises(ProcessLookupError):
            os.kill(cli_pid, 0)
        raw = next((root / "attempts").glob("*/stdout.raw"))
        assert raw.read_bytes().startswith(b"partial raw stdout")
        with pytest.raises(ValueError, match="stopped"):
            run_one(root, "H02-candidate-1", cli=fake)
    finally:
        if controller.poll() is None:
            controller.kill()
            controller.wait(timeout=5)
        _cleanup_recorded_fake_cli(root, fake)


def test_version_and_prompt_are_checked_before_judge_reservation(tmp_path: Path) -> None:
    root, fake = _programme(tmp_path)
    (root / "cli-version.stdout.raw").write_text("0.0.0\n")
    with pytest.raises(ValueError, match="frozen judge CLI"):
        run_one(root, "H01-candidate-1", cli=fake)
    assert inspect(root)["calls"] == 0

    other = tmp_path / "other-programme"
    with pytest.raises(ValueError, match="system prompt differs"):
        initialize(other, cli=fake, contract=tmp_path / "contract.txt",
                   system_prompt="different", input_paths={slot: tmp_path / "input.txt" for slot in SLOTS})
    assert not other.exists()

    wrong = tmp_path / "wrong-version"
    bad_cli = tmp_path / "bad-claude"
    _fake_cli(bad_cli)
    bad_cli.write_text(bad_cli.read_text().replace("2.1.278 (Claude Code)", "2.1.277 (Claude Code)"))
    with pytest.raises(ValueError, match="did not identify Claude Code 2.1.278"):
        initialize(wrong, cli=bad_cli, contract=tmp_path / "contract.txt",
                   system_prompt=_JUDGE_SYSTEM,
                   input_paths={slot: tmp_path / "input.txt" for slot in SLOTS})
    assert not (wrong / "judge.sqlite3").exists()


def test_cli_environment_excludes_billing_routing_and_model_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "cli-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
                 "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "ANTHROPIC_BASE_URL",
                 "CLAUDE_CODE_MODEL", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NODE_OPTIONS"):
        monkeypatch.setenv(name, "do-not-inherit")
    root, fake = _programme(tmp_path)
    assert run_one(root, "H01-candidate-1", cli=fake)["status"] == "verdict"
    child_env = json.loads(fake.with_suffix(".env.json").read_text())
    assert "HOME" in child_env
    assert all(name not in child_env for name in (
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_MODEL", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NODE_OPTIONS"))


def test_cli_settings_routing_override_is_rejected_before_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "cli-home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/settings.json").write_text(
        json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://unapproved.invalid"}}))
    monkeypatch.setenv("HOME", str(home))
    with pytest.raises(ValueError, match="model, routing or environment override"):
        _programme(tmp_path)
    assert not (tmp_path / "programme").exists()


@pytest.mark.parametrize("relative", ["CLAUDE.md", "CLAUDE.local.md", ".claude/settings.json",
                                      ".claude/settings.local.json", ".claude/rules/judge.md", ".git"])
def test_inherited_project_context_blocks_before_version_and_after_initialization(
    tmp_path: Path, relative: str,
) -> None:
    context = tmp_path / relative
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text("fake inherited project context")
    with pytest.raises(ValueError, match="inherits Claude project context"):
        _programme(tmp_path)
    assert not (tmp_path / "programme/cli-version.stdout.raw").exists()
    context.unlink()
    if relative.startswith(".claude/"):
        shutil.rmtree(tmp_path / ".claude")
    late_dir = tmp_path / "late"
    late_dir.mkdir()
    root, fake = _programme(late_dir)
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_text("late fake inherited project context")
    with pytest.raises(ValueError, match="inherits Claude project context"):
        run_one(root, "H01-candidate-1", cli=fake)
    assert inspect(root)["calls"] == 0


@pytest.mark.parametrize("probe_text", ["RETRY", "PASS"])
def test_nonverdict_quota_probe_stops_all_later_calls(tmp_path: Path, probe_text: str) -> None:
    root, fake = _programme(tmp_path, probe_text=probe_text)
    result = run_one(root, "quota-probe", cli=fake)
    assert result["status"] in {"cli_error", "invalid"}
    assert inspect(root)["stop_reason"] == "quota_probe_failed"
    assert inspect(root)["calls"] == 1
    assert (root / result["receipt_path"]).is_file()
    with pytest.raises(ValueError, match="stopped"):
        run_one(root, "H01-candidate-1", cli=fake)


def test_guardian_crash_stops_programme_and_kills_recorded_cli(tmp_path: Path) -> None:
    root, fake = _programme(tmp_path, input_text="SLEEP")
    controller = subprocess.Popen(
        [sys.executable, "-c", "from evals.acceptance_ai_judge_runner import run_one; "
         f"run_one({str(root)!r}, 'H01-candidate-1', cli={str(fake)!r})"],
        cwd=Path(__file__).parent, env=_controller_env(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 10
    try:
        guardian_pid = None
        cli_pid = None
        while time.monotonic() < deadline:
            with sqlite3.connect(root / "judge.sqlite3") as db:
                row = db.execute("SELECT guardian_pid,cli_pid FROM calls LIMIT 1").fetchone()
            if row and row[0] and row[1]:
                guardian_pid, cli_pid = row
                break
            assert controller.poll() is None
            time.sleep(0.05)
        assert guardian_pid and cli_pid
        os.kill(guardian_pid, signal.SIGKILL)
        _, error = controller.communicate(timeout=10)
        assert controller.returncode != 0 and b"guardian failed" in error
        assert inspect(root)["stop_reason"] == "transport_uncertain"
        assert inspect(root)["pending"] == ["H01-candidate-1"]
        while time.monotonic() < deadline:
            if _process_is_terminated(cli_pid):
                break
            time.sleep(0.05)
        assert _process_is_terminated(cli_pid)
    finally:
        if controller.poll() is None:
            controller.kill()
            controller.wait(timeout=5)
        _cleanup_recorded_fake_cli(root, fake)
