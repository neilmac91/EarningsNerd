#!/usr/bin/env python3
"""Create compact, hash-bound continuation evidence after one diagnostic pair."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT_RATE = Decimal("0.150000")
OUTPUT_RATE = Decimal("0.600000")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def ledger_snapshot(path: Path) -> dict:
    if not path.is_file():
        return {"present": False, "calls": 0, "reserved_usd": "0", "known_usage_usd": "0",
                "pending": 0, "stop_reason": None, "reservations": []}
    with sqlite3.connect(path) as db:
        programme = db.execute("SELECT manifest_sha256, stop_reason FROM programme WHERE id=1").fetchone()
        rows = db.execute("""SELECT id, slot_id, operation, request_sha256, input_bound,
            output_max, reserved_usd, status, outcome, usage_json, actual_model
            FROM reservations ORDER BY id""").fetchall()
    reservations = []
    known = Decimal(0)
    for row in rows:
        usage = json.loads(row[9]) if row[9] else None
        if usage and type(usage.get("prompt_tokens")) is int and type(usage.get("completion_tokens")) is int:
            known += ((Decimal(usage["prompt_tokens"]) * INPUT_RATE
                       + Decimal(usage["completion_tokens"]) * OUTPUT_RATE) / Decimal(1_000_000))
        reservations.append(dict(zip(("id", "slot_id", "operation", "request_sha256",
            "input_bound", "output_max", "reserved_usd", "status", "outcome",
            "usage", "actual_model"), row[:9] + (usage, row[10]))))
    return {"present": True, "manifest_sha256": programme[0], "stop_reason": programme[1],
            "calls": len(rows), "reserved_usd": str(sum((Decimal(row[6]) for row in rows), Decimal(0))),
            "known_usage_usd": str(known.quantize(Decimal("0.000000001"))),
            "pending": sum(row[7] == "pending" for row in rows), "reservations": reservations}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--prepare-receipt", type=Path, required=True)
    parser.add_argument("--subject-repo", type=Path, required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-head-sha", required=True)
    parser.add_argument("--workflow-head-branch", required=True)
    args = parser.parse_args()
    manifest_path = HERE / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    subject_repo = args.subject_repo.resolve()
    if (git(subject_repo, "rev-parse", "HEAD") != manifest["code"]["head"]
            or git(subject_repo, "rev-parse", "HEAD^{tree}") != manifest["code"]["tree"]
            or git(subject_repo, "status", "--porcelain")):
        raise SystemExit("subject checkout changed after the offline preflight")
    pair_order = manifest["pair_order"]
    prepared = json.loads(args.prepare_receipt.read_text())
    pair_receipt_path = args.state_dir / "pairs" / f"{args.pair_id}.json"
    pair_receipt = json.loads(pair_receipt_path.read_text()) if pair_receipt_path.is_file() else {}
    pair_complete = pair_receipt.get("status") == "complete"
    prior = prepared.get("completed_pairs") if isinstance(prepared.get("completed_pairs"), list) else []
    completed = prior + ([args.pair_id] if pair_complete else [])
    outputs = {}
    for arm, key in (("control", "control"), ("thinking-low", "thinking_low")):
        path = args.state_dir / "runs" / f"{args.pair_id}-{arm}" / "payload.json"
        outputs[key] = sha(path) if path.is_file() else None
    ledger_path = args.state_dir / "pilot-ledger.sqlite3"
    ledger = ledger_snapshot(ledger_path)
    continuation = {
        "schema": "thinking-low-continuation-v1",
        "status": "complete" if pair_complete and ledger["pending"] == 0 and not ledger["stop_reason"] else "error",
        "manifest_sha256": sha(manifest_path),
        "capsule_lock_sha256": sha(HERE / "capsule-lock.json"),
        "subject_head": manifest["code"]["head"], "subject_tree": manifest["code"]["tree"],
        "workflow_run_id": args.workflow_run_id, "workflow_head_sha": args.workflow_head_sha,
        "workflow_head_branch": args.workflow_head_branch, "pair_order": pair_order,
        "completed_pairs": completed, "last_pair": args.pair_id,
        "last_pair_outputs": outputs, "next_pair": (
            pair_order[len(completed)] if len(completed) < len(pair_order)
            and continuation_safe_prefix(completed, pair_order) else None
        ),
        "semantic_review": "pending", "ledger_sha256": sha(ledger_path) if ledger_path.is_file() else None,
        "ledger": ledger,
    }
    (args.state_dir / "continuation.json").write_text(
        json.dumps(continuation, indent=2, sort_keys=True) + "\n")
    rows = []
    for path in sorted(args.state_dir.rglob("*")):
        if path.is_symlink():
            raise SystemExit("state contains a symlink")
        if path.is_file() and path.name != "inventory.json":
            raw = path.read_bytes()
            rows.append({"path": path.relative_to(args.state_dir).as_posix(), "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest()})
    inventory = {"schema": "thinking-low-state-inventory-v1", "files": rows,
                 "total_bytes": sum(row["bytes"] for row in rows)}
    (args.state_dir / "inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    print(args.state_dir / "continuation.json")
    return 0 if continuation["status"] == "complete" else 1


def continuation_safe_prefix(completed: list[str], order: list[str]) -> bool:
    return completed == order[:len(completed)]


if __name__ == "__main__":
    raise SystemExit(main())
