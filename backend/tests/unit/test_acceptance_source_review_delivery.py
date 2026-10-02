"""The delivery adapter binds exact stdin/output to the journal and fails closed on every gap."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

import evals.acceptance_ai_judge_runner as judge_runner
import evals.acceptance_source_review_delivery as delivery
from evals.acceptance_source_review_delivery import (
    LIMITATIONS,
    ROUTE_SYSTEM_PROMPT,
    RouteInvocation,
    RouteProcessResult,
    classify_stream,
    deliver_reserved_attempt,
    native_member_dispositions,
    settle_delivery,
    validate_delivery_binding,
)
from evals.acceptance_source_review_execution import (
    initialize_journal,
    recover_pending_attempt,
    recover_terminal_attempt,
    reserve_attempt,
    seal_history,
    settle_attempt,
)
from evals.acceptance_source_units import build_unit_manifest
from evals.judge import _BILLING_ENV as JUDGE_BILLING_ENV


ACCESSION = "0000000000-26-000001"
MODEL = "claude-fable-5-1"
VERSION = "2.1.285"
PRIMARY = b"<p>Opaque tokens: " + b" ".join(
    hashlib.sha256(bytes([index])).hexdigest().encode("ascii") for index in range(4)
) + b"</p>"
PROJECTION = b"{\"projection\": \"" + hashlib.sha256(b"projection").hexdigest().encode("ascii") * 2 + b"\"}"
PACKETS = [{"role": "primary", "sha256": hashlib.sha256(PRIMARY).hexdigest(), "byte_length": len(PRIMARY)}]
MANIFEST = build_unit_manifest(
    accession_number=ACCESSION,
    packets=PACKETS,
    packet_bytes={"primary": PRIMARY},
    units=[{"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
            "coverage_spans": [{"start": 0, "end": len(PRIMARY)}], "context_spans": []}],
)
UNIT_ID = MANIFEST["units"][0]["unit_id"]
TEMPLATES = {"leaf": b"Echo the exact source span.", "role_synthesis": b"Synthesize exact child reviews."}
LIMITS = {"max_stdin_bytes": 65536, "timeout_seconds": 30, "max_budget_usd": None}
STREAM_SESSION = "sess-0001"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _contract(**overrides: Any) -> dict[str, Any]:
    contract = {
        "schema_version": 1,
        "kind": "e7_offline_source_role_contract",
        "role": "role-b",
        "node_kinds": {kind: {"template_sha256": _sha(template)} for kind, template in TEMPLATES.items()},
        "provider": delivery.ROUTE_PROVIDER,
        "model": MODEL,
        "provider_version": VERSION,
        "exposure_limit": None,
    }
    contract.update(overrides)
    return contract


@pytest.fixture(autouse=True)
def _no_managed_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # User settings are read from the injected temporary HOME; the two machine-managed paths are
    # real filesystem locations, so they are neutralised to keep the suite hermetic everywhere.
    monkeypatch.setattr(delivery, "_MANAGED_SETTINGS", ())


def _journal(root: Path, *, accession: str = ACCESSION, programme_id: str = "engineering-probe-synthetic",
             **contract_overrides: Any) -> dict[str, Any]:
    packets = [{"role": "primary", "sha256": _sha(PRIMARY), "byte_length": len(PRIMARY)}]
    manifest = build_unit_manifest(
        accession_number=accession, packets=packets, packet_bytes={"primary": PRIMARY},
        units=[{"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
                "coverage_spans": [{"start": 0, "end": len(PRIMARY)}], "context_spans": []}],
    )
    return initialize_journal(
        root, programme_id=programme_id, accession_number=accession,
        role_contract=_contract(**contract_overrides), unit_manifest_sha256=_sha(_canonical(manifest)),
        unit_manifest=manifest, expected_packets=packets, packet_bytes={"primary": PRIMARY},
    )


def _process_gone(pid: int) -> bool:
    """True when the pid is reaped, or is a zombie awaiting a reaper this container may lack."""
    try:
        status = Path(f"/proc/{pid}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return True
    return status.rpartition(")")[2].split()[0] in ("Z", "X")


def _unit_id(accession: str) -> str:
    """Unit identities hash the accession, so a journal for another accession needs its own id."""
    packets = [{"role": "primary", "sha256": _sha(PRIMARY), "byte_length": len(PRIMARY)}]
    return build_unit_manifest(
        accession_number=accession, packets=packets, packet_bytes={"primary": PRIMARY},
        units=[{"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
                "coverage_spans": [{"start": 0, "end": len(PRIMARY)}], "context_spans": []}],
    )["units"][0]["unit_id"]


def _reserve(root: Path, node_id: str = "l1", context_id: str = "ctx-l1", *, accession: str = ACCESSION) -> dict[str, Any]:
    return reserve_attempt(root, node_id=node_id, node_kind="leaf", context_id=context_id,
                           render_inputs={"template": TEMPLATES["leaf"], "unit_id": _unit_id(accession)})


def _stream(
    *, result_text: str = "echo", stop_reason: Any = "end_turn", tools: Any = (), model: Any = MODEL,
    version: Any = f"{VERSION} (Claude Code)", subtype: str = "success", is_error: Any = False,
    num_turns: Any = 1, compact: bool = False, tool_use: bool = False, second_message: bool = False,
    assistant_text: str | None = None, omit_result: bool = False, omit_init: bool = False,
    omit_assistant: bool = False, garbage: bool = False, api_retry: bool = False,
    result_value: Any = "text", duplicate_result: bool = False, message_id: Any = "msg_1",
    nan_usage: bool = False,
) -> bytes:
    init = {"type": "system", "subtype": "init", "model": model, "tools": None if tools is None else list(tools),
            "session_id": STREAM_SESSION, "cwd": "/elsewhere", "apiKeySource": "none"}
    if version is not None:
        init["claude_code_version"] = version
    events: list[dict[str, Any]] = [] if omit_init else [init]
    if api_retry:
        events.append({"type": "system", "subtype": "api_retry", "attempt": 1, "session_id": STREAM_SESSION})
    if compact:
        events.append({"type": "system", "subtype": "compact_boundary", "session_id": STREAM_SESSION,
                       "compact_metadata": {"trigger": "auto", "pre_tokens": 12}})
    content: list[dict[str, Any]] = [{"type": "text", "text": result_text if assistant_text is None else assistant_text}]
    if tool_use:
        content.append({"type": "tool_use", "id": "tu_1", "name": "Read", "input": {"file_path": "/x"}})
    message = {"model": model, "usage": {"input_tokens": 12, "output_tokens": 3}, "content": content}
    if message_id is not None:
        message["id"] = message_id
    if stop_reason != "absent":
        message["stop_reason"] = stop_reason
    if not omit_assistant:
        events.append({"type": "assistant", "message": message, "session_id": STREAM_SESSION})
    if second_message:
        events.append({"type": "assistant", "session_id": STREAM_SESSION,
                       "message": {"id": "msg_2", "model": model, "stop_reason": "end_turn",
                                   "usage": {"input_tokens": 1, "output_tokens": 1},
                                   "content": [{"type": "text", "text": ""}]}})
    if not omit_result:
        result = {"type": "result", "subtype": subtype, "is_error": is_error,
                  "result": result_text if result_value == "text" else result_value,
                  "num_turns": num_turns, "usage": {"input_tokens": 12, "output_tokens": 3},
                  "total_cost_usd": 0.0, "session_id": STREAM_SESSION, "permission_denials": []}
        events.append(result)
        if duplicate_result:
            events.append(dict(result))
    lines = [json.dumps(event) for event in events]
    if garbage:
        lines.insert(1, "this line is not JSON")
    if nan_usage:  # a NaN literal parses in Python but is not canonical JSON; the line must count as unparseable
        lines = [line.replace('"output_tokens": 3', '"output_tokens": NaN') if line.startswith('{"type": "assistant"') else line
                 for line in lines]
    return ("\n".join(lines) + "\n").encode("utf-8")


class FakeRoute:
    """Injected route runner: answers ``--version`` and writes one canned stream; never spawns."""

    def __init__(self, stdout: bytes = b"", *, exit_code: int | None = 0, timed_out: bool = False,
                 stderr: bytes = b"", version: bytes = f"{VERSION} (Claude Code)\n".encode("ascii")) -> None:
        self.stdout, self.exit_code, self.timed_out, self.stderr, self.version = stdout, exit_code, timed_out, stderr, version
        self.calls: list[RouteInvocation] = []

    def __call__(self, invocation: RouteInvocation) -> RouteProcessResult:
        self.calls.append(invocation)
        if invocation.argv[1:] == ("--version",):
            invocation.stdout_path.write_bytes(self.version)
            invocation.stderr_path.write_bytes(b"")
            return RouteProcessResult(exit_code=0, timed_out=False, elapsed_seconds=0.01)
        invocation.stdout_path.write_bytes(self.stdout)
        invocation.stderr_path.write_bytes(self.stderr)
        return RouteProcessResult(exit_code=self.exit_code, timed_out=self.timed_out, elapsed_seconds=0.5,
                                  kill_signal="SIGTERM" if self.timed_out else None)

    @property
    def dispatches(self) -> list[RouteInvocation]:
        return [call for call in self.calls if call.argv[1:] != ("--version",)]


def _cli(tmp_path: Path) -> Path:
    executable = tmp_path / "bin" / "claude"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def _environment(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TERM": "dumb",
        "ANTHROPIC_API_KEY": "sk-ant-api03-secret-value", "ANTHROPIC_AUTH_TOKEN": "oauth-secret-token",
        "ANTHROPIC_BASE_URL": "https://gateway.example/anthropic", "ANTHROPIC_MODEL": "other-model-override",
        "CLAUDECODE": "nested-launch-marker", "CLAUDE_CODE_USE_BEDROCK": "bedrock-routing-on",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "output-cap-override",
        "HTTPS_PROXY": "http://proxy.example:3128", "NODE_OPTIONS": "--require /evil.js",
    }


def _setup(tmp_path: Path, **journal_overrides: Any) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    journal_root = tmp_path / "journal"
    _journal(journal_root, **journal_overrides)
    delivery_root = tmp_path / "ledger"
    delivery_root.mkdir()
    reservation = _reserve(journal_root)
    common = {"reservation_id": reservation["reservation_id"], "prompt_bytes": reservation["prompt_bytes"],
              "cli_path": _cli(tmp_path), "environment": _environment(tmp_path), "limits": dict(LIMITS),
              "native_members": [{"label": "primary", "bytes": PRIMARY, "required": True},
                                 {"label": "projection", "bytes": PROJECTION, "required": False}],
              "engineering_probe": True}
    return journal_root, delivery_root, reservation, common


def test_dispatch_binds_exact_stdin_and_output_and_settles_through_the_journal(tmp_path: Path) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    route = FakeRoute(_stream(result_text="echo: 0f1e"))
    outcome = deliver_reserved_attempt(journal_root, delivery_root, runner=route, **common)

    assert [call.argv[1:] for call in route.calls][0] == ("--version",)
    assert len(route.dispatches) == 1
    dispatched = route.dispatches[0]
    assert dispatched.stdin_bytes == reservation["prompt_bytes"]
    ledger = Path(outcome["ledger_path"])
    assert (ledger / "stdin.bin").read_bytes() == reservation["prompt_bytes"]
    receipt = outcome["receipt"]
    assert receipt["stdin"]["sha256"] == reservation["prompt_sha256"] == receipt["reservation"]["prompt_sha256"]
    assert receipt["outcome"] == "complete" and receipt["reasons"] == []
    assert receipt["output"]["sha256"] == _sha(b"echo: 0f1e")
    assert receipt["native_delivery"]["complete_native_delivery"] is True
    assert [m["disposition"] for m in receipt["native_delivery"]["members"]] == ["delivered_inline", "retained_not_delivered"]
    assert receipt["provider_delivery_verified"] is False and receipt["admission_approved"] is False
    assert receipt["limitations"] == list(LIMITATIONS) and receipt["cli"]["version_observed"] == f"{VERSION} (Claude Code)"
    assert receipt["stream"]["session_ids"] == [STREAM_SESSION]
    assert outcome["settlement_proposal"]["status"] == "eligible"
    assert outcome["redispatch_permitted"] is False
    # Nothing is settled by delivery itself; the reservation is still the journal's pending row.
    assert recover_pending_attempt(journal_root)["reservation_id"] == reservation["reservation_id"]

    settled = settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    assert settled["status"] == "eligible" and settled["artifact_sha256"] == _sha(b"echo: 0f1e")
    terminal = recover_terminal_attempt(journal_root, reservation_id=reservation["reservation_id"])
    assert terminal["artifact_bytes"] == b"echo: 0f1e"
    assert terminal["receipt"] == {
        "role_contract_sha256": _sha(_canonical(_contract())), "template_sha256": _sha(TEMPLATES["leaf"]),
        "rendered_prompt_sha256": reservation["prompt_sha256"], "input_sha256": UNIT_ID,
        "provider": delivery.ROUTE_PROVIDER, "model": MODEL, "provider_version": VERSION, "source_only": True,
        "truncated": False, "compaction_observed": False, "candidate_inputs": [],
    }
    # Retrying the settlement from the same retained bytes is absorbed, never re-dispatched or rewritten.
    assert settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"]) == settled
    validation = validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation["reservation_id"],
                                           native_members=common["native_members"])
    assert validation["journal_status"] == "eligible" and validation["outcome"] == "complete"
    assert validation["operator_settled_after_outcome"] is None
    # The adapter-settled leaf is an ordinary V1 eligible child for downstream parent work and sealing.
    parent = reserve_attempt(journal_root, node_id="s", node_kind="role_synthesis", context_id="ctx-s",
                             render_inputs={"template": TEMPLATES["role_synthesis"],
                                            "children": [{"node_id": "l1", "artifact_sha256": _sha(b"echo: 0f1e")}],
                                            "child_artifacts": {_sha(b"echo: 0f1e"): b"echo: 0f1e"}})
    settle_attempt(journal_root, reservation_id=parent["reservation_id"], status="retired", artifact_bytes=None,
                   receipt={"outcome": "retired"})
    assert seal_history(journal_root)["history_sha256"]


@pytest.mark.parametrize(
    ("stream", "expected_outcome", "expected_status", "reason"),
    [
        (dict(stop_reason="max_tokens"), "truncated", "truncated", "stop_reason:max_tokens"),
        (dict(compact=True), "compacted", "compacted", None),
        (dict(compact=True, stop_reason="max_tokens"), "compacted", "compacted", "stop_reason:max_tokens"),
        (dict(is_error=True, subtype="error_during_execution"), "failed", "failed",
         ("result_is_error", "result_subtype:error_during_execution")),
        (dict(is_error=None), "failed", "failed", "stream_schema:is_error"),
        (dict(duplicate_result=True), "failed", "failed", ("stream_schema:multiple_result_events", "result_ambiguous")),
        (dict(result_value=5), "failed", "failed", "result_not_text"),
        (dict(tools=None), "failed", "failed", "stream_schema:tools"),
        (dict(model=None), "failed", "failed", "stream_schema:init_model"),
        (dict(message_id=None), "failed", "failed", "stream_schema:message_id"),
        (dict(message_id=7, second_message=True), "failed", "failed", "stream_schema:message_id"),
        (dict(nan_usage=True), "failed", "failed", ("stream_schema:unparseable_lines", "stream_schema:assistant_missing")),
        (dict(stop_reason="absent"), "failed", "failed", "stop_reason_unobserved"),
        (dict(stop_reason=None), "failed", "failed", "stop_reason_unobserved"),
        (dict(stop_reason="refusal"), "failed", "failed", "stop_reason:refusal"),
        (dict(tools=("Bash", "Read")), "failed", "failed", "tools_enabled"),
        (dict(tool_use=True), "failed", "failed", "tool_use_observed"),
        (dict(model="claude-other"), "failed", "failed", "model_mismatch"),
        (dict(version="2.1.290 (Claude Code)"), "failed", "failed", "version_mismatch"),
        (dict(num_turns=2), "failed", "failed", "num_turns:2"),
        (dict(num_turns=None), "failed", "failed", "stream_schema:num_turns"),
        (dict(second_message=True), "failed", "failed", "multiple_assistant_messages"),
        (dict(assistant_text="different"), "failed", "failed", "result_text_mismatch"),
        (dict(result_text=""), "failed", "failed", "empty_result"),
        (dict(result_text=" \n\t"), "failed", "failed", "empty_result"),
        (dict(result_text="\ud800"), "failed", "failed", "result_not_utf8"),
        (dict(omit_init=True), "failed", "failed", "stream_schema:init_missing"),
        (dict(omit_assistant=True), "failed", "failed", "stream_schema:assistant_missing"),
        (dict(garbage=True), "failed", "failed", "stream_schema:unparseable_lines"),
        (dict(api_retry=True), "complete", "eligible", None),
    ],
)
def test_outcomes_classify_fail_closed_and_settle_only_terminal_statuses(
    tmp_path: Path, stream: dict[str, Any], expected_outcome: str, expected_status: str,
    reason: str | tuple[str, ...] | None
) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    route = FakeRoute(_stream(**stream))
    outcome = deliver_reserved_attempt(journal_root, delivery_root, runner=route, **common)
    assert outcome["outcome"] == expected_outcome, outcome["receipt"]["reasons"]
    for expected_reason in ([reason] if isinstance(reason, str) else reason or ()):
        assert expected_reason in outcome["receipt"]["reasons"], outcome["receipt"]["reasons"]
    assert len(route.dispatches) == 1
    assert (Path(outcome["ledger_path"]) / "receipt.json").is_file()
    settled = settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    assert settled["status"] == expected_status
    terminal = recover_terminal_attempt(journal_root, reservation_id=reservation["reservation_id"])
    if expected_status == "eligible":
        assert terminal["receipt"]["source_only"] is True
    else:
        # Non-eligible attempts retain the complete delivery receipt as their journal receipt.
        assert terminal["receipt"] == outcome["receipt"]
        assert terminal["receipt"]["outcome"] == expected_outcome
    validation = validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    assert validation["journal_status"] == expected_status


@pytest.mark.parametrize("exit_code", [1, -15])
def test_nonzero_exit_is_failed_with_stderr_retained(tmp_path: Path, exit_code: int) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    route = FakeRoute(_stream(), exit_code=exit_code, stderr=b"Not logged in. Please run /login\n")
    outcome = deliver_reserved_attempt(journal_root, delivery_root, runner=route, **common)
    assert outcome["outcome"] == "failed" and f"exit_code:{exit_code}" in outcome["receipt"]["reasons"]
    ledger = Path(outcome["ledger_path"])
    assert (ledger / "stderr.raw").read_bytes() == b"Not logged in. Please run /login\n"
    assert outcome["receipt"]["streams"]["stderr_sha256"] == _sha(b"Not logged in. Please run /login\n")
    assert settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])["status"] == "failed"


@pytest.mark.parametrize("scenario", ["timeout", "timeout_with_result", "no_result_event", "empty_stdout"])
def test_unknown_delivery_stays_pending_retains_partial_output_and_blocks_redispatch(
    tmp_path: Path, scenario: str
) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    timed_out = scenario.startswith("timeout")
    partial = {"timeout": _stream(omit_result=True), "timeout_with_result": _stream(result_text="echo"),
               "no_result_event": _stream(omit_result=True), "empty_stdout": b""}[scenario]
    route = FakeRoute(partial, exit_code=-9 if timed_out else 0, timed_out=timed_out)
    outcome = deliver_reserved_attempt(journal_root, delivery_root, runner=route, **common)
    assert outcome["outcome"] == "unknown" and outcome["settlement_proposal"] is None
    assert outcome["redispatch_permitted"] is False
    receipt = outcome["receipt"]
    assert receipt["reasons"] == ["timed_out" if timed_out else "no_result_event"]
    assert receipt["process"]["timed_out"] is timed_out
    ledger = Path(outcome["ledger_path"])
    assert (ledger / "stdout.raw").read_bytes() == partial
    assert receipt["streams"]["stdout_sha256"] == _sha(partial)
    assert (ledger / "receipt.json").read_bytes() == _canonical(receipt)

    with pytest.raises(ValueError, match="outcome is unknown"):
        settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    pending = recover_pending_attempt(journal_root)
    assert pending["reservation_id"] == reservation["reservation_id"]
    assert pending["delivery_uncertain"] is True and pending["redispatch_permitted"] is False
    validation = validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    assert validation["journal_status"] == "reserved" and validation["outcome"] == "unknown"
    assert validation["operator_settled_after_outcome"] is None

    # The ledger directory is the dispatch lock: the same reservation into the same root is refused
    # before the pinned executable is even asked for its version.
    calls_before = len(route.calls)
    with pytest.raises(ValueError, match="already dispatched"):
        deliver_reserved_attempt(journal_root, delivery_root, runner=route, **common)
    assert len(route.calls) == calls_before and len(route.dispatches) == 1
    # The lock is per delivery root; the journal keeps no dispatch memory, so a second root would
    # dispatch again. That scope is a stated limitation and an operator rule, pinned here.
    other_root = tmp_path / "ledger-2"
    other_root.mkdir()
    second = FakeRoute(partial, exit_code=-9 if timed_out else 0, timed_out=timed_out)
    deliver_reserved_attempt(journal_root, other_root, runner=second, **common)
    assert len(second.dispatches) == 1 and "one delivery root per journal" in LIMITATIONS[-1]
    # The journal's own rules keep holding: no other reservation and no seal while it is pending.
    with pytest.raises(ValueError, match="pending attempt blocks another reservation"):
        _reserve(journal_root, "l2", "ctx-l2")
    # An unknown delivery never admits eligible, even when the timed-out stream carried a result:
    # the matrix gate refuses an operator's hand-typed V1 receipt.
    if scenario == "timeout_with_result":
        assert receipt["output"]["sha256"] == _sha(b"echo")
        hand_settled = tmp_path / "hand-settled-eligible"
        shutil.copytree(journal_root, hand_settled)
        settle_attempt(hand_settled, reservation_id=reservation["reservation_id"], status="eligible",
                       artifact_bytes=b"echo", receipt=delivery._eligible_receipt(
                           delivery._journal_binding(hand_settled), receipt["reservation"]))
        with pytest.raises(ValueError, match="journal status eligible is not admissible for delivery outcome unknown"):
            validate_delivery_binding(hand_settled, delivery_root, reservation_id=reservation["reservation_id"])
    # Only the operator may retire it, after inspection; the validator then records that decision.
    settle_attempt(journal_root, reservation_id=reservation["reservation_id"], status="retired",
                   artifact_bytes=None, receipt={"outcome": "delivery-uncertain-retired",
                                                 "delivery_receipt_sha256": outcome["receipt_sha256"]})
    validation = validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    assert validation["journal_status"] == "retired" and validation["operator_settled_after_outcome"] == "unknown"
    retry = _reserve(journal_root, "l1", "ctx-l1-fresh")
    assert retry["attempt"] == 2


def test_route_environment_and_argv_are_frozen_and_leak_no_values(tmp_path: Path) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    # A user-local install puts the executable under HOME; receipts must not carry that path.
    home = Path(common["environment"]["HOME"])
    user_cli = home / ".local" / "bin" / "claude"
    user_cli.parent.mkdir(parents=True)
    shutil.copy(common["cli_path"], user_cli)
    common["cli_path"] = user_cli
    route = FakeRoute(_stream())
    outcome = deliver_reserved_attempt(journal_root, delivery_root, runner=route, passthrough_env=("HTTPS_PROXY",), **common)
    dispatched = route.dispatches[0]
    environment = common["environment"]
    assert dict(dispatched.env) == {key: environment[key] for key in ("HOME", "PATH", "LANG", "TERM", "HTTPS_PROXY")}
    assert not (JUDGE_BILLING_ENV & dispatched.env.keys())
    assert delivery.BILLING_ENV == JUDGE_BILLING_ENV == judge_runner.BILLING_ENV
    assert delivery.SAFE_ENV == judge_runner.SAFE_ENV
    assert dispatched.argv == (
        str(user_cli.resolve()), "-p", "--output-format", "stream-json", "--verbose", "--model", MODEL,
        "--system-prompt", ROUTE_SYSTEM_PROMPT, "--tools", "", "--strict-mcp-config", "--no-session-persistence",
        "--permission-prompts", "none",
    )
    assert dispatched.cwd == Path(outcome["ledger_path"]) / "cwd" and dispatched.timeout_seconds == 30
    receipt = outcome["receipt"]
    assert receipt["cli"]["path"] == "~/.local/bin/claude" and receipt["argv"][0] == "~/.local/bin/claude"
    assert receipt["argv"][1:] == list(dispatched.argv[1:])
    assert receipt["environment"] == {"env_passed_names": ["HOME", "HTTPS_PROXY", "LANG", "PATH", "TERM"],
                                      "env_dropped_count": len(environment) - 5, "passthrough_declared": ["HTTPS_PROXY"]}
    # The fixed route overhead is pinned by hash: changing ROUTE_SYSTEM_PROMPT is a deliberate contract edit.
    assert receipt["route_system_prompt_sha256"] == _sha(ROUTE_SYSTEM_PROMPT.encode("utf-8")) \
        == "5413f66546c673176d27c823fce3556577a9488717c717c6bfcdeed029772e50"
    ledger = Path(outcome["ledger_path"])
    retained = (ledger / "request.json").read_bytes() + (ledger / "receipt.json").read_bytes()
    for name, value in environment.items():
        if name != "PATH":  # values are never recorded, whether dropped or passed through
            assert value.encode("utf-8") not in retained, name
    assert str(tmp_path / "home").encode("utf-8") not in retained
    assert receipt["settings_observation"] == {
        "~/.claude/settings.json": None, "~/.claude/settings.local.json": None, "~/.claude/managed-settings.json": None,
        "~/.claude/CLAUDE.md": None, "~/.claude/rules": None, "~/.claude/plugins/installed_plugins.json": None,
    }


def test_pre_dispatch_refusals_leave_no_ledger_and_never_dispatch(tmp_path: Path) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    route = FakeRoute(_stream())

    def refuse(match: str, **overrides: Any) -> None:
        arguments = {**common, **overrides}
        with pytest.raises(ValueError, match=match):
            deliver_reserved_attempt(journal_root, delivery_root, runner=route, **arguments)
        assert not any(delivery_root.iterdir()), match
        assert route.dispatches == []

    refuse("exceed the declared max_stdin_bytes", limits={**LIMITS, "max_stdin_bytes": 16})
    refuse("documented CLI stdin cap", limits={**LIMITS, "max_stdin_bytes": 10 * 1024 * 1024 + 1})
    refuse("differ from the pending reservation", prompt_bytes=reservation["prompt_bytes"] + b"\n")
    refuse("not the journal's pending attempt", reservation_id="0" * 32)
    refuse("not strict UTF-8", prompt_bytes=b"\xff\xfe")
    refuse("required native members are not inside the reserved prompt",
           native_members=[{"label": "projection", "bytes": PROJECTION, "required": True}])
    refuse("differs from its expected identity",
           expected_members={"primary": {"sha256": "0" * 64, "byte_length": len(PRIMARY)},
                             "projection": {"sha256": _sha(PROJECTION), "byte_length": len(PROJECTION)}})
    refuse("outside the allowed proxy/CA set", passthrough_env=("ANTHROPIC_BASE_URL",))
    refuse("route HOME missing", environment={k: v for k, v in common["environment"].items() if k != "HOME"})
    home = Path(common["environment"]["HOME"])
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"command": "x"}]}}))
    refuse("model, routing, hook or environment override")
    (home / ".claude" / "settings.json").write_text(json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://x"}}))
    refuse("model, routing, hook or environment override")
    (home / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {"some-plugin@market": True}}))
    refuse("model, routing, hook or environment override")
    (home / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": []}}))
    # User memory, rules and installed plugins are model-visible context the route cannot exclude.
    (home / ".claude" / "CLAUDE.md").write_text("founder memory: always answer in haiku")
    refuse("user-level Claude context")
    (home / ".claude" / "CLAUDE.md").unlink()
    (home / ".claude" / "rules").mkdir()
    refuse("user-level Claude context")
    (home / ".claude" / "rules").rmdir()
    # A drifted CLI build is refused before dispatch and before any ledger entry.
    drifted = FakeRoute(_stream(), version=b"2.1.290 (Claude Code)\n")
    with pytest.raises(ValueError, match="did not identify 2.1.285"):
        deliver_reserved_attempt(journal_root, delivery_root, runner=drifted, **common)
    assert not any(delivery_root.iterdir()) and drifted.dispatches == []
    assert [call.argv[1:] for call in drifted.calls] == [("--version",)]
    # Inherited project context around the ledger root is refused before the lock directory exists.
    (tmp_path / "CLAUDE.md").write_text("project instructions")
    refuse("inherits Claude project context")
    (tmp_path / "CLAUDE.md").unlink()
    inside_repo = Path(__file__).resolve().parents[2] / "tmp-delivery-root-must-not-exist"
    assert not inside_repo.exists()
    with pytest.raises(ValueError, match="delivery_root must be an existing absolute directory"):
        deliver_reserved_attempt(journal_root, inside_repo, runner=route, **common)

    # A journal whose contract names another provider, or an exposure-limited build, cannot use this route.
    other_root = tmp_path / "other-provider"
    _journal(other_root, provider="example-provider")
    other = _reserve(other_root)
    with pytest.raises(ValueError, match="provider is not anthropic-claude-code-cli"):
        deliver_reserved_attempt(other_root, delivery_root, runner=route,
                                 **{**common, "reservation_id": other["reservation_id"], "prompt_bytes": other["prompt_bytes"]})
    limited_root = tmp_path / "exposure-limited"
    _journal(limited_root, provider_version=None, exposure_limit="internal-build-unavailable")
    limited = _reserve(limited_root)
    with pytest.raises(ValueError, match="requires a declared provider_version"):
        deliver_reserved_attempt(limited_root, delivery_root, runner=route,
                                 **{**common, "reservation_id": limited["reservation_id"], "prompt_bytes": limited["prompt_bytes"]})
    # An engineering probe may never dispatch against a real-looking accession.
    real_root = tmp_path / "real-accession"
    _journal(real_root, accession="0000014846-26-000037")
    real = _reserve(real_root, accession="0000014846-26-000037")
    with pytest.raises(ValueError, match="only dispatch against a synthetic accession"):
        deliver_reserved_attempt(real_root, delivery_root, runner=route,
                                 **{**common, "reservation_id": real["reservation_id"], "prompt_bytes": real["prompt_bytes"]})
    assert route.dispatches == [] and not any(delivery_root.iterdir())


def test_native_member_dispositions_never_let_a_substitute_stand_in() -> None:
    prompt = b"template\n" + PRIMARY + b"\n"
    tiny = b"<p>x</p>"
    members = [{"label": "primary", "bytes": PRIMARY, "required": True},
               {"label": "source-view.json", "bytes": PROJECTION, "required": True},
               {"label": "compact.txt", "bytes": PRIMARY[:80], "required": True},
               {"label": "manifest.json", "bytes": tiny, "required": False}]
    custody = native_member_dispositions(prompt, members)
    assert [m["disposition"] for m in custody["members"]] == [
        "delivered_inline", "retained_not_delivered", "delivered_inline", "indeterminate"]
    assert custody["complete_native_delivery"] is False
    assert custody["native_members_declared"] == 4 and custody["required_members_declared"] == 3
    assert native_member_dispositions(prompt, [])["complete_native_delivery"] is None
    # Hash identity alone is never delivery: a prompt carrying only the member's hash keeps it retained.
    pointer = b"template\n" + _sha(PROJECTION).encode("ascii") + b"\n"
    assert native_member_dispositions(pointer, members[1:2])["members"][0]["disposition"] == "retained_not_delivered"
    with pytest.raises(ValueError, match="declared twice"):
        native_member_dispositions(prompt, members[:1] * 2)
    with pytest.raises(ValueError, match="names members that were not supplied"):
        native_member_dispositions(prompt, members[:1], expected_members={
            "primary": {"sha256": _sha(PRIMARY), "byte_length": len(PRIMARY)},
            "reader.txt": {"sha256": "0" * 64, "byte_length": 1}})


def test_default_runner_delivers_exact_stdin_and_preserves_partial_output_on_timeout(tmp_path: Path) -> None:
    journal_root = tmp_path / "journal"
    _journal(journal_root)
    delivery_root = tmp_path / "ledger"
    delivery_root.mkdir()
    fake_cli = tmp_path / "bin" / "claude"
    fake_cli.parent.mkdir()
    fake_cli.write_text(
        "#!" + sys.executable + "\n"
        "import hashlib, json, os, subprocess, sys, time\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('2.1.285 (Claude Code)'); sys.exit(0)\n"
        "data = sys.stdin.buffer.read()\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init', 'model': sys.argv[sys.argv.index('--model') + 1],\n"
        "                  'tools': [], 'claude_code_version': '2.1.285', 'session_id': 'real-1'}), flush=True)\n"
        "if b'SLEEP' in data:\n"
        "    child = subprocess.Popen(['sleep', '60'])\n"
        "    open('pids', 'w').write(f'{os.getpid()} {child.pid}')\n"
        "    time.sleep(60)\n"
        "text = 'sha256:' + hashlib.sha256(data).hexdigest()\n"
        "print(json.dumps({'type': 'assistant', 'session_id': 'real-1', 'message': {'id': 'm1', 'model': 'claude-fable-5-1',\n"
        "                  'stop_reason': 'end_turn', 'usage': {'input_tokens': 1, 'output_tokens': 1},\n"
        "                  'content': [{'type': 'text', 'text': text}]}}))\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': text, 'num_turns': 1,\n"
        "                  'usage': {'input_tokens': 1, 'output_tokens': 1}, 'total_cost_usd': 0, 'session_id': 'real-1'}))\n"
    )
    fake_cli.chmod(fake_cli.stat().st_mode | stat.S_IXUSR)
    environment = {"HOME": str(tmp_path / "home"), "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
    (tmp_path / "home").mkdir()
    reservation = _reserve(journal_root)
    common = {"cli_path": fake_cli, "environment": environment, "engineering_probe": True,
              "native_members": [{"label": "primary", "bytes": PRIMARY, "required": True}]}

    outcome = deliver_reserved_attempt(journal_root, delivery_root, reservation_id=reservation["reservation_id"],
                                       prompt_bytes=reservation["prompt_bytes"], limits=dict(LIMITS), **common)
    expected = ("sha256:" + reservation["prompt_sha256"]).encode("ascii")
    assert outcome["outcome"] == "complete", outcome["receipt"]["reasons"]
    assert outcome["settlement_proposal"]["artifact_bytes"] == expected
    assert outcome["receipt"]["process"]["exit_code"] == 0 and outcome["receipt"]["cli"]["sha256"] == _sha(fake_cli.read_bytes())
    settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])

    # A second synthetic journal, whose frozen leaf template carries the fake CLI's sleep trigger,
    # exercises the timeout path through the real subprocess machinery.
    trigger_root = tmp_path / "trigger-journal"
    trigger_templates = {"leaf": b"SLEEP then echo the exact source span.",
                         "role_synthesis": TEMPLATES["role_synthesis"]}
    packets = [{"role": "primary", "sha256": _sha(PRIMARY), "byte_length": len(PRIMARY)}]
    manifest = build_unit_manifest(
        accession_number=ACCESSION, packets=packets, packet_bytes={"primary": PRIMARY},
        units=[{"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
                "coverage_spans": [{"start": 0, "end": len(PRIMARY)}], "context_spans": []}],
    )
    initialize_journal(
        trigger_root, programme_id="engineering-probe-timeout", accession_number=ACCESSION,
        role_contract=_contract(node_kinds={kind: {"template_sha256": _sha(template)}
                                            for kind, template in trigger_templates.items()}),
        unit_manifest_sha256=_sha(_canonical(manifest)), unit_manifest=manifest, expected_packets=packets,
        packet_bytes={"primary": PRIMARY},
    )
    trigger = reserve_attempt(trigger_root, node_id="l1", node_kind="leaf", context_id="ctx-slow",
                              render_inputs={"template": trigger_templates["leaf"], "unit_id": UNIT_ID})
    trigger_ledger = tmp_path / "trigger-ledger"
    trigger_ledger.mkdir()
    outcome = deliver_reserved_attempt(trigger_root, trigger_ledger, reservation_id=trigger["reservation_id"],
                                       prompt_bytes=trigger["prompt_bytes"],
                                       limits={**LIMITS, "timeout_seconds": 2}, **common)
    assert outcome["outcome"] == "unknown" and outcome["receipt"]["process"]["timed_out"] is True
    assert outcome["receipt"]["process"]["kill_signal"] in ("SIGTERM", "SIGKILL")
    ledger = Path(outcome["ledger_path"])
    partial = (ledger / "stdout.raw").read_bytes()
    assert partial.startswith(b'{"type": "system", "subtype": "init"') and b'"type": "result"' not in partial
    pids = [int(value) for value in (ledger / "cwd" / "pids").read_text().split()]
    assert len(pids) == 2 and all(_process_gone(pid) for pid in pids), pids


def test_ledger_tamper_and_status_matrix_are_rejected(tmp_path: Path) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    route = FakeRoute(_stream(result_text="echo"))
    outcome = deliver_reserved_attempt(journal_root, delivery_root, runner=route, **common)
    ledger = Path(outcome["ledger_path"])
    reservation_id = reservation["reservation_id"]

    # A hand-typed V1 eligible receipt after a non-complete delivery is caught by the binding matrix.
    tampered_stream = ledger / "stdout.raw"
    original_stream = tampered_stream.read_bytes()
    tampered_stream.write_bytes(_stream(result_text="echo", stop_reason="max_tokens"))
    with pytest.raises(ValueError, match="retained delivery file changed: stdout.raw"):
        settle_delivery(journal_root, delivery_root, reservation_id=reservation_id)
    tampered_stream.write_bytes(original_stream)

    receipt = json.loads((ledger / "receipt.json").read_bytes())
    receipt["outcome"] = "failed"
    edited = _canonical(receipt)
    (ledger / "receipt.json").write_bytes(edited)
    with pytest.raises(ValueError, match="disagrees with its retained stream"):
        validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation_id)
    (ledger / "receipt.json").write_bytes(_canonical(outcome["receipt"]))

    # A rewritten ledger cannot re-label a model-mismatch stream: the route identity used for the
    # rebuild comes from the journal contract, and the receipt's own identity must equal it.
    relabelled_root = tmp_path / "relabelled-journal"
    _journal(relabelled_root, programme_id="engineering-probe-relabel")
    relabelled = _reserve(relabelled_root)
    relabelled_ledger = tmp_path / "relabelled-ledger"
    relabelled_ledger.mkdir()
    mismatch = deliver_reserved_attempt(relabelled_root, relabelled_ledger, runner=FakeRoute(_stream(model="claude-other")),
                                        **{**common, "reservation_id": relabelled["reservation_id"],
                                           "prompt_bytes": relabelled["prompt_bytes"]})
    assert mismatch["outcome"] == "failed" and "model_mismatch" in mismatch["receipt"]["reasons"]
    forged_dir = Path(mismatch["ledger_path"])
    forged_request = json.loads((forged_dir / "request.json").read_bytes())
    forged_request["model_requested"] = "claude-other"
    (forged_dir / "request.json").write_bytes(_canonical(forged_request))
    forged = json.loads((forged_dir / "receipt.json").read_bytes())
    forged.update({"model_requested": "claude-other", "request_sha256": _sha(_canonical(forged_request)),
                   "outcome": "complete", "reasons": [], "output": {**forged["output"], "sha256": _sha(b"echo")},
                   "settlement_proposal": {"status": "eligible", "artifact_sha256": _sha(b"echo"), "receipt_kind": "v1_eligible"}})
    (forged_dir / "receipt.json").write_bytes(_canonical(forged))
    with pytest.raises(ValueError, match="route identity differs from the journal contract"):
        settle_delivery(relabelled_root, relabelled_ledger, reservation_id=relabelled["reservation_id"])
    with pytest.raises(ValueError, match="route identity differs from the journal contract"):
        validate_delivery_binding(relabelled_root, relabelled_ledger, reservation_id=relabelled["reservation_id"])
    assert recover_pending_attempt(relabelled_root)["reservation_id"] == relabelled["reservation_id"]

    # An operator settling `failed` for a delivery that completed is rejected by the matrix.
    with pytest.raises(ValueError, match="classified delivery has not been settled"):
        validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation_id)
    settle_attempt(journal_root, reservation_id=reservation_id, status="failed", artifact_bytes=None,
                   receipt={"outcome": "operator-said-failed"})
    with pytest.raises(ValueError, match="journal status failed is not admissible for delivery outcome complete"):
        validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation_id)

    # A failed delivery may be retired by the operator without re-supplying the output bytes.
    retired_root = tmp_path / "retired-journal"
    _journal(retired_root, programme_id="engineering-probe-retired")
    to_retire = _reserve(retired_root)
    retired_ledger = tmp_path / "retired-ledger"
    retired_ledger.mkdir()
    failed = deliver_reserved_attempt(retired_root, retired_ledger, runner=FakeRoute(_stream(is_error=True, subtype="error_during_execution")),
                                      **{**common, "reservation_id": to_retire["reservation_id"], "prompt_bytes": to_retire["prompt_bytes"]})
    assert failed["outcome"] == "failed"
    settle_attempt(retired_root, reservation_id=to_retire["reservation_id"], status="retired", artifact_bytes=None,
                   receipt={"outcome": "operator-retired-after-failed", "delivery_receipt_sha256": failed["receipt_sha256"]})
    validation = validate_delivery_binding(retired_root, retired_ledger, reservation_id=to_retire["reservation_id"])
    assert validation["journal_status"] == "retired" and validation["operator_settled_after_outcome"] == "failed"

    # A different journal cannot adopt the ledger.
    foreign_root = tmp_path / "foreign-journal"
    _journal(foreign_root, programme_id="engineering-probe-foreign")
    foreign = _reserve(foreign_root)
    assert foreign["reservation_id"] != reservation_id
    with pytest.raises(ValueError, match="bound to a different journal"):
        validate_delivery_binding(foreign_root, delivery_root, reservation_id=reservation_id)
    with pytest.raises(ValueError, match="delivery ledger is missing"):
        validate_delivery_binding(journal_root, delivery_root, reservation_id=foreign["reservation_id"])
    with pytest.raises(ValueError, match="incomplete; the dispatch did not reach a receipt"):
        (ledger / "receipt.json").unlink()
        validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation_id)


def test_classifier_precedence_is_deterministic_on_the_same_stream() -> None:
    stream = _stream(compact=True, stop_reason="max_tokens", tools=("Read",), num_turns=3)
    first = classify_stream(stream, exit_code=0, timed_out=False, model_requested=MODEL, provider_version=VERSION)
    assert first["outcome"] == "compacted"
    assert {"stop_reason:max_tokens", "tools_enabled", "num_turns:3"} <= set(first["reasons"])
    assert first["finish_metadata_observed"] is True
    timed = classify_stream(stream, exit_code=-9, timed_out=True, model_requested=MODEL, provider_version=VERSION)
    assert timed["outcome"] == "unknown" and timed["reasons"] == ["timed_out"]
    clean = classify_stream(_stream(result_text="k" * 10), exit_code=0, timed_out=False,
                            model_requested=MODEL, provider_version=VERSION)
    assert clean["outcome"] == "complete" and clean["output_bytes"] == b"k" * 10
    assert clean["observed"]["event_type_counts"] == {"system/init": 1, "assistant": 1, "result/success": 1}
    # A pathologically nested line is unparseable, never a crash.
    nested = _stream() + b"[" * 200000 + b"\n"
    deep = classify_stream(nested, exit_code=0, timed_out=False, model_requested=MODEL, provider_version=VERSION)
    assert deep["outcome"] == "failed" and deep["reasons"] == ["stream_schema:unparseable_lines"]


@pytest.mark.parametrize("reported_model", ["claude-other", None])
def test_assistant_model_must_match_frozen_contract(reported_model: str | None) -> None:
    events = [json.loads(line) for line in _stream().splitlines()]
    next(event for event in events if event["type"] == "assistant")["message"]["model"] = reported_model
    raw = b"\n".join(_canonical(event) for event in events) + b"\n"
    result = delivery.classify_stream(raw, exit_code=0, timed_out=False,
                                      model_requested=MODEL, provider_version=VERSION)
    assert result["outcome"] == "failed"
    reason = "stream_schema:assistant_model" if reported_model is None else "assistant_model_mismatch"
    assert reason in result["reasons"]


def test_settlement_rejects_rehashed_stdin_before_journal_mutation(tmp_path: Path) -> None:
    journal_root, delivery_root, reservation, common = _setup(tmp_path)
    outcome = deliver_reserved_attempt(journal_root, delivery_root, runner=FakeRoute(_stream()), **common)
    ledger = Path(outcome["ledger_path"])
    changed = b"Synthetic bytes that are not the reserved prompt.\n"
    (ledger / "stdin.bin").write_bytes(changed)
    receipt = json.loads((ledger / "receipt.json").read_bytes())
    receipt["stdin"].update(sha256=_sha(changed), byte_length=len(changed))
    (ledger / "receipt.json").write_bytes(_canonical(receipt))
    with pytest.raises(ValueError, match="does not bind the journal reservation"):
        settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
    pending = recover_pending_attempt(journal_root)
    assert pending["reservation_id"] == reservation["reservation_id"]
    assert pending["prompt_bytes"] == reservation["prompt_bytes"]
