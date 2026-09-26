"""Prototype E7 Fable CLI admission and raw evidence capture; no implicit calls.

The operator must initialize a new programme, then explicitly call run_one.
Every launch is reserved in synchronous SQLite first. A stale pending
row, stopped programme, changed binary/input/contract, or uncertain transport
state refuses later dispatch; this module has no reset or redraw operation.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping


MODEL = "cli:claude-fable-5-1"
CLI_VERSION = "2.1.278"
CONTRACT_VERSION = "2"
CAP = 243
# Exact mirror of evals.judge._BILLING_ENV. The allowlist below also removes
# endpoint/model/proxy/Node overrides that are outside that billing set.
BILLING_ENV = frozenset({"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
                         "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"})
SAFE_ENV = frozenset({"HOME", "PATH", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL",
                      "LC_CTYPE", "USER", "LOGNAME", "SHELL", "TERM",
                      "SSL_CERT_FILE", "SSL_CERT_DIR"})
_MANAGED_SETTINGS = (Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
                     Path("/etc/claude-code/managed-settings.json"))
COMPARATOR = frozenset({"H01", "H03", "H05", "H07", "H09", "H14", "H18", "H23", "H26", "H29"})
SLOTS = {f"H{i:02d}-candidate-{draw}" for i in range(1, 31) for draw in (1, 2, 3)}
SLOTS |= {f"{holdout}-comparator-{draw}" for holdout in COMPARATOR for draw in (1, 2, 3)}
SLOTS.add("development-smoke")
_QUOTA = re.compile(r"quota|rate[ _-]?limit|usage limit|credit balance|insufficient credit|resource.exhausted", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _cli_env() -> dict[str, str]:
    """Keep local CLI/runtime basics; exclude billing, routing and model overrides."""
    env = {key: value for key, value in os.environ.items() if key in SAFE_ENV}
    if not env.get("HOME") or not Path(env["HOME"]).is_dir():
        raise ValueError("CLI subscription HOME missing")
    if BILLING_ENV & env.keys():
        raise AssertionError("judge billing environment reached CLI")
    return env


def _settings_observation() -> dict[str, str | None]:
    """Freeze known CLI settings and refuse model, endpoint, proxy or env overrides."""
    home = Path(_cli_env()["HOME"])
    paths = (home / ".claude/settings.json", home / ".claude/settings.local.json",
             home / ".claude/managed-settings.json", *_MANAGED_SETTINGS)

    def check(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"[^a-z]", "", str(key).lower())
                if any(token in normalized for token in
                       ("model", "baseurl", "apiurl", "endpoint", "proxy")) or (
                           normalized in {"env", "hooks", "statusline", "mcpservers"} and item
                       ):
                    raise ValueError("Claude settings contain a model, routing or environment override")
                check(item)

    observed: dict[str, str | None] = {}
    for path in paths:
        if path.exists():
            if not path.is_file():
                raise ValueError("Claude settings path is not a file")
            raw = path.read_bytes()
            try:
                parsed = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Claude settings are not valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("Claude settings must be a JSON object")
            check(parsed)
            observed[str(path)] = _sha(raw)
        else:
            observed[str(path)] = None
    return observed


def _verified_cli_cwd(root: Path) -> Path:
    """Refuse inherited Claude project instructions/settings and repository cwd."""
    cwd = _safe(root, "empty-cli-cwd")
    if not cwd.is_dir() or cwd.is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("CLI cwd must be an isolated directory outside the repository")
    for ancestor in (cwd, *cwd.parents):
        for relative in ("CLAUDE.md", "CLAUDE.local.md", ".claude", ".git"):
            candidate = ancestor / relative
            if candidate.exists() or candidate.is_symlink():
                raise ValueError("CLI cwd inherits Claude project context or settings")
    return cwd


def _durable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _durable_new(path: Path, data: bytes) -> None:
    """Preserve partial evidence on interruption; never replace an existing artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError("programme must be an existing absolute, non-symlink directory")
    return path.resolve(strict=True)


def _safe(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("unsafe programme path")
    path = root / relative
    if ".." in Path(relative).parts or not path.resolve().is_relative_to(root):
        raise ValueError("unsafe programme path")
    cursor = root
    for part in Path(relative).parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("symlink in programme path")
    return path


@contextmanager
def _lock(root: Path) -> Iterator[None]:
    with (root / "owner.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another E7 judge runner owns this programme") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _db(root: Path) -> sqlite3.Connection:
    db = sqlite3.connect(root / "judge.sqlite3")
    db.execute("PRAGMA synchronous=FULL")
    return db


def initialize(
    programme: Path, *, cli: Path, contract: Path,
    system_prompt: str, input_paths: Mapping[str, Path],
    probe_input: Path | None = None,
) -> dict[str, Any]:
    """Freeze all 121 judge stdin bytes, contract and explicit CLI binary identity.

    Run and retain the pinned executable's ``--version`` before any judge call.
    This is a local binary observation, not a provider authentication claim.
    """
    if set(input_paths) != SLOTS:
        raise ValueError("exact 120 E7 slots plus development-smoke required")
    try:
        from evals.judge import _JUDGE_SYSTEM  # Deferred: guardian needs no package import.
    except ImportError as exc:
        raise ValueError("repository judge contract unavailable for prompt verification") from exc
    if system_prompt != _JUDGE_SYSTEM:
        raise ValueError("system prompt differs from frozen judge contract")
    executable = Path(cli).resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("explicit executable CLI path required")
    settings = _settings_observation()
    binary_sha = _sha(executable.read_bytes())
    contract_bytes = Path(contract).read_bytes()
    if not contract_bytes:
        raise ValueError("empty judge contract")
    inputs = {slot: Path(path).read_bytes() for slot, path in input_paths.items()}
    if any(not value for value in inputs.values()):
        raise ValueError("empty judge stdin")
    probe = Path(probe_input).read_bytes() if probe_input is not None else None
    if probe is not None and not probe:
        raise ValueError("empty quota probe stdin")
    root = Path(programme)
    if not root.is_absolute() or root.exists() or root.is_symlink():
        raise ValueError("programme must be a new absolute directory")
    root.mkdir(mode=0o700, parents=False)
    cwd = root / "empty-cli-cwd"
    cwd.mkdir(mode=0o700)
    cwd = _verified_cli_cwd(root)
    version_started = _now()
    try:
        observed = subprocess.run([str(executable), "--version"], cwd=cwd,
                                  env=_cli_env(), capture_output=True, timeout=10,
                                  check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("pinned CLI --version invocation failed") from exc
    version_finished = _now()
    if len(observed.stdout) > 8192 or len(observed.stderr) > 8192:
        raise ValueError("pinned CLI --version output unexpectedly large")
    _durable_new(root / "cli-version.stdout.raw", observed.stdout)
    _durable_new(root / "cli-version.stderr.raw", observed.stderr)
    try:
        version_text = observed.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("pinned CLI --version output is not UTF-8") from exc
    if observed.returncode != 0 or not re.fullmatch(r"2\.1\.278(?: \(Claude Code\))?", version_text):
        raise ValueError("pinned CLI --version did not identify Claude Code 2.1.278")
    version_receipt = {"argv": ["claude", "--version"], "binary_sha256": binary_sha,
                       "exit_code": observed.returncode, "started_at": version_started,
                       "finished_at": version_finished,
                       "stdout_sha256": _sha(observed.stdout),
                       "stderr_sha256": _sha(observed.stderr)}
    version_receipt_bytes = _json_bytes(version_receipt)
    _durable_new(root / "cli-version.receipt.json", version_receipt_bytes)
    _durable(root / "contract.bin", contract_bytes)
    _durable(root / "system-prompt.txt", system_prompt.encode("utf-8"))
    for slot, payload in inputs.items():
        _durable(root / "inputs" / f"{slot}.txt", payload)
    if probe is not None:
        _durable(root / "inputs" / "quota-probe.txt", probe)
    binding = {"programme_id": "E7", "schema_version": 1, "model": MODEL,
               "contract_version": CONTRACT_VERSION, "cli_version": CLI_VERSION,
               "cli_version_observation": version_text,
               "cli_version_stdout_sha256": _sha(observed.stdout),
               "cli_version_stderr_sha256": _sha(observed.stderr),
               "cli_version_receipt_sha256": _sha(version_receipt_bytes),
               "cli_settings_sha256": settings,
               "cli_path": str(executable), "cli_sha256": binary_sha,
               "contract_sha256": _sha(contract_bytes),
               "system_prompt_sha256": _sha(system_prompt.encode("utf-8")),
               "input_sha256": {slot: _sha(value) for slot, value in sorted(inputs.items())},
               "probe_input_sha256": _sha(probe) if probe is not None else None,
               "cap": CAP}
    with _db(root) as db:
        db.execute("CREATE TABLE programme (id INTEGER PRIMARY KEY, binding TEXT NOT NULL, stop_reason TEXT)")
        db.execute("CREATE TABLE calls (id INTEGER PRIMARY KEY AUTOINCREMENT, slot TEXT NOT NULL, "
                   "attempt INTEGER NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, "
                   "input_sha TEXT NOT NULL, invocation_id TEXT NOT NULL UNIQUE, "
                   "owner_pid INTEGER, guardian_pid INTEGER, cli_pid INTEGER, "
                   "receipt_path TEXT, receipt_sha TEXT, UNIQUE(slot, attempt))")
        db.execute("INSERT INTO programme VALUES (1, ?, NULL)", (json.dumps(binding, sort_keys=True),))
    return binding


def _binding(root: Path, db: sqlite3.Connection, cli: Path) -> dict[str, Any]:
    row = db.execute("SELECT binding,stop_reason FROM programme WHERE id=1").fetchone()
    if row is None or row[1]:
        raise ValueError("E7 judge programme missing or stopped")
    _verified_cli_cwd(root)
    binding = json.loads(row[0])
    actual_cli = Path(cli).resolve(strict=True)
    if (str(actual_cli) != binding["cli_path"] or _sha(actual_cli.read_bytes()) != binding["cli_sha256"] or
            _sha((root / "contract.bin").read_bytes()) != binding["contract_sha256"] or
            _sha((root / "system-prompt.txt").read_bytes()) != binding["system_prompt_sha256"] or
            _sha((root / "cli-version.stdout.raw").read_bytes()) != binding["cli_version_stdout_sha256"] or
            _sha((root / "cli-version.stderr.raw").read_bytes()) != binding["cli_version_stderr_sha256"] or
            _sha((root / "cli-version.receipt.json").read_bytes()) != binding["cli_version_receipt_sha256"] or
            binding["cap"] != CAP or binding["model"] != MODEL or
            binding["contract_version"] != CONTRACT_VERSION or binding["cli_version"] != CLI_VERSION):
        raise ValueError("frozen judge CLI, contract or prompt changed")
    if _settings_observation() != binding["cli_settings_sha256"]:
        raise ValueError("Claude CLI settings changed since version observation")
    version_receipt = json.loads((root / "cli-version.receipt.json").read_bytes())
    if (version_receipt.get("argv") != ["claude", "--version"] or
            version_receipt.get("binary_sha256") != binding["cli_sha256"] or
            version_receipt.get("exit_code") != 0 or
            version_receipt.get("stdout_sha256") != binding["cli_version_stdout_sha256"] or
            version_receipt.get("stderr_sha256") != binding["cli_version_stderr_sha256"] or
            (root / "cli-version.stdout.raw").read_text(encoding="utf-8").strip() !=
            binding["cli_version_observation"]):
        raise ValueError("frozen CLI version observation changed")
    for slot, digest in binding["input_sha256"].items():
        if _sha(_safe(root, f"inputs/{slot}.txt").read_bytes()) != digest:
            raise ValueError("frozen judge input changed")
    if binding["probe_input_sha256"] is not None and _sha(
        _safe(root, "inputs/quota-probe.txt").read_bytes()
    ) != binding["probe_input_sha256"]:
        raise ValueError("frozen quota probe input changed")
    return binding


def _argv(kind: str, system_prompt: str) -> list[str]:
    prefix = ["claude", "-p", "--model", "claude-fable-5-1", "--output-format", "json"]
    return (prefix + ["--system-prompt", system_prompt, "--tools", "",
                      "--strict-mcp-config", "--no-session-persistence"] if kind == "substantive"
            else prefix + ["--tools", "", "--strict-mcp-config", "--no-session-persistence"])


def _classify(stdout: bytes, stderr: bytes, exit_code: int, kind: str) -> str:
    if exit_code != 0:
        return "cli_error"
    try:
        outer = json.loads(stdout.decode("utf-8"))
        if not isinstance(outer, dict):
            return "invalid"
        if outer.get("is_error") is True or outer.get("subtype") not in (None, "success"):
            return "cli_error"
        if outer.get("is_error") is not False or not isinstance(outer.get("result"), str):
            return "invalid"
        if kind == "quota_probe":
            return "verdict" if outer["result"].strip() == "OK" else "invalid"
        result = json.loads(outer["result"])
        if (not isinstance(result, dict) or set(result) != {"gate_failures", "dimensions", "verdict", "notes"} or
                result.get("verdict") not in {"PASS", "FAIL"} or
                not isinstance(result.get("gate_failures"), list) or
                any(not isinstance(item, str) or not item.strip()
                    for item in result["gate_failures"]) or
                not isinstance(result.get("dimensions"), dict) or
                set(result["dimensions"]) != {"faithfulness", "insight", "clarity", "specificity"} or
                any(type(n) is not int or not 1 <= n <= 5 for n in result["dimensions"].values()) or
                not isinstance(result.get("notes"), str)):
            return "invalid"
        return "verdict"
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return "invalid"


def _stop(db: sqlite3.Connection, reason: str) -> None:
    db.execute("UPDATE programme SET stop_reason=COALESCE(stop_reason, ?) WHERE id=1", (reason,))
    db.commit()


def _terminate_group(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def _kill_recorded_cli(db: sqlite3.Connection, call_id: int) -> None:
    """Fail closed if the guardian itself dies while its CLI child is live."""
    row = db.execute("SELECT cli_pid FROM calls WHERE id=? AND status='reserved'", (call_id,)).fetchone()
    pid = row[0] if row else None
    if type(pid) is not int or pid <= 0:
        return
    try:
        if os.getpgid(pid) == pid:  # CLI uses start_new_session=True.
            os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _guardian_main(control_fd: int, programme: str, call_id: int, timeout: int) -> int:
    """One-call child supervisor. EOF on the owner pipe kills the CLI group."""
    root = _root(Path(programme))
    done = threading.Event()
    owner_lost = threading.Event()
    child: subprocess.Popen[bytes] | None = None

    def owner_gone() -> None:
        if done.is_set():
            return
        owner_lost.set()
        if child is not None:
            _terminate_group(child)
        try:
            with _db(root) as stop_db:
                _stop(stop_db, "owner_died_during_cli")
        except sqlite3.Error:
            pass  # The durable reserved row still prevents any redraw.

    def watch_owner() -> None:
        try:
            while os.read(control_fd, 1):
                pass
            owner_gone()
        except OSError:
            owner_gone()

    threading.Thread(target=watch_owner, daemon=True).start()
    try:
        with _db(root) as db:
            row = db.execute("SELECT slot,attempt,kind,input_sha,status FROM calls WHERE id=?", (call_id,)).fetchone()
            programme_row = db.execute("SELECT binding,stop_reason FROM programme WHERE id=1").fetchone()
            if row is None or row[4] != "reserved" or programme_row is None or programme_row[1]:
                raise ValueError("guardian reservation missing or programme stopped")
            slot, attempt, kind, input_sha, _ = row
            binding = json.loads(programme_row[0])
            payload = sys.stdin.buffer.read()
            if _sha(payload) != input_sha or _sha(_safe(root, f"inputs/{slot}.txt").read_bytes()) != input_sha:
                raise ValueError("guardian stdin differs from reservation")
            _binding(root, db, Path(binding["cli_path"]))
            if owner_lost.is_set():
                raise ValueError("owner died before CLI dispatch")
            relative = f"attempts/{call_id:03d}-{slot}-{attempt}"
            directory = _safe(root, relative)
            directory.mkdir(mode=0o700, parents=True, exist_ok=False)
            stdout_path, stderr_path = directory / "stdout.raw", directory / "stderr.txt"
            argv = _argv(kind, (root / "system-prompt.txt").read_text(encoding="utf-8"))
            child_env = _cli_env()
            cwd = _verified_cli_cwd(root)
            with stdout_path.open("xb") as stdout_file, stderr_path.open("xb") as stderr_file:
                child = subprocess.Popen([binding["cli_path"], *argv[1:]], stdin=subprocess.PIPE,
                                         stdout=stdout_file, stderr=stderr_file, env=child_env,
                                         cwd=cwd, start_new_session=True)
                if owner_lost.is_set():
                    _terminate_group(child)
                    raise ValueError("owner died while CLI started")
                db.execute("UPDATE calls SET guardian_pid=?,cli_pid=? WHERE id=? AND status='reserved'",
                           (os.getpid(), child.pid, call_id))
                db.commit()
                try:
                    try:
                        child.communicate(payload, timeout=timeout)
                    except subprocess.TimeoutExpired:
                        _terminate_group(child)
                        _stop(db, "cli_timeout_uncertain")
                        raise
                finally:
                    stdout_file.flush()
                    stderr_file.flush()
                    os.fsync(stdout_file.fileno())
                    os.fsync(stderr_file.fileno())
            if owner_lost.is_set():
                _stop(db, "owner_died_during_cli")
                raise ValueError("owner died during CLI invocation")
            stdout, stderr = stdout_path.read_bytes(), stderr_path.read_bytes()
            result = {"call_id": call_id, "exit_code": child.returncode,
                      "stdout_sha256": _sha(stdout), "stderr_sha256": _sha(stderr),
                      "guardian_pid": os.getpid(), "cli_pid": child.pid}
            _durable_new(directory / "guardian-result.json", _json_bytes(result))
            done.set()
            sys.stdout.buffer.write(_json_bytes(result))
            sys.stdout.buffer.flush()
            return 0
    except BaseException as exc:
        if child is not None:
            _terminate_group(child)
        with _db(root) as db:
            _stop(db, "guardian_or_transport_uncertain")
        sys.stderr.write(f"guardian stopped: {type(exc).__name__}: {exc}\n")
        return 75
    finally:
        os.close(control_fd)


def run_one(programme: Path, slot: str, *, cli: Path, timeout_seconds: int = 300) -> dict[str, Any]:
    """Launch one explicitly requested Fable call; never selects another slot itself."""
    root = _root(programme)
    if slot not in SLOTS | {"quota-probe"}:
        raise ValueError("unknown E7 judge slot")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 300:
        raise ValueError("timeout must be 1..300 seconds")
    with _lock(root), _db(root) as db:
        binding = _binding(root, db, cli)
        if db.execute("SELECT 1 FROM calls WHERE status='reserved' LIMIT 1").fetchone():
            raise ValueError("pending invocation is uncertain; dispatch stopped")
        history = db.execute("SELECT attempt,status,input_sha FROM calls WHERE slot=? ORDER BY id", (slot,)).fetchall()
        if slot == "quota-probe":
            if binding["probe_input_sha256"] is None or history:
                raise ValueError("quota probe absent from binding or already attempted")
            attempt, kind, input_sha = 1, "quota_probe", binding["probe_input_sha256"]
        else:
            if len(history) >= 2 or (history and history[-1][1] != "cli_error"):
                raise ValueError("slot has verdict or no permitted retry")
            attempt, kind, input_sha = len(history) + 1, "substantive", binding["input_sha256"][slot]
            if history and history[-1][2] != input_sha:
                raise ValueError("retry input differs")
        count = db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        if count >= CAP:
            raise ValueError("243-call absolute ceiling reached")
        input_rel = f"inputs/{slot}.txt"
        payload = _safe(root, input_rel).read_bytes()
        if _sha(payload) != input_sha:
            raise ValueError("input changed before reservation")
        invocation_id = uuid.uuid4().hex
        db.execute("INSERT INTO calls(slot,attempt,kind,status,input_sha,invocation_id,owner_pid) "
                   "VALUES (?,?,?,'reserved',?,?,?)", (slot, attempt, kind, input_sha, invocation_id,
                                                       os.getpid()))
        db.commit()  # Durable pending reservation precedes any subprocess creation.
        call_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        argv = _argv(kind, (root / "system-prompt.txt").read_text(encoding="utf-8"))
        guardian: subprocess.Popen[bytes] | None = None
        reader, writer = os.pipe()
        started = _now()
        try:
            guardian = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--e7-internal-guardian",
                 str(reader), str(root), str(call_id), str(timeout_seconds)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                pass_fds=(reader,), start_new_session=True,
            )
            os.close(reader)
            reader = -1
            guardian_out, guardian_err = guardian.communicate(payload, timeout=timeout_seconds + 15)
            if guardian.returncode != 0:
                raise ValueError("guardian failed; reserved invocation remains uncertain: " +
                                 guardian_err.decode("utf-8", "replace")[:500])
            guardian_result = json.loads(guardian_out)
            if type(guardian_result) is not dict or guardian_result.get("call_id") != call_id:
                raise ValueError("guardian returned mismatched call")
            relative = f"attempts/{call_id:03d}-{slot}-{attempt}"
            stdout_rel, stderr_rel, receipt_rel = (f"{relative}/{name}" for name in
                                                  ("stdout.raw", "stderr.txt", "receipt.json"))
            sidecar = _safe(root, f"{relative}/guardian-result.json").read_bytes()
            if sidecar != guardian_out:
                raise ValueError("guardian sidecar differs from returned result")
            stdout = _safe(root, stdout_rel).read_bytes()
            stderr = _safe(root, stderr_rel).read_bytes()
            if (_sha(stdout) != guardian_result.get("stdout_sha256") or
                    _sha(stderr) != guardian_result.get("stderr_sha256") or
                    type(guardian_result.get("exit_code")) is not int):
                raise ValueError("guardian raw CLI evidence changed")
            exit_code = guardian_result["exit_code"]
        except BaseException:
            _stop(db, "transport_uncertain")
            if guardian is not None and guardian.poll() is None:
                os.close(writer)  # Guardian watches EOF and terminates the CLI group.
                writer = -1
                try:
                    guardian.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    _terminate_group(guardian)
            _kill_recorded_cli(db, call_id)
            raise
        finally:
            if reader >= 0:
                os.close(reader)
            if writer >= 0:
                os.close(writer)
        finished = _now()
        status = _classify(stdout, stderr, exit_code, kind)
        receipt = {"schema_version": 1, "programme_id": "E7", "slot_id": slot,
                   "attempt": attempt, "kind": kind, "invocation_id": invocation_id,
                   "model": MODEL, "contract_version": CONTRACT_VERSION,
                   "cli_version": CLI_VERSION, "auth_mode": "subscription_oauth_no_api_key",
                   "argv": argv, "exit_code": exit_code,
                   "started_at": started, "finished_at": finished,
                   "input_sha256": input_sha, "stdout_sha256": _sha(stdout),
                   "stderr_sha256": _sha(stderr)}
        try:
            _durable_new(_safe(root, receipt_rel), _json_bytes(receipt))
            db.execute("UPDATE calls SET status=?,receipt_path=?,receipt_sha=? WHERE id=? AND status='reserved'",
                       (status, receipt_rel, _sha(_json_bytes(receipt)), call_id))
            if kind == "quota_probe" and status != "verdict":
                _stop(db, "quota_probe_failed")
            elif status == "invalid":
                _stop(db, "invalid_cli_result")
            elif status == "cli_error" and _QUOTA.search((stdout + b"\n" + stderr).decode("utf-8", "replace")):
                _stop(db, "quota_error")
            db.commit()
        except BaseException:
            _stop(db, "receipt_or_status_uncertain")
            raise
        return {"slot_id": slot, "attempt": attempt, "status": status,
                "invocation_id": invocation_id, "receipt_path": receipt_rel}


def inspect(programme: Path) -> dict[str, Any]:
    """Read-only progress; a reserved row means an uncertain call, never a retry cue."""
    root = _root(programme)
    with sqlite3.connect((root / "judge.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT binding,stop_reason FROM programme WHERE id=1").fetchone()
        if row is None:
            raise ValueError("judge programme missing")
        calls = db.execute("SELECT slot,attempt,status,receipt_path FROM calls ORDER BY id").fetchall()
    latest = {slot: (attempt, status) for slot, attempt, status, _ in calls}
    pending = [slot for slot, _, status, _ in calls if status == "reserved"]
    verdict_slots = sorted({slot for slot, _, status, _ in calls
                            if status == "verdict" and slot != "quota-probe"})
    return {"binding": json.loads(row[0]), "stop_reason": row[1], "calls": len(calls),
            "pending": pending, "verdict_slots": verdict_slots,
            "retryable_cli_errors": sorted(slot for slot, (attempt, status) in latest.items()
                                           if row[1] is None and status == "cli_error" and attempt == 1),
            "complete": row[1] is None and not pending and len(verdict_slots) == 121}


def export_ledger(programme: Path) -> dict[str, str]:
    """Materialize an immutable, validator-compatible snapshot in the programme."""
    root = _root(programme)
    with _lock(root), sqlite3.connect((root / "judge.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("SELECT id,slot,attempt,kind,status,input_sha,receipt_path,receipt_sha "
                          "FROM calls ORDER BY id").fetchall()
        if any(row[4] == "reserved" for row in rows):
            raise ValueError("pending call cannot be exported as completed evidence")
        entries = []
        for _, slot, attempt, kind, _, input_sha, receipt_rel, receipt_sha in rows:
            receipt_path = _safe(root, receipt_rel)
            if _sha(receipt_path.read_bytes()) != receipt_sha:
                raise ValueError("retained receipt changed")
            receipt = json.loads(receipt_path.read_text())
            parent = receipt_path.parent
            stdout, stderr = parent / "stdout.raw", parent / "stderr.txt"
            if (_sha(stdout.read_bytes()) != receipt["stdout_sha256"] or
                    _sha(stderr.read_bytes()) != receipt["stderr_sha256"]):
                raise ValueError("retained raw CLI bytes changed")
            input_rel = f"inputs/{slot}.txt"
            if _sha(_safe(root, input_rel).read_bytes()) != input_sha:
                raise ValueError("retained CLI stdin changed")
            entries.append({"slot_id": slot, "attempt": attempt, "kind": kind,
                            "input": {"path": input_rel, "sha256": input_sha},
                            "stdout": {"path": str(stdout.relative_to(root)),
                                       "sha256": receipt["stdout_sha256"]},
                            "stderr": {"path": str(stderr.relative_to(root)),
                                       "sha256": receipt["stderr_sha256"]},
                            "receipt": {"path": receipt_rel, "sha256": receipt_sha}})
        ledger = {"schema_version": 1, "programme_id": "E7", "kind": "e7_fable_cli_ledger",
                  "model": MODEL, "contract_version": CONTRACT_VERSION,
                  "cli_version": CLI_VERSION, "entries": entries}
        data = _json_bytes(ledger)
        path = root / f"judge-ledger-{len(rows):03d}-{_sha(data)[:12]}.json"
        if path.exists() and path.read_bytes() != data:
            raise ValueError("ledger snapshot path collision")
        if not path.exists():
            _durable(path, data)
        return {"path": path.name, "sha256": _sha(data)}


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "--e7-internal-guardian":
        raise SystemExit(_guardian_main(int(sys.argv[2]), sys.argv[3],
                                        int(sys.argv[4]), int(sys.argv[5])))
    raise SystemExit("This module exposes initialize/run_one/inspect/export_ledger only; "
                     "there is no implicit queue runner.")
