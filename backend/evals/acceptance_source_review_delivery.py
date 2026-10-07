"""Non-admitting native-delivery adapter for one reserved E7 source-review prompt.

This is the thin, route-specific transport candidate the execution custody seam lacked. It
dispatches exactly the reserved ``prompt.bin`` bytes to one consumer route — the Claude Code CLI
in print mode (``claude -p``, prompt on standard input, ``stream-json`` output) — retains the
complete request, delivered bytes, raw process streams and finish metadata in an immutable
delivery ledger, and proposes a settlement for the existing journal.  It never initializes a
journal, never renders a prompt, never retries, never redispatches a pending reservation, and never
attests provider delivery, model attention, source review or admission.

Three things stay separate throughout:

* **custody** — native evidence members supplied by the caller are hashed and each receives one
  disposition against the delivered bytes (``delivered_inline`` only when the member's exact bytes
  occur contiguously inside the reserved prompt; otherwise ``retained_not_delivered``); a hash
  pointer or compact substitute never counts for another member;
* **delivery** — the bytes written to the route process's standard input are exactly the reserved
  prompt bytes; this is process-level delivery, not verified model ingestion
  (``provider_delivery_verified`` is always ``false``);
* **output** — the consumer output is the ``result`` text of the stream, retained by hash and
  proposed as the settlement artifact; the whole raw stream is retained alongside it.

Every outcome fails closed: any assumed stream field that is absent classifies the attempt as
``failed`` (never ``complete``), a timeout or a stream without a result event is ``unknown`` and is
left pending for the operator, and a second dispatch of the same reservation into the same delivery
root is refused before the route child starts. The ledger root is that lock; the journal keeps no
dispatch memory, so exactly one delivery root per journal is an operator rule, not a guarantee.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import evals.acceptance_source_review_execution as execution
from evals.acceptance_source_review_graph import ATTESTATION_FLAGS


SCHEMA_VERSION = 1
REQUEST_KIND = "e7_native_delivery_request"
RECEIPT_KIND = "e7_native_delivery_receipt"
VALIDATION_KIND = "e7_native_delivery_validation"
CLASSIFIER_VERSION = 2
ROUTE = "claude_code_cli_print"
ROUTE_PROVIDER = "anthropic-claude-code-cli"
# Fixed route overhead: replaces the CLI's default agent system prompt so the model-visible input is
# the reserved prompt plus this constant (recorded by hash) plus whatever the CLI itself adds.
ROUTE_SYSTEM_PROMPT = (
    "You are the consumer of one exact source-review input delivered on standard input. "
    "Reply only to that input. No tools are available. Do not add a preamble or commentary "
    "beyond what the input instructs."
)
DOCUMENTED_STDIN_CAP_BYTES = 10 * 1024 * 1024  # code.claude.com/docs/en/headless: "capped at 10MB"
MIN_MEMBER_BYTES = 64  # shorter members match trivially, so their delivery is indeterminate
OUTCOMES = ("complete", "truncated", "compacted", "failed", "unknown")
DISPOSITIONS = ("delivered_inline", "retained_not_delivered", "indeterminate")
# Exact mirror of evals.judge._BILLING_ENV; the allowlist below is what actually reaches the child.
BILLING_ENV = frozenset({"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
                         "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"})
SAFE_ENV = frozenset({"HOME", "PATH", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "LC_CTYPE", "USER",
                      "LOGNAME", "SHELL", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR"})
PASSTHROUGH_ENV = frozenset({"HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy",
                             "no_proxy", "NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE"})
_MANAGED_SETTINGS = ("/Library/Application Support/ClaudeCode/managed-settings.json",
                     "/etc/claude-code/managed-settings.json")
_USER_SETTINGS = (".claude/settings.json", ".claude/settings.local.json", ".claude/managed-settings.json")
LIMITATIONS = (
    "Delivery is process-level: the bytes written to the route's standard input equal the reserved prompt; provider ingestion, model attention and the CLI's own wrapper tokens are not verified.",
    "Stream finish metadata (stop_reason, usage, subtype, compaction) is recorded as the route reported it; a required field that is absent classifies the attempt as failed, never complete.",
    "A native member counts as delivered only when its exact bytes occur inside the reserved prompt; attachments, tool-mediated file reads and binary modalities are unsupported by this route, so members above the operator stdin cap are retained_not_delivered.",
    "Usage and cost are route-reported estimates, not billing; the journal context_id is operator-chosen and the CLI session_id is retained only as route evidence.",
    "No source review, source-role readiness, E7 coverage_status or E7 admission is attested; an unknown outcome stays pending with no automatic retirement or redispatch.",
    "The redispatch lock is the per-delivery-root ledger directory and the journal keeps no dispatch memory, so one delivery root per journal is an operator rule; user-level Claude memory, rules, plugins and hook settings are excluded only by the pre-dispatch home observation, and the raw streams are retained unredacted for local custody.",
)

_RESERVATION = re.compile(r"[0-9a-f]{32}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SYNTHETIC_ACCESSION = re.compile(r"0000000000-[0-9]{2}-[0-9]{6}")
_LIMIT_KEYS = frozenset({"max_stdin_bytes", "timeout_seconds", "max_budget_usd"})
_MEMBER_KEYS = frozenset({"label", "bytes", "required"})
_EXPECTED_KEYS = frozenset({"sha256", "byte_length"})
_LEDGER_FILES = ("request.json", "stdin.bin", "cli-version.stdout.raw", "cli-version.stderr.raw",
                 "stdout.raw", "stderr.raw", "receipt.json")
_STATUS_BY_OUTCOME = {"complete": ("eligible",), "truncated": ("truncated",), "compacted": ("compacted",),
                      "failed": ("failed", "retired"), "unknown": ("retired", "failed")}
_SETTINGS_OVERRIDE_TOKENS = ("model", "baseurl", "apiurl", "endpoint", "proxy")
_SETTINGS_OVERRIDE_KEYS = frozenset({"env", "hooks", "statusline", "mcpservers", "enabledplugins"})
# Model-visible context the CLI loads from the home directory independently of cwd or argv.
_HOME_CONTEXT = (".claude/CLAUDE.md", ".claude/rules", ".claude/plugins/installed_plugins.json")


@dataclass(frozen=True, slots=True)
class RouteInvocation:
    """One process launch: argv, exact stdin bytes, allow-listed env and file-backed streams."""

    argv: tuple[str, ...]
    stdin_bytes: bytes
    env: Mapping[str, str]
    cwd: Path
    timeout_seconds: int
    stdout_path: Path
    stderr_path: Path


@dataclass(frozen=True, slots=True)
class RouteProcessResult:
    exit_code: int | None
    timed_out: bool
    elapsed_seconds: float
    kill_signal: str | None = None


RouteRunner = Callable[[RouteInvocation], RouteProcessResult]


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                          allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("value is not canonical JSON") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _token(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != keys:
        raise ValueError(f"{name} must be an object with exactly: {', '.join(sorted(keys))}")
    return value


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _terminate_group(proc: subprocess.Popen[bytes]) -> str | None:
    """SIGTERM the child's process group, escalate to SIGKILL, and reap; returns the signal used."""
    if proc.poll() is not None:
        return None
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        proc.wait()
        return None
    try:
        proc.wait(timeout=5)
        return "SIGTERM"
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        return "SIGKILL"


def run_route_process(invocation: RouteInvocation) -> RouteProcessResult:
    """Default runner: file-backed streams opened create-once, own session, group kill on timeout.

    Partial stdout/stderr survive a timeout because the child writes straight into the ledger
    files; nothing is buffered in this process. There is no retry.
    """
    kill_signal = None
    timed_out = False
    started = time.monotonic()
    with invocation.stdout_path.open("xb") as stdout_file, invocation.stderr_path.open("xb") as stderr_file:
        proc = subprocess.Popen(  # argv is the frozen route list, never shell-interpreted
            list(invocation.argv), stdin=subprocess.PIPE, stdout=stdout_file, stderr=stderr_file,
            env=dict(invocation.env), cwd=str(invocation.cwd), start_new_session=True,
        )
        try:
            try:
                # communicate() tolerates a child that exits before reading all of stdin
                # (BrokenPipe/EPIPE are swallowed by CPython), so early auth/quota exits are
                # classified from the retained streams rather than raised here.
                proc.communicate(invocation.stdin_bytes, timeout=invocation.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                kill_signal = _terminate_group(proc)
        except BaseException:
            _terminate_group(proc)
            raise
        finally:
            for stream in (stdout_file, stderr_file):
                stream.flush()
                os.fsync(stream.fileno())
    return RouteProcessResult(exit_code=proc.returncode, timed_out=timed_out,
                              elapsed_seconds=time.monotonic() - started, kill_signal=kill_signal)


def native_member_dispositions(
    prompt_bytes: bytes,
    native_members: Any,
    *,
    expected_members: Any = None,
) -> dict[str, Any]:
    """Give every declared native member exactly one disposition against the delivered bytes.

    ``native_members`` is an ordered list of ``{label, bytes, required}``. ``expected_members``
    optionally maps labels to ``{sha256, byte_length}`` from an external custody receipt; a member
    whose bytes differ from its expected identity is rejected rather than relabelled. Members are
    compared by exact bytes, never by hash, so compact text or a manifest pointer cannot stand in
    for another member. ``complete_native_delivery`` is ``None`` with no members, else ``True`` only
    when every required member is ``delivered_inline``.
    """
    if type(prompt_bytes) is not bytes:
        raise ValueError("prompt_bytes must be bytes")
    if type(native_members) is not list:
        raise ValueError("native_members must be a list")
    if expected_members is not None and (
        type(expected_members) is not dict or any(type(key) is not str for key in expected_members)
    ):
        raise ValueError("expected_members must map labels to identities")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in native_members:
        member = _object(value, _MEMBER_KEYS, "native member")
        label = _token(member["label"], _LABEL, "native member label")
        data = member["bytes"]
        if type(data) is not bytes or type(member["required"]) is not bool:
            raise ValueError(f"native member {label} needs bytes and a boolean required flag")
        if label in seen:
            raise ValueError(f"native member {label} is declared twice")
        seen.add(label)
        digest = _sha(data)
        if expected_members is not None:
            expected = _object(expected_members.get(label), _EXPECTED_KEYS, f"expected member {label}")
            if expected["sha256"] != digest or expected["byte_length"] != len(data):
                raise ValueError(f"native member {label} differs from its expected identity")
        if len(data) < MIN_MEMBER_BYTES:
            disposition = "indeterminate"
        elif data in prompt_bytes:
            disposition = "delivered_inline"
        else:
            disposition = "retained_not_delivered"
        records.append({"label": label, "sha256": digest, "byte_length": len(data),
                        "required": member["required"], "disposition": disposition})
    if expected_members is not None and set(expected_members) - seen:
        raise ValueError("expected_members names members that were not supplied")
    required = [record for record in records if record["required"]]
    complete = None if not records else all(r["disposition"] == "delivered_inline" for r in required)
    return {"members": records, "native_members_declared": len(records),
            "required_members_declared": len(required), "complete_native_delivery": complete}


def _limits(value: Any) -> dict[str, Any]:
    limits = _object(value, _LIMIT_KEYS, "limits")
    stdin_cap, timeout, budget = limits["max_stdin_bytes"], limits["timeout_seconds"], limits["max_budget_usd"]
    if type(stdin_cap) is not int or not 1 <= stdin_cap <= DOCUMENTED_STDIN_CAP_BYTES:
        raise ValueError(f"max_stdin_bytes must be 1..{DOCUMENTED_STDIN_CAP_BYTES} (documented CLI stdin cap)")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("timeout_seconds must be 1..3600")
    if budget is not None and (type(budget) not in (int, float) or not 0 < budget <= 100):
        raise ValueError("max_budget_usd must be null or a positive number of at most 100")
    return {"max_stdin_bytes": stdin_cap, "timeout_seconds": timeout, "max_budget_usd": budget}


def _child_env(environment: Mapping[str, str], passthrough: tuple[str, ...]) -> tuple[dict[str, str], dict[str, Any]]:
    """Allow-list the parent environment; record names only, never values."""
    if not isinstance(environment, Mapping) or any(
        type(key) is not str or type(value) is not str for key, value in environment.items()
    ):
        raise ValueError("environment must map string names to string values")
    if type(passthrough) is not tuple or any(type(name) is not str for name in passthrough):
        raise ValueError("passthrough_env must be a tuple of variable names")
    if set(passthrough) - PASSTHROUGH_ENV:
        raise ValueError("passthrough_env names a variable outside the allowed proxy/CA set")
    allowed = SAFE_ENV | set(passthrough)
    env = {key: value for key, value in environment.items() if key in allowed}
    if not env.get("HOME") or not Path(env["HOME"]).is_dir():
        raise ValueError("route HOME missing; the CLI subscription login needs a home directory")
    if BILLING_ENV & env.keys():
        raise AssertionError("billing environment reached the route child")
    record = {"env_passed_names": sorted(env), "env_dropped_count": len(environment) - len(env),
              "passthrough_declared": sorted(passthrough)}
    return env, record


def _settings_observation(home: Path) -> dict[str, str | None]:
    """Freeze the CLI settings files by hash and refuse model, routing, hook or env overrides.

    Mirrors the E7 judge runner's observation. The keys are recorded relative to the home directory
    so receipts carry no absolute home path.
    """
    def check(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"[^a-z]", "", str(key).lower())
                if any(token in normalized for token in _SETTINGS_OVERRIDE_TOKENS) or (
                    normalized in _SETTINGS_OVERRIDE_KEYS and item
                ):
                    raise ValueError("Claude settings contain a model, routing, hook or environment override")
                check(item)

    observed: dict[str, str | None] = {}
    candidates = [(f"~/{relative}", home / relative) for relative in _USER_SETTINGS]
    candidates += [(managed, Path(managed)) for managed in _MANAGED_SETTINGS]
    for label, path in candidates:
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
            observed[label] = _sha(raw)
        else:
            observed[label] = None
    # User memory, rules and plugins are injected regardless of --system-prompt and cwd; they would
    # make the delivered context more than the reserved prompt, so their presence refuses dispatch.
    for relative in _HOME_CONTEXT:
        path = home / relative
        present = path.exists() or path.is_symlink()
        observed[f"~/{relative}"] = "present" if present else None
        if present:
            raise ValueError(f"route HOME carries user-level Claude context (~/{relative}); relocate it before dispatch")
    return observed


def _verify_project_isolation(path: Path, name: str) -> None:
    """Refuse a path inside the repository or under any inherited Claude project context."""
    if path.is_relative_to(_repository_root()):
        raise ValueError(f"{name} must be outside the repository")
    for ancestor in (path, *path.parents):
        for relative in ("CLAUDE.md", "CLAUDE.local.md", ".claude", ".git"):
            candidate = ancestor / relative
            if candidate.exists() or candidate.is_symlink():
                raise ValueError(f"{name} inherits Claude project context or settings")


def _verified_cwd(cwd: Path) -> Path:
    """The route runs in an empty private directory with no inherited Claude project context."""
    if not cwd.is_dir() or any(cwd.iterdir()):
        raise ValueError("route cwd must be an empty directory")
    _verify_project_isolation(cwd, "route cwd")
    return cwd


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path, home: Path) -> str:
    """Record an executable path home-relatively so receipts carry no account-named home path."""
    try:
        return "~/" + path.relative_to(home.resolve()).as_posix()
    except ValueError:
        return str(path)


def _prove_hard_links(delivery_root: Path) -> None:
    """The ledger publishes through os.link; a root that cannot link would fail mid-dispatch."""
    probe = delivery_root / f".link-probe-{os.getpid()}"
    linked = delivery_root / f".link-probe-{os.getpid()}.linked"
    try:
        probe.write_bytes(b"")
        os.link(probe, linked)
    except OSError as exc:
        raise ValueError("delivery_root does not support hard links; choose a local non-synced volume") from exc
    finally:
        linked.unlink(missing_ok=True)
        probe.unlink(missing_ok=True)


def _cli_identity(cli_path: Any) -> tuple[Path, str]:
    if not isinstance(cli_path, (str, Path)):
        raise ValueError("cli_path must be an absolute executable path")
    executable = Path(cli_path)
    if not executable.is_absolute():
        raise ValueError("cli_path must be an absolute executable path")
    executable = executable.resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("cli_path is not an executable file")
    return executable, _file_sha(executable)


def _observe_version(
    executable: Path, *, provider_version: str, env: Mapping[str, str], runner: RouteRunner
) -> dict[str, Any]:
    """Run the pinned executable's ``--version`` and require the journal contract's version."""
    with tempfile.TemporaryDirectory(prefix="e7-delivery-version-") as temporary:
        directory = Path(temporary)
        cwd = directory / "cwd"
        cwd.mkdir(mode=0o700)
        invocation = RouteInvocation(
            argv=(str(executable), "--version"), stdin_bytes=b"", env=env, cwd=_verified_cwd(cwd),
            timeout_seconds=10, stdout_path=directory / "stdout.raw", stderr_path=directory / "stderr.raw",
        )
        result = runner(invocation)
        stdout = invocation.stdout_path.read_bytes() if invocation.stdout_path.exists() else b""
        stderr = invocation.stderr_path.read_bytes() if invocation.stderr_path.exists() else b""
    if result.timed_out or len(stdout) > 8192 or len(stderr) > 8192:
        raise ValueError("pinned CLI --version timed out or produced unexpectedly large output")
    try:
        text = stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("pinned CLI --version output is not UTF-8") from exc
    if result.exit_code != 0 or re.fullmatch(re.escape(provider_version) + r"(?: \(Claude Code\))?", text) is None:
        raise ValueError(f"pinned CLI --version did not identify {provider_version}; refusing dispatch (drift)")
    return {"observed": text, "stdout": stdout, "stderr": stderr, "exit_code": result.exit_code}


def _journal_binding(journal_root: Path) -> dict[str, Any]:
    with execution._connect(journal_root, read_only=True) as db:
        binding = execution._load_binding(journal_root, db)
    if binding["schema_version"] != 1:
        raise ValueError("joint-input journal needs a separately versioned delivery contract")
    return binding


def _pending_reservation(journal_root: Path, reservation_id: str, prompt_bytes: bytes) -> dict[str, Any]:
    """Take the reservation identity from the journal's durable pending row, never from the caller."""
    pending = execution.recover_pending_attempt(journal_root)
    if pending is None or pending["reservation_id"] != reservation_id:
        raise ValueError("reservation is not the journal's pending attempt")
    if pending["settlement_recovery_required"]:
        raise ValueError("reservation has an uncommitted settlement intent; finish settlement first")
    if pending["prompt_bytes"] != prompt_bytes or pending["prompt_sha256"] != _sha(prompt_bytes):
        raise ValueError("supplied prompt bytes differ from the pending reservation")
    return pending


def _argv(executable: Path, model: str, limits: dict[str, Any]) -> tuple[str, ...]:
    argv = [str(executable), "-p", "--output-format", "stream-json", "--verbose", "--model", model,
            "--system-prompt", ROUTE_SYSTEM_PROMPT, "--tools", "", "--strict-mcp-config",
            "--no-session-persistence", "--permission-prompts", "none"]
    if limits["max_budget_usd"] is not None:
        argv += ["--max-budget-usd", repr(float(limits["max_budget_usd"]))]
    return tuple(argv)


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite JSON constant {name}")


def _finite_float(text: str) -> float:
    value = float(text)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("non-finite JSON number")
    return value


def _parse_stream(stdout: bytes) -> dict[str, Any]:
    """Project the raw NDJSON stream into recorded observations; nothing here decides an outcome."""
    events: list[dict[str, Any]] = []
    unparseable = 0
    for raw_line in stdout.split(b"\n"):
        line = raw_line.strip()
        if not line:
            continue
        try:
            # NaN/Infinity and overflowing literals parse in Python but are not canonical JSON, and a
            # pathologically nested line raises RecursionError; both count as unparseable so the
            # receipt is still written and the attempt classifies failed rather than crashing.
            event = json.loads(line.decode("utf-8"), parse_constant=_reject_constant, parse_float=_finite_float)
        except (UnicodeDecodeError, ValueError, RecursionError):
            unparseable += 1
            continue
        if type(event) is not dict or type(event.get("type")) is not str:
            unparseable += 1
            continue
        events.append(event)
    counts: dict[str, int] = {}
    init = None
    results = []
    assistant_ids: list[str] = []
    assistant_ids_missing = 0
    stop_reasons: list[Any] = []
    models: list[Any] = []
    usage: list[Any] = []
    text_parts: list[str] = []
    tool_use = False
    compaction = False
    api_retries = 0
    session_ids: list[str] = []
    for event in events:
        kind = event["type"]
        subtype = event.get("subtype")
        key = f"{kind}/{subtype}" if type(subtype) is str else kind
        counts[key] = counts.get(key, 0) + 1
        if type(event.get("session_id")) is str and event["session_id"] not in session_ids:
            session_ids.append(event["session_id"])
        if kind == "system" and subtype == "init" and init is None:
            init = {"model": event.get("model"), "tools": event.get("tools"),
                    "claude_code_version": event.get("claude_code_version"),
                    "api_key_source": event.get("apiKeySource"), "permission_mode": event.get("permissionMode")}
        elif kind == "system" and subtype == "compact_boundary":
            compaction = True
        elif kind == "system" and subtype == "api_retry":
            api_retries += 1
        elif kind == "assistant":
            message = event.get("message")
            message = message if type(message) is dict else {}
            identity = message.get("id")
            if type(identity) is not str:
                assistant_ids_missing += 1
            elif identity not in assistant_ids:
                assistant_ids.append(identity)
            stop_reasons.append(message.get("stop_reason"))
            models.append(message.get("model"))
            usage.append(message.get("usage"))
            content = message.get("content")
            for block in content if type(content) is list else []:
                if type(block) is not dict:
                    continue
                if block.get("type") == "tool_use":
                    tool_use = True
                if block.get("type") == "text" and type(block.get("text")) is str:
                    text_parts.append(block["text"])
        elif kind == "result":
            results.append({"subtype": subtype, "is_error": event.get("is_error"), "result": event.get("result"),
                            "num_turns": event.get("num_turns"), "usage": event.get("usage"),
                            "total_cost_usd": event.get("total_cost_usd"), "stop_reason": event.get("stop_reason"),
                            "permission_denials": event.get("permission_denials")})
    return {"event_type_counts": counts, "unparseable_lines": unparseable, "init": init, "results": results,
            "assistant_message_ids": assistant_ids, "assistant_message_ids_missing": assistant_ids_missing,
            "assistant_event_count": counts.get("assistant", 0),
            "stop_reasons": stop_reasons, "models_reported": models, "usage_reported": usage,
            "assistant_text": "".join(text_parts), "tool_use_observed": tool_use,
            "compaction_observed": compaction, "api_retry_count": api_retries, "session_ids": session_ids}


def _encode_output(value: Any) -> tuple[bytes | None, str | None]:
    if type(value) is not str:
        return None, "result_not_text"
    try:
        data = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        return None, "result_not_utf8"
    if not data.strip():
        return None, "empty_result"
    return data, None


def classify_stream(
    stdout: bytes,
    *,
    exit_code: int | None,
    timed_out: bool,
    model_requested: str,
    provider_version: str,
) -> dict[str, Any]:
    """Classify one retained stream fail-closed; pure, so a retained stream can be re-read later.

    Precedence is fixed: ``unknown`` (timeout or no result event) > ``compacted`` > ``truncated`` >
    ``failed`` > ``complete``. ``complete`` requires every documented predicate and an observed
    ``end_turn`` stop reason on every assistant event; any absent field is a ``failed`` reason.
    """
    observed = _parse_stream(stdout)
    reasons: list[str] = []
    results = observed["results"]
    result = results[0] if len(results) == 1 else None
    if result is not None:
        output, output_reason = _encode_output(result["result"])
    else:
        output, output_reason = None, ("no_result_event" if not results else "result_ambiguous")
    if timed_out or not results:
        outcome = "unknown"
        reasons.append("timed_out" if timed_out else "no_result_event")
    else:
        if len(results) != 1:
            reasons.append("stream_schema:multiple_result_events")
        if observed["unparseable_lines"]:
            reasons.append("stream_schema:unparseable_lines")
        if exit_code != 0:
            reasons.append(f"exit_code:{exit_code}")
        if result is not None:
            if result["is_error"] is not False:
                reasons.append("stream_schema:is_error" if result["is_error"] is None else "result_is_error")
            if result["subtype"] != "success":
                reasons.append(f"result_subtype:{result['subtype']}")
            if result["num_turns"] is None:
                reasons.append("stream_schema:num_turns")
            elif result["num_turns"] != 1:
                reasons.append(f"num_turns:{result['num_turns']}")
        if output_reason is not None:
            reasons.append(output_reason)
        init = observed["init"]
        if init is None:
            reasons.append("stream_schema:init_missing")
        else:
            if init["tools"] != []:
                reasons.append("stream_schema:tools" if init["tools"] is None else "tools_enabled")
            if init["model"] is None:
                reasons.append("stream_schema:init_model")
            elif init["model"] != model_requested:
                reasons.append("model_mismatch")
            version = init["claude_code_version"]
            if version is not None and re.fullmatch(re.escape(provider_version) + r"(?: \(Claude Code\))?",
                                                    str(version)) is None:
                reasons.append("version_mismatch")
        if observed["assistant_event_count"] == 0:
            reasons.append("stream_schema:assistant_missing")
        if observed["assistant_message_ids_missing"]:
            reasons.append("stream_schema:message_id")
        if any(model is None for model in observed["models_reported"]):
            reasons.append("stream_schema:assistant_model")
        if any(model is not None and model != model_requested for model in observed["models_reported"]):
            reasons.append("assistant_model_mismatch")
        if len(observed["assistant_message_ids"]) > 1:
            reasons.append("multiple_assistant_messages")
        if any(reason is None for reason in observed["stop_reasons"]):
            reasons.append("stop_reason_unobserved")
        for reason in observed["stop_reasons"]:
            if reason is not None and reason != "end_turn":
                reasons.append(f"stop_reason:{reason}")
        if observed["tool_use_observed"]:
            reasons.append("tool_use_observed")
        if output is not None and observed["assistant_text"] != result["result"]:
            reasons.append("result_text_mismatch")
        if observed["compaction_observed"]:
            outcome = "compacted"
        elif "max_tokens" in observed["stop_reasons"]:
            outcome = "truncated"
        elif reasons:
            outcome = "failed"
        else:
            outcome = "complete"
    return {
        "classifier_version": CLASSIFIER_VERSION,
        "outcome": outcome,
        "reasons": reasons,
        "output_sha256": _sha(output) if output is not None else None,
        "output_byte_length": len(output) if output is not None else None,
        "output_bytes": output,
        "observed": {key: value for key, value in observed.items() if key != "assistant_text"},
        "assistant_text_sha256": _sha(observed["assistant_text"].encode("utf-8", errors="replace")),
        "finish_metadata_observed": bool(observed["stop_reasons"]) and all(r is not None for r in observed["stop_reasons"]),
    }


def _eligible_receipt(binding: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any]:
    contract = binding["role_contract"]
    return {
        "role_contract_sha256": binding["role_contract_sha256"],
        "template_sha256": pending["template_sha256"],
        "rendered_prompt_sha256": pending["prompt_sha256"],
        "input_sha256": pending["input_sha256"],
        "provider": contract["provider"],
        "model": contract["model"],
        "provider_version": contract["provider_version"],
        "source_only": True,
        "truncated": False,
        "compaction_observed": False,
        "candidate_inputs": [],
    }


def _proposal(receipt: dict[str, Any], classification: dict[str, Any],
              binding: dict[str, Any], pending: dict[str, Any]) -> dict[str, Any] | None:
    outcome = classification["outcome"]
    if outcome == "unknown":
        return None
    if outcome == "complete":
        return {"status": "eligible", "artifact_bytes": classification["output_bytes"],
                "receipt": _eligible_receipt(binding, pending)}
    status = {"truncated": "truncated", "compacted": "compacted", "failed": "failed"}[outcome]
    return {"status": status, "artifact_bytes": classification["output_bytes"], "receipt": receipt}


def _read_ledger(delivery_root: Path, reservation_id: str) -> tuple[Path, dict[str, Any], dict[str, bytes]]:
    _token(reservation_id, _RESERVATION, "reservation_id")
    ledger = execution._safe(Path(delivery_root).resolve(), reservation_id)
    if not ledger.is_dir():
        raise ValueError("delivery ledger is missing")
    files = {name: execution._safe(ledger, name).read_bytes() for name in _LEDGER_FILES
             if execution._safe(ledger, name).exists()}
    if set(files) != set(_LEDGER_FILES):
        raise ValueError("delivery ledger is incomplete; the dispatch did not reach a receipt")
    try:
        receipt = json.loads(files["receipt.json"].decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("delivery receipt is not canonical JSON") from exc
    if type(receipt) is not dict or _canonical(receipt) != files["receipt.json"]:
        raise ValueError("delivery receipt is not canonical JSON")
    if receipt.get("schema_version") != SCHEMA_VERSION or receipt.get("kind") != RECEIPT_KIND:
        raise ValueError("unsupported delivery receipt")
    try:
        expected = {
            "request.json": receipt["request_sha256"], "stdin.bin": receipt["stdin"]["sha256"],
            "cli-version.stdout.raw": receipt["cli"]["version_stdout_sha256"],
            "cli-version.stderr.raw": receipt["cli"]["version_stderr_sha256"],
            "stdout.raw": receipt["streams"]["stdout_sha256"], "stderr.raw": receipt["streams"]["stderr_sha256"],
        }
        named = receipt["reservation"]["reservation_id"]
    except (KeyError, TypeError) as exc:
        raise ValueError("delivery receipt is malformed") from exc
    for name, digest in expected.items():
        if _sha(files[name]) != digest:
            raise ValueError(f"retained delivery file changed: {name}")
    if named != reservation_id:
        raise ValueError("delivery receipt names a different reservation")
    return ledger, receipt, files


def deliver_reserved_attempt(
    journal_root: Path,
    delivery_root: Path,
    *,
    reservation_id: str,
    prompt_bytes: bytes,
    cli_path: Path | str,
    environment: Mapping[str, str],
    limits: dict[str, Any],
    native_members: list[dict[str, Any]] | None = None,
    expected_members: dict[str, dict[str, Any]] | None = None,
    passthrough_env: tuple[str, ...] = (),
    engineering_probe: bool = False,
    runner: RouteRunner = run_route_process,
) -> dict[str, Any]:
    """Dispatch the journal's one pending reservation through the CLI print route exactly once.

    Every check that can refuse runs before the route child starts and leaves no ledger entry
    behind; a refusal is a ``ValueError`` (only the pinned executable's ``--version`` may have run).
    The ledger directory under ``delivery_root`` is created exclusively before the child is
    spawned, so a second call for the same reservation into the same delivery root (including after
    an ``unknown`` outcome) is refused rather than redispatched; a different delivery root is not
    covered, which is why one delivery root per journal is the operator rule. Returns the durable
    delivery receipt plus the settlement proposal (``None`` for ``unknown``); nothing is settled here.
    """
    journal_root = Path(journal_root).resolve()
    delivery_root = Path(delivery_root)
    if not delivery_root.is_absolute() or not delivery_root.is_dir() or delivery_root.is_symlink():
        raise ValueError("delivery_root must be an existing absolute directory")
    delivery_root = delivery_root.resolve()
    if delivery_root.is_relative_to(_repository_root()):
        raise ValueError("delivery_root must be outside the repository")
    _token(reservation_id, _RESERVATION, "reservation_id")
    if type(prompt_bytes) is not bytes or not prompt_bytes:
        raise ValueError("prompt_bytes must be non-empty bytes")
    if type(engineering_probe) is not bool:
        raise ValueError("engineering_probe must be a boolean")
    limits = _limits(limits)
    try:
        prompt_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("prompt bytes are not strict UTF-8; this route delivers text only") from exc
    if len(prompt_bytes) > limits["max_stdin_bytes"]:
        raise ValueError("prompt bytes exceed the declared max_stdin_bytes; refusing dispatch")

    binding = _journal_binding(journal_root)
    contract = binding["role_contract"]
    if contract["provider"] != ROUTE_PROVIDER:
        raise ValueError(f"journal role contract provider is not {ROUTE_PROVIDER}")
    provider_version = contract["provider_version"]
    if provider_version is None:
        raise ValueError("this route requires a declared provider_version; exposure-limited contracts are unsupported")
    model = contract["model"]
    if engineering_probe and _SYNTHETIC_ACCESSION.fullmatch(binding["accession_number"]) is None:
        raise ValueError("an engineering probe may only dispatch against a synthetic accession")
    pending = _pending_reservation(journal_root, reservation_id, prompt_bytes)
    custody = native_member_dispositions(prompt_bytes, native_members if native_members is not None else [],
                                         expected_members=expected_members)
    if custody["complete_native_delivery"] is False:
        missing = [m["label"] for m in custody["members"] if m["required"] and m["disposition"] != "delivered_inline"]
        raise ValueError("required native members are not inside the reserved prompt: " + ", ".join(missing))
    env, env_record = _child_env(environment, passthrough_env)
    home = Path(env["HOME"])
    settings = _settings_observation(home)
    _verify_project_isolation(delivery_root, "delivery_root")
    ledger = execution._safe(delivery_root, reservation_id)
    if ledger.exists() or ledger.is_symlink():
        raise ValueError("reservation already dispatched; delivery uncertain, redispatch refused")
    _prove_hard_links(delivery_root)
    executable, cli_sha256 = _cli_identity(cli_path)
    version = _observe_version(executable, provider_version=provider_version, env=env, runner=runner)
    argv = _argv(executable, model, limits)
    cli_display = _display_path(executable, home)
    recorded_argv = [cli_display, *argv[1:]]

    request = {
        "schema_version": SCHEMA_VERSION,
        "kind": REQUEST_KIND,
        "route": ROUTE,
        "route_provider": ROUTE_PROVIDER,
        "engineering_probe": engineering_probe,
        "programme_id": binding["programme_id"],
        "accession_number": binding["accession_number"],
        "journal_binding_sha256": _sha(_canonical(binding)),
        "role_contract_sha256": binding["role_contract_sha256"],
        "reservation": {key: pending[key] for key in ("reservation_id", "sequence", "node_id", "node_kind",
                                                       "context_id", "attempt", "template_sha256",
                                                       "input_sha256", "prompt_sha256")},
        "model_requested": model,
        "provider_version": provider_version,
        "cli": {"path": cli_display, "sha256": cli_sha256, "version_observed": version["observed"]},
        "argv": recorded_argv,
        "route_system_prompt_sha256": _sha(ROUTE_SYSTEM_PROMPT.encode("utf-8")),
        "route_system_prompt_byte_length": len(ROUTE_SYSTEM_PROMPT.encode("utf-8")),
        "environment": env_record,
        "settings_observation": settings,
        "limits": limits,
        "stdin": {"sha256": pending["prompt_sha256"], "byte_length": len(prompt_bytes), "strict_utf8": True},
        "native_delivery": custody,
        "cwd": "cwd",
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }
    request_bytes = _canonical(request)

    try:
        ledger.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise ValueError("reservation already dispatched; delivery uncertain, redispatch refused") from exc
    execution._fsync_directory(delivery_root)
    cwd = ledger / "cwd"
    cwd.mkdir(mode=0o700)
    cwd = _verified_cwd(cwd)
    execution._durable_new(ledger / "request.json", request_bytes)
    execution._durable_new(ledger / "stdin.bin", prompt_bytes)
    execution._durable_new(ledger / "cli-version.stdout.raw", version["stdout"])
    execution._durable_new(ledger / "cli-version.stderr.raw", version["stderr"])
    invocation = RouteInvocation(argv=argv, stdin_bytes=prompt_bytes, env=env, cwd=cwd,
                                 timeout_seconds=limits["timeout_seconds"],
                                 stdout_path=ledger / "stdout.raw", stderr_path=ledger / "stderr.raw")
    process = runner(invocation)
    for path in (invocation.stdout_path, invocation.stderr_path):
        if not path.exists():
            execution._durable_new(path, b"")
    stdout = invocation.stdout_path.read_bytes()
    stderr = invocation.stderr_path.read_bytes()
    classification = classify_stream(stdout, exit_code=process.exit_code, timed_out=process.timed_out,
                                     model_requested=model, provider_version=provider_version)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "route": ROUTE,
        "route_provider": ROUTE_PROVIDER,
        "engineering_probe": engineering_probe,
        "programme_id": binding["programme_id"],
        "accession_number": binding["accession_number"],
        "journal_binding_sha256": request["journal_binding_sha256"],
        "role_contract_sha256": binding["role_contract_sha256"],
        "reservation": request["reservation"],
        "request_sha256": _sha(request_bytes),
        "model_requested": model,
        "provider_version": provider_version,
        "cli": {"path": cli_display, "sha256": cli_sha256, "version_observed": version["observed"],
                "version_exit_code": version["exit_code"], "version_stdout_sha256": _sha(version["stdout"]),
                "version_stderr_sha256": _sha(version["stderr"])},
        "argv": recorded_argv,
        "route_system_prompt_sha256": request["route_system_prompt_sha256"],
        "environment": env_record,
        "settings_observation": settings,
        "limits": limits,
        "stdin": request["stdin"],
        "native_delivery": custody,
        "process": {"exit_code": process.exit_code, "timed_out": process.timed_out,
                    "kill_signal": process.kill_signal, "elapsed_seconds": round(process.elapsed_seconds, 6)},
        "streams": {"stdout_sha256": _sha(stdout), "stdout_byte_length": len(stdout),
                    "stderr_sha256": _sha(stderr), "stderr_byte_length": len(stderr)},
        "stream": classification["observed"],
        "classifier_version": classification["classifier_version"],
        "outcome": classification["outcome"],
        "reasons": classification["reasons"],
        "finish_metadata_observed": classification["finish_metadata_observed"],
        "output": {"sha256": classification["output_sha256"], "byte_length": classification["output_byte_length"],
                   "assistant_text_sha256": classification["assistant_text_sha256"]},
        "settlement_proposal": None,
        "provider_delivery_verified": False,
        "model_attention_verified": False,
        "usage_is_route_reported_estimate": True,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }
    proposal = _proposal(receipt, classification, binding, pending)
    if proposal is not None:
        receipt["settlement_proposal"] = {
            "status": proposal["status"],
            "artifact_sha256": _sha(proposal["artifact_bytes"]) if proposal["artifact_bytes"] is not None else None,
            "receipt_kind": "v1_eligible" if proposal["status"] == "eligible" else "delivery_receipt",
        }
    receipt_bytes = _canonical(receipt)
    execution._durable_exact(ledger / "receipt.json", receipt_bytes)
    return {"receipt": receipt, "receipt_sha256": _sha(receipt_bytes), "ledger_path": str(ledger),
            "outcome": classification["outcome"], "settlement_proposal": proposal,
            "redispatch_permitted": False}


def _bound_reservation(journal_root: Path, receipt: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    """Bind retained input to the durable attempt before either settlement or validation."""
    expected = receipt["reservation"]
    with execution._connect(journal_root, read_only=True) as db:
        row = db.execute("SELECT * FROM attempts WHERE reservation_id=?", (expected["reservation_id"],)).fetchone()
    if row is None:
        raise ValueError("journal has no attempt for this reservation")
    fields = ("reservation_id", "sequence", "node_id", "node_kind", "context_id", "attempt",
              "template_sha256", "input_sha256", "prompt_sha256")
    if (any(row[key] != expected.get(key) for key in fields)
            or row["prompt_sha256"] != receipt["stdin"]["sha256"]
            or _sha(files["stdin.bin"]) != row["prompt_sha256"]
            or len(files["stdin.bin"]) != receipt["stdin"]["byte_length"]):
        raise ValueError("delivery ledger does not bind the journal reservation")
    return dict(row)


def _bound_ledger(journal_root: Path, delivery_root: Path, reservation_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes], dict[str, Any], dict[str, Any]]:
    """Read the ledger, bind it to the journal contract, and re-derive its classification from bytes.

    The route identity the classification depends on (provider, model, version) is taken from the
    frozen journal contract, never from the ledger's own receipt, so a rewritten ledger cannot
    re-label a model-mismatch stream; the receipt must then agree with that re-derivation.
    """
    _, receipt, files = _read_ledger(delivery_root, reservation_id)
    binding = _journal_binding(journal_root)
    contract = binding["role_contract"]
    if _sha(_canonical(binding)) != receipt["journal_binding_sha256"]:
        raise ValueError("delivery ledger is bound to a different journal")
    if receipt["role_contract_sha256"] != binding["role_contract_sha256"]:
        raise ValueError("delivery receipt names a different role contract")
    if (receipt["route_provider"] != contract["provider"] or receipt["model_requested"] != contract["model"]
            or receipt["provider_version"] != contract["provider_version"] or receipt["route"] != ROUTE):
        raise ValueError("delivery receipt route identity differs from the journal contract")
    row = _bound_reservation(journal_root, receipt, files)
    classification = classify_stream(files["stdout.raw"], exit_code=receipt["process"]["exit_code"],
                                     timed_out=receipt["process"]["timed_out"],
                                     model_requested=contract["model"], provider_version=contract["provider_version"])
    if (classification["outcome"] != receipt["outcome"] or classification["reasons"] != receipt["reasons"]
            or classification["output_sha256"] != receipt["output"]["sha256"]
            or classification["classifier_version"] != receipt["classifier_version"]):
        raise ValueError("retained delivery receipt disagrees with its retained stream")
    return binding, receipt, files, classification, row


def settle_delivery(journal_root: Path, delivery_root: Path, *, reservation_id: str) -> dict[str, Any]:
    """Apply the ledger's settlement proposal to the journal from retained bytes, never from memory.

    ``unknown`` outcomes are refused: the operator inspects the ledger and settles or retires the
    reservation through the journal directly. Identical retries are absorbed by ``settle_attempt``.
    """
    journal_root = Path(journal_root).resolve()
    binding, receipt, _files, classification, pending = _bound_ledger(journal_root, delivery_root, reservation_id)
    if classification["outcome"] == "unknown":
        raise ValueError("delivery outcome is unknown; inspect the ledger and settle or retire manually")
    proposal = _proposal(receipt, classification, binding, pending)
    if proposal is None:  # unreachable: unknown was refused above; keep the refusal explicit
        raise ValueError("delivery outcome has no settlement proposal")
    return execution.settle_attempt(journal_root, reservation_id=reservation_id, status=proposal["status"],
                                    artifact_bytes=proposal["artifact_bytes"], receipt=proposal["receipt"])


def validate_delivery_binding(
    journal_root: Path,
    delivery_root: Path,
    *,
    reservation_id: str,
    native_members: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Cross-check the delivery ledger, the retained stream and the journal row in both directions.

    Journal ``eligible`` is accepted only for a ``complete`` delivery whose stdin equals the row's
    prompt and whose output equals the row's artifact; ``truncated``/``compacted``/``failed`` must
    carry the delivered output and the retained delivery receipt; an operator ``retired`` row is
    admitted after ``failed`` or ``unknown`` (and ``failed`` after ``unknown``) without those
    equalities and is reported as ``operator_settled_after_outcome``. ``unknown`` never admits
    ``eligible``. Supplying ``native_members`` re-derives their dispositions from ``stdin.bin``.
    """
    journal_root = Path(journal_root).resolve()
    binding, receipt, files, classification, row = _bound_ledger(journal_root, delivery_root, reservation_id)
    if receipt["engineering_probe"] and _SYNTHETIC_ACCESSION.fullmatch(receipt["accession_number"]) is None:
        raise ValueError("engineering probe receipt is bound to a non-synthetic accession")
    if receipt["native_delivery"]["complete_native_delivery"] is False:
        raise ValueError("delivery receipt declares an incomplete native delivery")
    if native_members is not None:
        rederived = native_member_dispositions(files["stdin.bin"], native_members)
        if rederived != receipt["native_delivery"]:
            raise ValueError("native member dispositions differ from the retained stdin")
    expected_row = receipt["reservation"]
    status = row["status"]
    outcome = receipt["outcome"]
    operator_settled = False
    if status == execution.RESERVED_STATUS:
        if outcome != "unknown":
            raise ValueError("classified delivery has not been settled in the journal")
    else:
        if status not in _STATUS_BY_OUTCOME[outcome]:
            raise ValueError(f"journal status {status} is not admissible for delivery outcome {outcome}")
        operator_settled = status == "retired" or outcome == "unknown"
        if status == "eligible":
            if row["artifact_sha256"] != classification["output_sha256"]:
                raise ValueError("eligible artifact differs from the delivered output")
            receipt_bytes = execution._safe(journal_root, row["receipt_path"]).read_bytes()
            if receipt_bytes != _canonical(_eligible_receipt(binding, expected_row)):
                raise ValueError("eligible journal receipt was not derived from this delivery")
        elif not operator_settled:
            if row["artifact_sha256"] != classification["output_sha256"]:
                raise ValueError("journal artifact differs from the delivered output")
            receipt_bytes = execution._safe(journal_root, row["receipt_path"]).read_bytes()
            if receipt_bytes != files["receipt.json"]:
                raise ValueError("journal receipt is not the retained delivery receipt")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": VALIDATION_KIND,
        "reservation_id": reservation_id,
        "outcome": outcome,
        "journal_status": status,
        "delivery_receipt_sha256": _sha(files["receipt.json"]),
        "stdin_matches_reservation": True,
        "operator_settled_after_outcome": outcome if operator_settled else None,
        "provider_delivery_verified": False,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }
