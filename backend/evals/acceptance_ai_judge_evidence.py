"""Offline verifier for the retained E7 Fable subscription-CLI invocation ledger.

The caller reconstructs and hashes the exact judge input for all 120 approved slots
and development-smoke. Local receipts establish retained bytes and declared CLI
metadata; they do not authenticate a provider or replace source-grounded review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.acceptance_readiness import COMPARATOR_HOLDOUT_IDS, _evidence, _utc
from evals.judge import _JUDGE_SYSTEM, parse_judge_response


MODEL = "cli:claude-fable-5-1"
CLI_VERSION = "2.1.278"
CONTRACT_VERSION = "2"
_CALL_KEYS = {"slot_id", "attempt", "kind", "input", "stdout", "stderr", "receipt"}
_RECEIPT_KEYS = {
    "schema_version", "programme_id", "slot_id", "attempt", "kind", "invocation_id", "model",
    "contract_version", "cli_version", "auth_mode", "argv", "exit_code",
    "started_at", "finished_at", "input_sha256", "stdout_sha256", "stderr_sha256",
}
_ARGV = [
    "claude", "-p", "--model", "claude-fable-5-1", "--output-format", "json",
    "--system-prompt", _JUDGE_SYSTEM,
    "--tools", "", "--strict-mcp-config", "--no-session-persistence",
]
_PROBE_ARGV_PREFIX = ["claude", "-p", "--model", "claude-fable-5-1", "--output-format", "json"]
_EXPECTED_SLOTS = {f"H{i:02d}-candidate-{draw}" for i in range(1, 31) for draw in (1, 2, 3)}
_EXPECTED_SLOTS |= {f"{holdout}-comparator-{draw}" for holdout in COMPARATOR_HOLDOUT_IDS
                    for draw in (1, 2, 3)}
_EXPECTED_SLOTS.add("development-smoke")


def _problem(issues: list[str], detail: str) -> None:
    issues.append(detail)


def _raw_bytes(base: Path, record: Any) -> bytes:
    path, _ = _evidence(base, record)
    return path.read_bytes()


def _cli_result(stdout: bytes, exit_code: int) -> tuple[str, str | None]:
    """Return result text and CLI error reason; malformed output is not retryable."""
    if exit_code != 0:
        return "", f"CLI exit {exit_code}"
    try:
        outer = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("CLI stdout is not JSON") from exc
    if not isinstance(outer, dict):
        raise ValueError("CLI stdout wrapper is not an object")
    if outer.get("is_error") is True or outer.get("subtype") not in (None, "success"):
        return "", "CLI error wrapper"
    if outer.get("is_error") is not False:
        raise ValueError("CLI is_error flag missing or invalid")
    result = outer.get("result")
    if not isinstance(result, str):
        raise ValueError("CLI result missing")
    return result, None


def _valid_verdict_result(raw: str) -> bool:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(value, dict) or set(value) != {"gate_failures", "dimensions", "verdict", "notes"}:
        return False
    if (not isinstance(value["gate_failures"], list) or
            any(not isinstance(item, str) or not item.strip() for item in value["gate_failures"])):
        return False
    dimensions = value["dimensions"]
    if (not isinstance(dimensions, dict) or
            set(dimensions) != {"faithfulness", "insight", "clarity", "specificity"} or
            any(type(number) is not int or number < 1 or number > 5 for number in dimensions.values())):
        return False
    return value["verdict"] in {"PASS", "FAIL"} and isinstance(value["notes"], str)


def validate_judge_ledger(
    base: Path, record: dict[str, Any], expected_inputs: dict[str, str],
) -> dict[str, Any]:
    """Validate exact E7 calls, retries and raw outcomes without invoking Fable.

    ``expected_inputs`` must come from the caller's independent reconstruction of
    the exact CLI stdin bytes, not from this ledger's claims.
    """
    issues: list[str] = []
    verdicts: dict[str, dict[str, Any]] = {}
    if (not isinstance(expected_inputs, dict) or set(expected_inputs) != _EXPECTED_SLOTS or
            any(not isinstance(slot, str) or not isinstance(sha, str) or len(sha) != 64 or
                any(char not in "0123456789abcdef" for char in sha)
                for slot, sha in expected_inputs.items())):
        return {"complete": False, "issues": ["expected 120 slots plus development-smoke with exact input hashes"],
                "verdicts": {}}
    base = Path(base)
    try:
        _, ledger = _evidence(base, record)
        if (ledger is None or set(ledger) != {"schema_version", "programme_id", "kind", "model",
                                               "contract_version", "cli_version", "entries"} or
                type(ledger["schema_version"]) is not int or ledger["schema_version"] != 1 or
                ledger["programme_id"] != "E7" or
                ledger["kind"] != "e7_fable_cli_ledger" or ledger["model"] != MODEL or
                ledger["contract_version"] != CONTRACT_VERSION or
                ledger["cli_version"] != CLI_VERSION or
                not isinstance(ledger["entries"], list)):
            raise ValueError("judge ledger header invalid")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return {"complete": False, "issues": [f"judge ledger unavailable: {type(exc).__name__}"],
                "verdicts": {}}
    entries = ledger["entries"]
    if len(entries) > 243:
        _problem(issues, "Fable CLI invocation ceiling exceeded")
    attempts: dict[str, list[dict[str, Any]]] = {}
    invocation_ids: set[str] = set()
    raw_paths: set[str] = set()
    probe_count = 0
    for position, entry in enumerate(entries):
        label = f"entry {position}"
        try:
            if not isinstance(entry, dict) or set(entry) != _CALL_KEYS:
                raise ValueError("entry shape invalid")
            slot = entry["slot_id"]
            kind = entry["kind"]
            attempt = entry["attempt"]
            if (kind not in {"quota_probe", "substantive"} or
                    type(attempt) is not int or attempt not in {1, 2} or
                    (kind == "quota_probe" and (slot != "quota-probe" or attempt != 1)) or
                    (kind == "substantive" and slot not in expected_inputs)):
                raise ValueError("unknown E7 slot, call kind or attempt")
            for artifact_name in ("stdout", "stderr", "receipt"):
                artifact = entry[artifact_name]
                artifact_path = artifact.get("path") if isinstance(artifact, dict) else None
                if not isinstance(artifact_path, str) or artifact_path in raw_paths:
                    raise ValueError("CLI output or receipt path reused")
                raw_paths.add(artifact_path)
            input_bytes = _raw_bytes(base, entry["input"])
            stdout = _raw_bytes(base, entry["stdout"])
            _raw_bytes(base, entry["stderr"])
            _, receipt = _evidence(base, entry["receipt"])
            if receipt is None or set(receipt) != _RECEIPT_KEYS:
                raise ValueError("CLI receipt shape invalid")
            if (type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1 or
                    receipt["programme_id"] != "E7" or
                    receipt["slot_id"] != slot or receipt["kind"] != kind or
                    receipt["attempt"] != attempt or receipt["model"] != MODEL or
                    receipt["contract_version"] != CONTRACT_VERSION or
                    receipt["cli_version"] != CLI_VERSION or
                    receipt["auth_mode"] != "subscription_oauth_no_api_key" or
                    (kind == "substantive" and receipt["argv"] != _ARGV) or
                    (kind == "quota_probe" and (
                        not isinstance(receipt["argv"], list) or
                        receipt["argv"][:len(_PROBE_ARGV_PREFIX)] != _PROBE_ARGV_PREFIX or
                        any(not isinstance(arg, str) for arg in receipt["argv"]))) or
                    type(receipt["exit_code"]) is not int or
                    receipt["input_sha256"] != entry["input"]["sha256"] or
                    receipt["stdout_sha256"] != entry["stdout"]["sha256"] or
                    receipt["stderr_sha256"] != entry["stderr"]["sha256"]):
                raise ValueError("CLI receipt identity or byte hashes differ")
            started, finished = _utc(receipt["started_at"]), _utc(receipt["finished_at"])
            if started is None or finished is None or finished < started:
                raise ValueError("CLI invocation times invalid")
            invocation_id = receipt["invocation_id"]
            if (not isinstance(invocation_id, str) or not invocation_id.strip() or
                    invocation_id in invocation_ids):
                raise ValueError("CLI invocation ID missing or reused")
            invocation_ids.add(invocation_id)
            if kind == "substantive" and entry["input"]["sha256"] != expected_inputs[slot]:
                raise ValueError("judge input differs from independently reconstructed bytes")
            # Hash equality above checks the exact retained bytes; the receipt records
            # what the CLI call claims it received, without silently normalizing text.
            if not input_bytes:
                raise ValueError("empty CLI input")
            raw, cli_error = _cli_result(stdout, receipt["exit_code"])
            verdict = None
            if cli_error is None:
                if kind == "quota_probe":
                    if raw.strip() != "OK":
                        raise ValueError("quota probe reply differs from OK")
                else:
                    if not _valid_verdict_result(raw):
                        raise ValueError("CLI result does not satisfy judge contract")
                    parsed = parse_judge_response(raw)
                    if parsed.error:
                        raise ValueError("judge response parser rejected CLI result")
                    verdict = parsed.verdict.lower()
            item = {"attempt": attempt, "input_sha256": entry["input"]["sha256"],
                    "stdout_sha256": entry["stdout"]["sha256"], "started_at": started,
                    "finished_at": finished, "cli_error": cli_error, "verdict": verdict,
                    "raw": raw}
            attempts.setdefault(slot, []).append(item)
            if kind == "quota_probe":
                probe_count += 1
        except (OSError, KeyError, TypeError, ValueError) as exc:
            _problem(issues, f"{label}: {type(exc).__name__}: {exc}")
    if probe_count > 1:
        _problem(issues, "more than one Fable quota probe")
    for slot in expected_inputs:
        history = attempts.get(slot, [])
        if not history or len(history) > 2 or [row["attempt"] for row in history] != list(range(1, len(history) + 1)):
            _problem(issues, f"{slot}: missing, excess or out-of-order substantive attempts")
            continue
        if len(history) == 2 and (history[0]["cli_error"] is None or
                                  history[0]["input_sha256"] != history[1]["input_sha256"] or
                                  history[1]["started_at"] < history[0]["finished_at"]):
            _problem(issues, f"{slot}: retry was not after a CLI error on identical input")
        last = history[-1]
        if last["cli_error"] is not None or last["verdict"] not in {"pass", "fail"}:
            _problem(issues, f"{slot}: no complete Fable verdict")
            continue
        verdicts[slot] = {"verdict": last["verdict"], "raw": last["raw"],
                          "stdout_sha256": last["stdout_sha256"],
                          "input_sha256": last["input_sha256"], "attempts": len(history)}
    if probe_count == 1 and (len(attempts.get("quota-probe", [])) != 1 or
                             attempts["quota-probe"][0]["cli_error"] is not None):
        _problem(issues, "quota probe history incomplete")
    if set(attempts) != set(expected_inputs) | ({"quota-probe"} if probe_count else set()):
        _problem(issues, "ledger contains unknown or omitted invocation identity")
    return {"complete": not issues and len(verdicts) == 121,
            "issues": issues, "verdicts": verdicts, "invocations": len(entries)}
