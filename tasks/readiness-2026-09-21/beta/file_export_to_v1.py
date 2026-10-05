"""Thin adapter from PostHog file-download batch-export parts (JSONLines) to the v1 query-response shape.

No network/database access. Parts are bytes the operator already downloaded and hashed. Fields are
addressed by name (key order in a part is not the projection's), every value is kept exactly as
decoded (no coercion), nothing but columns/results is emitted (no hasMore, offset, warnings or
error), and parts are never joined across runs. The file-route completeness verdict (contract
section 2.0 step 8) is a separate record, never a response field: the released consumer's own
export_complete_observed remains a query-route field and stays false by construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Iterator
from pathlib import Path

from readout_v1 import COLUMNS, MAX_ROWS

MAX_PART_BYTES = 16 * 1024 * 1024
BOMS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")
PRICING_TERMS = ("payment", "plan", "billing", "trial", "quota")
INVENTORY_KEYS = ("id", "sha256", "bytes", "rows")
FILE_ID = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")


def _parse(parts: list[bytes]) -> tuple[list[dict], list[dict]]:
    """One owner for parsing: objects in parts-then-line order, plus per-part facts."""
    expected = set(COLUMNS)
    objects: list[dict] = []
    facts: list[dict] = []
    for index, part in enumerate(parts):
        if len(part) > MAX_PART_BYTES:
            raise ValueError(f"part {index}: byte bound exceeded")
        if part.startswith(BOMS):
            raise ValueError(f"part {index}: byte-order mark present")
        lines = part.split(b"\n")
        if lines[-1] == b"":
            lines.pop()  # only a single trailing empty line is ignored; CR bytes stay in place
        matched = 0
        for number, line in enumerate(lines, 1):
            try:
                obj = json.loads(line.decode("utf-8"))
            except ValueError as exc:
                raise ValueError(f"part {index} line {number}: invalid JSON ({exc})") from None
            if not isinstance(obj, dict):
                raise ValueError(f"part {index} line {number}: not a JSON object")
            if set(obj) != expected:
                raise ValueError(f"part {index} line {number}: key set mismatch "
                                 f"(missing={sorted(expected - set(obj))}, extra={sorted(set(obj) - expected)})")
            matched += list(obj) == COLUMNS
            objects.append(obj)
        facts.append({"bytes": len(part), "bom": False, "cr_bytes": part.count(b"\r"),
                      "trailing_newline": part.endswith(b"\n"), "lines": len(lines), "rows": len(lines),
                      "key_order_matched_rows": matched})
    return objects, facts


def parse_record(parts: list[bytes]) -> dict:
    """Per-part and total parse facts for the receipt; ValueError on a BOM or a key-set deviation."""
    _, facts = _parse(parts)
    totals = {key: sum(fact[key] for fact in facts)
              for key in ("bytes", "cr_bytes", "lines", "rows", "key_order_matched_rows")}
    return {"parts": facts, "totals": {"parts": len(facts), **totals}}


def v1_response_from_parts(parts: list[bytes]) -> dict:
    """Only columns and results, by name, parts order then line order; never hasMore/offset/warnings/error."""
    objects, _ = _parse(parts)
    return {"columns": list(COLUMNS), "results": [[obj[column] for column in COLUMNS] for obj in objects]}


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def file_export_completeness(run_record: dict, parts: list[dict], n_before: int | None,
                             n_after: int | None) -> dict:
    """Contract section 2.0 step 8: every failing rule is listed; the verdict is true only when none fails."""
    failing: list[str] = []
    status = run_record.get("status")
    if status != "Completed":
        failing.append(f"status {status!r} is not Completed")
    if "error" in run_record:
        failing.append(f"error field present: {run_record['error']!r}")
    inventory: dict[str, dict] = {}
    for part in parts:
        if not isinstance(part, dict) or any(key not in part for key in INVENTORY_KEYS):
            failing.append(f"part inventory entry lacks {'/'.join(INVENTORY_KEYS)}: {part!r}")
        else:
            inventory[part["id"]] = part
    rows_parsed = sum(part["rows"] for part in inventory.values())
    records_completed = run_record.get("records_completed")
    counts = {"n_before": n_before, "n_after": n_after, "records_completed": records_completed,
              "rows_parsed": rows_parsed}
    for name, value in counts.items():
        if value is None:
            failing.append(f"{name} not observed")
        elif type(value) is not int:
            failing.append(f"{name} is not an integer: {value!r}")
    if len({value for value in counts.values() if type(value) is int}) > 1:
        failing.append("counts differ: " + ", ".join(f"{name}={value!r}" for name, value in counts.items()))
    if type(n_before) is int and n_before >= MAX_ROWS:
        failing.append(f"n_before {n_before} is not below the LIMIT cap {MAX_ROWS}")
    declared = run_record.get("files")
    if isinstance(declared, list) and all(isinstance(item, str) for item in declared):
        failing.extend(f"file {file_id} not downloaded and hashed" for file_id in declared if file_id not in inventory)
        failing.extend(f"part {part_id} is not in this run's files inventory" for part_id in inventory
                       if part_id not in declared)
    else:
        failing.append("files inventory absent from the run record")
    if status == "FailedBilling":
        failing.append("status FailedBilling (pricing signal)")
    for text in _strings(run_record):
        terms = [term for term in PRICING_TERMS if term in text.lower()]
        if terms:
            failing.append(f"pricing signal {terms} in run record text: {text!r}")
    if rows_parsed == 0 and run_record.get("source_availability_recorded") is not True:
        failing.append("zero rows without a source-availability record")
    return {"status": status, "error": run_record.get("error"), "records_completed": records_completed,
            "n_before": n_before, "n_after": n_after, "rows_parsed": rows_parsed, "files": list(parts),
            "file_export_complete_observed": not failing, "failing_rules": failing}


def _file_id(path: Path) -> str:
    """The part's file id: the trailing UUID of the file name, as the download leg names parts."""
    match = FILE_ID.search(path.stem)
    return match.group(1) if match else path.stem


def _write(path: Path, payload: dict) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts", type=Path, nargs="+", required=True, help="downloaded parts, in files[] order")
    parser.add_argument("--run-record", type=Path, required=True, help="the retrieve response as returned")
    parser.add_argument("--n-before", type=int, required=True, help="count-rows before create")
    parser.add_argument("--n-after", type=int, default=None, help="count-rows after Completed; omit if not observed")
    parser.add_argument("--output", type=Path, required=True, help="v1 query-response JSON for readout_v1.py --events")
    parser.add_argument("--completeness-output", type=Path, required=True)
    args = parser.parse_args()
    parts: list[bytes] = []
    for path in args.parts:
        with path.open("rb") as handle:
            parts.append(handle.read(MAX_PART_BYTES + 1))
    with args.run_record.open("rb") as handle:
        raw_record = handle.read(MAX_PART_BYTES + 1)
    if len(raw_record) > MAX_PART_BYTES:
        raise ValueError("run record byte bound exceeded")
    response = v1_response_from_parts(parts)
    record = parse_record(parts)
    inventory = [{"id": _file_id(path), "sha256": hashlib.sha256(part).hexdigest(),
                  "bytes": fact["bytes"], "rows": fact["rows"]}
                 for path, part, fact in zip(args.parts, parts, record["parts"])]
    completeness = file_export_completeness(json.loads(raw_record), inventory, args.n_before, args.n_after)
    _write(args.output, response)
    _write(args.completeness_output, completeness)


if __name__ == "__main__":
    main()
