"""Gate for the CODE RED runtime records under ``tasks/code-red-20261004/runtime/`` (CLAUDE.md rule 12).

Every record PR's independent reviewer re-derived the same invariants by hand before merge. This test derives them in CI so
a broken record never reaches a reviewer:

* every hash row of ``CHECKPOINT.md`` names a file whose SHA-256 equals the recorded one, and every file under the runtime tree
  has a row (the checkpoint is the durable index of the records);
* the ``control/source-context-exclusion-NNN.json`` closures form an append-only chain: each one's ``prior_record`` hash equals the
  previous file, its counts equal its lists, the previous ids are a prefix, nothing is duplicated, and the new entries are the
  ones it declares;
* the checkpoint header and ``APPOINTMENTS.json`` are stamped no earlier than the newest closure (they are written last);
* the chief's decisions are numbered contiguously from 1;
* every JSON file parses;
* no private artifact URL, local-machine home path or session upload-area path is written into the records.

Records-only PRs touch nothing under ``backend/``, yet CI runs the backend gate on every PR, so this test runs on each record PR;
it lives under ``backend/tests/`` and therefore never triggers ``deploy-backend`` (the detector ignores that directory).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME = REPO_ROOT / "tasks" / "code-red-20261004" / "runtime"
CONTROL = RUNTIME / "control"
CHECKPOINT = RUNTIME / "CHECKPOINT.md"
APPOINTMENTS = CONTROL / "APPOINTMENTS.json"

HASH_ROW = re.compile(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|", re.MULTILINE)
HEADER_STAMP = re.compile(r"\(updated (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\)")
CLOSURE_NAME = re.compile(r"^source-context-exclusion-(\d+)\.json$")
DECISIONS_HEADING = "## Decisions taken by the chief"

# Strings that must never appear in the chief's own records (the repository is public; these belong to private stores).
FORBIDDEN_EVERYWHERE = ("claude.ai/artifact", "/Users/")
FORBIDDEN_IN_CONTROL = FORBIDDEN_EVERYWHERE + (".claude/uploads",)

pytestmark = pytest.mark.skipif(not RUNTIME.is_dir(), reason="CODE RED runtime records are not present")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkpoint_rows() -> list[tuple[str, str]]:
    return HASH_ROW.findall(CHECKPOINT.read_text(encoding="utf-8"))


def _closures() -> list[Path]:
    files = [p for p in CONTROL.iterdir() if CLOSURE_NAME.match(p.name)]
    return sorted(files, key=lambda p: int(CLOSURE_NAME.match(p.name).group(1)))


def _stamp(value: str) -> datetime:
    """Parse ``…Z`` or ``…+00:00`` stamps, with or without fractional seconds, truncated to whole seconds."""
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _runtime_files() -> set[Path]:
    return {p for p in RUNTIME.rglob("*") if p.is_file() and p != CHECKPOINT and "__pycache__" not in p.parts}


def test_checkpoint_hash_rows_match_their_files() -> None:
    rows = _checkpoint_rows()
    assert rows, "CHECKPOINT.md has no hash rows"
    paths = [path for path, _ in rows]
    assert len(paths) == len(set(paths)), f"duplicate hash-row paths: {sorted(p for p in paths if paths.count(p) > 1)}"
    mismatched = []
    missing = []
    for rel, recorded in rows:
        target = (RUNTIME / rel).resolve()
        if not target.is_file():
            missing.append(rel)
        elif _sha256(target) != recorded:
            mismatched.append(rel)
    assert not missing, f"hash rows name files that do not exist: {missing}"
    assert not mismatched, f"hash rows disagree with the files on disk: {mismatched}"


def test_every_runtime_file_has_a_checkpoint_row() -> None:
    tabled = {(RUNTIME / rel).resolve() for rel, _ in _checkpoint_rows()}
    untabled = sorted(str(p.relative_to(RUNTIME)) for p in _runtime_files() if p.resolve() not in tabled)
    assert not untabled, f"files under the runtime tree without a CHECKPOINT.md hash row: {untabled}"


def test_closure_chain_is_append_only() -> None:
    closures = _closures()
    assert len(closures) >= 2, "expected at least two exclusion closures"
    previous: tuple[Path, str, dict] | None = None
    for path in closures:
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = data["excluded_context_ids"]
        assert len(ids) == len(set(ids)), f"{path.name}: duplicate context ids"
        assert data["exclusion_count"] == len(ids), (
            f"{path.name}: exclusion_count {data['exclusion_count']} != {len(ids)} ids"
        )
        if previous is not None:
            prev_path, prev_sha, prev_data = previous
            prior = data["prior_record"]
            assert prior["path"] == f"control/{prev_path.name}", f"{path.name}: prior_record.path is {prior['path']}"
            assert prior["sha256"] == prev_sha, f"{path.name}: prior_record.sha256 does not equal {prev_path.name}"
            prev_ids = prev_data["excluded_context_ids"]
            assert data["previous_count"] == len(prev_ids), f"{path.name}: previous_count != len({prev_path.name} ids)"
            assert ids[: len(prev_ids)] == prev_ids, f"{path.name}: the previous closure's ids are not a prefix"
            assert data.get("all_previous_entries_preserved") is True, (
                f"{path.name}: all_previous_entries_preserved is not true"
            )
            declared = list(data.get("new_actual_contexts", [])) + list(data.get("new_provisional_contexts", []))
            assert sorted(declared) == sorted(ids[len(prev_ids) :]), (
                f"{path.name}: declared new contexts != appended ids"
            )
            assert sorted(data.get("new_context_roles", {})) == sorted(declared), (
                f"{path.name}: new_context_roles keys != new ids"
            )
            resolved = data.get("provisional_labels_resolved", {})
            unknown = sorted(label for label in resolved if label not in prev_ids)
            assert not unknown, f"{path.name}: resolves labels never registered: {unknown}"
        previous = (path, _sha256(path), data)


def test_checkpoint_and_appointments_are_stamped_after_the_newest_closure() -> None:
    newest = json.loads(_closures()[-1].read_text(encoding="utf-8"))
    closure_stamp = _stamp(newest["recorded_at"])
    header = HEADER_STAMP.search(CHECKPOINT.read_text(encoding="utf-8"))
    assert header, "CHECKPOINT.md header carries no '(updated …Z)' stamp"
    assert _stamp(header.group(1)) >= closure_stamp, "CHECKPOINT.md is stamped earlier than the newest closure"
    appointments = json.loads(APPOINTMENTS.read_text(encoding="utf-8"))
    assert _stamp(appointments["updated_at"]) >= closure_stamp, (
        "APPOINTMENTS.json is stamped earlier than the newest closure"
    )


def test_decisions_are_numbered_contiguously() -> None:
    text = CHECKPOINT.read_text(encoding="utf-8")
    start = text.index(DECISIONS_HEADING)
    end = text.find("\n## ", start + len(DECISIONS_HEADING))
    section = text[start : end if end != -1 else None]
    numbers = [int(n) for n in re.findall(r"^(\d+)\. ", section, re.MULTILINE)]
    assert numbers, "no numbered decisions found"
    assert numbers == list(range(1, len(numbers) + 1)), f"decision numbering is not 1..{len(numbers)}: {numbers}"


def test_every_runtime_json_file_parses() -> None:
    broken = []
    for path in sorted(RUNTIME.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:  # pragma: no cover - the message is the point
            broken.append(f"{path.relative_to(RUNTIME)}: {exc}")
    assert not broken, f"JSON files under the runtime tree do not parse: {broken}"


def test_records_carry_no_private_urls_or_local_machine_paths() -> None:
    offenders = []
    for path in sorted(_runtime_files() | {CHECKPOINT}):
        if path.suffix not in {".md", ".json", ".txt", ".sh", ".py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        needles = FORBIDDEN_IN_CONTROL if (path == CHECKPOINT or path.parent == CONTROL) else FORBIDDEN_EVERYWHERE
        for needle in needles:
            if needle in text:
                offenders.append(f"{path.relative_to(RUNTIME)}: {needle!r}")
    assert not offenders, f"private or local-machine strings in the records: {offenders}"
