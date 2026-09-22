"""Retained Fable CLI history must cover E7 exactly and reject verdict redraws."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from evals.acceptance_ai_judge_evidence import (_ARGV, _EXPECTED_SLOTS, MODEL,
                                                validate_judge_ledger)


def _write(path: Path, value: object) -> dict[str, str]:
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(json.dumps(value), encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _fixture(root: Path) -> tuple[dict, dict[str, str]]:
    now = datetime.now(timezone.utc).isoformat()
    stdin = _write(root / "stdin.txt", b"Exact source and summary judge input")
    expected = {slot: stdin["sha256"] for slot in _EXPECTED_SLOTS}
    reply = json.dumps({"gate_failures": [], "dimensions": {
        "faithfulness": 5, "insight": 5, "clarity": 5, "specificity": 5},
        "verdict": "PASS", "notes": "supported"})
    entries = []
    for index, slot in enumerate(sorted(_EXPECTED_SLOTS)):
        stdout = _write(root / f"stdout-{index}.json", {
            "is_error": False, "subtype": "success", "result": reply})
        stderr = _write(root / f"stderr-{index}.txt", b"")
        receipt = _write(root / f"receipt-{index}.json", {
            "schema_version": 1, "programme_id": "E7", "slot_id": slot,
            "attempt": 1, "kind": "substantive", "invocation_id": f"call-{index}",
            "model": MODEL, "contract_version": "2", "cli_version": "2.1.278",
            "auth_mode": "subscription_oauth_no_api_key", "argv": _ARGV,
            "exit_code": 0, "started_at": now, "finished_at": now,
            "input_sha256": stdin["sha256"], "stdout_sha256": stdout["sha256"],
            "stderr_sha256": stderr["sha256"]})
        entries.append({"slot_id": slot, "attempt": 1, "kind": "substantive",
                        "input": stdin, "stdout": stdout, "stderr": stderr, "receipt": receipt})
    ledger = {"schema_version": 1, "programme_id": "E7", "kind": "e7_fable_cli_ledger",
              "model": MODEL, "contract_version": "2", "cli_version": "2.1.278",
              "entries": entries}
    return ledger, expected


def test_fable_cli_ledger_exact_coverage_and_no_verdict_redraw(tmp_path: Path) -> None:
    ledger, expected = _fixture(tmp_path)
    record = _write(tmp_path / "ledger.json", ledger)
    valid = validate_judge_ledger(tmp_path, record, expected)
    assert valid["complete"] is True
    assert len(valid["verdicts"]) == 121

    # A coherent second PASS on the same input is forbidden after a verdict.
    first = ledger["entries"][0]
    receipt = json.loads((tmp_path / first["receipt"]["path"]).read_text())
    receipt.update(attempt=2, invocation_id="redraw-after-pass")
    second_stdout = _write(tmp_path / "redraw-stdout.json", {
        "is_error": False, "subtype": "success",
        "result": json.dumps({"gate_failures": [], "dimensions": {
            "faithfulness": 5, "insight": 5, "clarity": 5, "specificity": 5},
            "verdict": "PASS", "notes": "second draw"})})
    receipt["stdout_sha256"] = second_stdout["sha256"]
    second_receipt = _write(tmp_path / "redraw-receipt.json", receipt)
    second_stderr = _write(tmp_path / "redraw-stderr.txt", b"")
    ledger["entries"].insert(1, {"slot_id": first["slot_id"], "attempt": 2,
                                 "kind": "substantive", "input": first["input"],
                                 "stdout": second_stdout, "stderr": second_stderr,
                                 "receipt": second_receipt})
    record = _write(tmp_path / "ledger.json", ledger)
    invalid = validate_judge_ledger(tmp_path, record, expected)
    assert invalid["complete"] is False
    assert any("retry was not after a CLI error" in issue for issue in invalid["issues"])


def test_fable_cli_ledger_rejects_missing_and_foreign_programme(tmp_path: Path) -> None:
    ledger, expected = _fixture(tmp_path)
    ledger["entries"].pop()
    record = _write(tmp_path / "ledger.json", ledger)
    incomplete = validate_judge_ledger(tmp_path, record, expected)
    assert incomplete["complete"] is False
    assert any("missing" in issue for issue in incomplete["issues"])

    ledger["programme_id"] = "E8"
    record = _write(tmp_path / "ledger.json", ledger)
    foreign = validate_judge_ledger(tmp_path, record, expected)
    assert foreign["complete"] is False
    assert any("ledger unavailable" in issue for issue in foreign["issues"])
