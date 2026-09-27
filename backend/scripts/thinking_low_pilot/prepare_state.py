#!/usr/bin/env python3
"""Validate an explicit prior diagnostic artifact and prepare the next durable state."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(receipt: dict, path: Path, message: str) -> None:
    receipt["errors"].append(message)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    raise SystemExit(message)


def safe_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("prior artifact contains a symlink")
        if path.is_file():
            relative = path.relative_to(root)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("prior artifact path escapes its root")
            files.append(path)
    if sum(path.stat().st_size for path in files) > 25 * 1024 * 1024:
        raise ValueError("prior artifact exceeds 25 MiB")
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--previous-dir", type=Path)
    parser.add_argument("--previous-run-metadata", type=Path)
    parser.add_argument("--previous-run-id", default="")
    parser.add_argument("--previous-state-sha256", default="")
    parser.add_argument("--previous-verdict", choices=("FIRST", "PASS"), required=True)
    parser.add_argument("--previous-control-sha256", default="")
    parser.add_argument("--previous-candidate-sha256", default="")
    parser.add_argument("--workflow-head-sha", required=True)
    parser.add_argument("--workflow-head-branch", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = HERE / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    pair_order = manifest["pair_order"]
    receipt = {"schema": "thinking-low-state-prepare-v1", "pair_id": args.pair_id,
               "previous_run_id": args.previous_run_id or None, "errors": []}
    if args.pair_id not in pair_order:
        fail(receipt, args.receipt, "pair is not in the frozen sequence")
    index = pair_order.index(args.pair_id)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    if any(args.state_dir.iterdir()):
        fail(receipt, args.receipt, "new state directory is not empty")

    if index == 0:
        if (args.previous_verdict != "FIRST" or args.previous_run_id
                or args.previous_state_sha256 or args.previous_control_sha256
                or args.previous_candidate_sha256 or args.previous_dir
                or args.previous_run_metadata):
            fail(receipt, args.receipt, "first pair must not claim prior state")
        receipt.update(status="prepared", completed_pairs=[])
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return 0

    if (args.previous_verdict != "PASS" or not re.fullmatch(r"[1-9][0-9]*", args.previous_run_id)
            or not re.fullmatch(r"[0-9a-f]{64}", args.previous_state_sha256)
            or not re.fullmatch(r"[0-9a-f]{64}", args.previous_control_sha256)
            or not re.fullmatch(r"[0-9a-f]{64}", args.previous_candidate_sha256)
            or args.previous_dir is None or args.previous_run_metadata is None):
        fail(receipt, args.receipt, "continuation requires exact prior run, state and reviewed output hashes")
    metadata = json.loads(args.previous_run_metadata.read_text())
    if (str(metadata.get("id")) != args.previous_run_id
            or metadata.get("event") != "workflow_dispatch"
            or metadata.get("conclusion") != "success"
            or metadata.get("path") != ".github/workflows/ci.yml"
            or metadata.get("head_sha") != args.workflow_head_sha
            or metadata.get("head_branch") != args.workflow_head_branch):
        fail(receipt, args.receipt, "prior workflow identity does not match this frozen diagnostic")
    try:
        files = safe_files(args.previous_dir)
    except ValueError as exc:
        fail(receipt, args.receipt, str(exc))
    continuation_path = args.previous_dir / "continuation.json"
    if not continuation_path.is_file() or sha(continuation_path) != args.previous_state_sha256:
        fail(receipt, args.receipt, "prior continuation hash differs")
    continuation = json.loads(continuation_path.read_text())
    expected_previous = pair_order[index - 1]
    if (continuation.get("schema") != "thinking-low-continuation-v1"
            or continuation.get("manifest_sha256") != sha(manifest_path)
            or continuation.get("capsule_lock_sha256") != sha(HERE / "capsule-lock.json")
            or continuation.get("subject_head") != manifest["code"]["head"]
            or continuation.get("subject_tree") != manifest["code"]["tree"]
            or continuation.get("workflow_run_id") != int(args.previous_run_id)
            or continuation.get("workflow_head_sha") != args.workflow_head_sha
            or continuation.get("pair_order") != pair_order
            or continuation.get("completed_pairs") != pair_order[:index]
            or continuation.get("last_pair") != expected_previous
            or continuation.get("status") != "complete"):
        fail(receipt, args.receipt, "prior continuation authority is incomplete or from another programme")
    outputs = continuation.get("last_pair_outputs")
    if outputs != {"control": args.previous_control_sha256,
                   "thinking_low": args.previous_candidate_sha256}:
        fail(receipt, args.receipt, "reviewed hashes do not match the prior continuation")
    ledger_path = args.previous_dir / "pilot-ledger.sqlite3"
    if not ledger_path.is_file() or sha(ledger_path) != continuation.get("ledger_sha256"):
        fail(receipt, args.receipt, "prior durable ledger hash differs")
    inventory_path = args.previous_dir / "inventory.json"
    inventory = json.loads(inventory_path.read_text()) if inventory_path.is_file() else None
    if (not isinstance(inventory, dict)
            or inventory.get("schema") != "thinking-low-state-inventory-v1"
            or not isinstance(inventory.get("files"), list)):
        fail(receipt, args.receipt, "prior artifact inventory is missing")
    try:
        inventory_rows = inventory["files"]
        inventory_map = {row["path"]: row["sha256"] for row in inventory_rows}
    except (KeyError, TypeError):
        fail(receipt, args.receipt, "prior artifact inventory is malformed")
    if (len(inventory_map) != len(inventory_rows)
            or set(inventory_map) != {
                path.relative_to(args.previous_dir).as_posix()
                for path in files if path.name != "inventory.json"
            }):
        fail(receipt, args.receipt, "prior artifact inventory paths differ")
    for path in files:
        relative = path.relative_to(args.previous_dir).as_posix()
        if relative == "inventory.json":
            continue
        if inventory_map.get(relative) != sha(path):
            fail(receipt, args.receipt, f"prior artifact inventory mismatch: {relative}")

    for path in files:
        relative = path.relative_to(args.previous_dir)
        target = args.state_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    # These are regenerated after the new pair; retaining them would make the next authority ambiguous.
    for name in ("continuation.json", "inventory.json"):
        (args.state_dir / name).unlink(missing_ok=True)
    receipt.update(status="prepared", completed_pairs=pair_order[:index],
                   previous_state_sha256=args.previous_state_sha256)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
