"""Gate for the CODE RED runtime records under ``tasks/code-red-20261004/runtime/`` (CLAUDE.md rule 12).

Every record PR's independent reviewer re-derived the same invariants by hand before merge. This test derives them in CI so
a broken record never reaches a reviewer:

* every row of ``CHECKPOINT.md``'s deliverables table carries a well-formed SHA-256 and names a file whose digest equals it, and
  every file under the runtime tree has a row (the checkpoint is the durable index of the records);
* the ``control/source-context-exclusion-NNN.json`` closures form an append-only chain anchored to the committed tail (closures
  136–164 present, closure 164 pinned by digest): each one's ``prior_record`` hash equals the previous file, its counts equal its
  lists, the previous ids are a prefix, nothing is duplicated, and the new entries are the ones it declares;
* the checkpoint header and ``APPOINTMENTS.json`` are stamped no earlier than the newest closure, compared at the closure's
  fractional precision (they are written last);
* every non-blank line of the decisions section is a numbered entry and the numbers run contiguously from 1;
* every JSON file parses;
* no private artifact URL (either link form), macOS home path (``/Users/``) or, anywhere under the chief's ``control/`` tree,
  session upload-area path is written into the records — every file in the tree is scanned, whatever its suffix.

Records-only PRs touch nothing under ``backend/``, yet CI runs the backend gate on every PR, so this test runs on each record PR;
it lives under ``backend/tests/`` and therefore never triggers ``deploy-backend`` (the detector ignores that directory). The tree's
absence fails the module rather than skipping it.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME = REPO_ROOT / "tasks" / "code-red-20261004" / "runtime"
CONTROL = RUNTIME / "control"
CHECKPOINT = RUNTIME / "CHECKPOINT.md"
APPOINTMENTS = CONTROL / "APPOINTMENTS.json"

# Every body row of the deliverables table must parse as | `path` | `digest` |, and its digest is then validated, so a
# malformed or unbackticked row fails instead of being dropped.
TABLE_ROW = re.compile(r"^\| `([^`]+)` \| `([^`]*)` \|")
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
HEADER_STAMP = re.compile(r"\(updated (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\)")
CLOSURE_NAME = re.compile(r"^source-context-exclusion-(\d+)\.json$")
DELIVERABLES_HEADING = "## Deliverables and exact hashes (SHA-256)"
DECISIONS_HEADING = "## Decisions taken by the chief"
# Every non-blank line of the decisions section is one entry of the form ``N. text`` (a malformed entry fails, not vanishes).
DECISION_LINE = re.compile(r"^(\d+)\. \S")
# Hash rows may point outside the runtime tree only into these trees (the chief-committed D1/D3/D5 deliverables).
ALLOWED_OFF_TREE = (REPO_ROOT / "tasks" / "readiness-2026-09-21" / "beta",)

# Strings that must never appear in the chief's own records (the repository is public; these belong to private stores).
FORBIDDEN_EVERYWHERE = ("claude.ai/artifact", "claude.ai/code/artifact", "/Users/")
FORBIDDEN_IN_CONTROL = FORBIDDEN_EVERYWHERE + (".claude/uploads",)

# The tree is a durable record: its absence is a failure, never a skip (a PR that deleted or renamed it would otherwise stay
# green). The closure chain is anchored to its committed tail so no suffix of the chain can be removed.
COMMITTED_CLOSURES = range(136, 165)
COMMITTED_TAIL = (
    "source-context-exclusion-164.json",
    "3e486add2a9c136d8b434a3544bb1fb6a9c4287a82bda5e88def112582802eec",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _section(text: str, heading: str) -> str:
    """The body of one ``## `` section of CHECKPOINT.md, from its heading line to the next ``## `` heading."""
    match = re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE)
    assert match, f"CHECKPOINT.md has no {heading!r} heading line"
    end = text.find("\n## ", match.end())
    return text[match.start() : end if end != -1 else None]


def _checkpoint_rows() -> list[tuple[str, str]]:
    """Every body row of the deliverables table, each required to parse and to carry a well-formed digest."""
    section = _section(CHECKPOINT.read_text(encoding="utf-8"), DELIVERABLES_HEADING)
    table_lines = [line for line in section.splitlines()[1:] if line.strip()]
    assert len(table_lines) >= 3, "the deliverables table has no body rows"
    _header, _separator, *body = table_lines
    assert _header.startswith("|") and not TABLE_ROW.match(_header), (
        f"the deliverables section's first line is not the table header: {_header!r}"
    )
    assert re.fullmatch(r"\|(?:-+\|)+", _separator), (
        f"the deliverables section's second line is not the table's separator row: {_separator!r}"
    )
    unparsed = [line for line in body if not TABLE_ROW.match(line)]
    assert not unparsed, f"deliverables rows that do not parse as | `path` | `sha256` |: {unparsed}"
    rows = [(match.group(1), match.group(2)) for match in map(TABLE_ROW.match, body) if match]
    malformed = [path for path, digest in rows if not SHA256_HEX.fullmatch(digest)]
    assert not malformed, f"hash rows whose digest is not 64 lowercase hex characters: {malformed}"
    return rows


def _closures() -> list[Path]:
    files = [p for p in CONTROL.iterdir() if CLOSURE_NAME.match(p.name)]
    return sorted(files, key=lambda p: int(CLOSURE_NAME.match(p.name).group(1)))


def _stamp(value: str) -> datetime:
    """Parse ``…Z`` or ``…+00:00`` stamps, keeping any fractional seconds (a stamp without a fraction is the exact second)."""
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _runtime_files() -> set[Path]:
    return {p for p in RUNTIME.rglob("*") if p.is_file() and p != CHECKPOINT}


def test_runtime_tree_is_present() -> None:
    missing = [str(p.relative_to(REPO_ROOT)) for p in (RUNTIME, CONTROL, CHECKPOINT, APPOINTMENTS) if not p.exists()]
    assert not missing, f"the CODE RED runtime records are missing from the tree: {missing}"


def test_checkpoint_hash_rows_match_their_files() -> None:
    rows = _checkpoint_rows()
    assert rows, "CHECKPOINT.md has no hash rows"
    paths = [path for path, _ in rows]
    assert len(paths) == len(set(paths)), f"duplicate hash-row paths: {sorted(p for p in paths if paths.count(p) > 1)}"
    mismatched = []
    missing = []
    escaped = []
    for rel, recorded in rows:
        target = (RUNTIME / rel).resolve()
        if not (target.is_relative_to(RUNTIME) or any(target.is_relative_to(root) for root in ALLOWED_OFF_TREE)):
            escaped.append(rel)
        elif not target.is_file():
            missing.append(rel)
        elif _sha256(target) != recorded:
            mismatched.append(rel)
    assert not escaped, f"hash rows escape the permitted trees: {escaped}"
    assert not missing, f"hash rows name files that do not exist: {missing}"
    assert not mismatched, f"hash rows disagree with the files on disk: {mismatched}"


def test_every_runtime_file_has_a_checkpoint_row() -> None:
    tabled = {(RUNTIME / rel).resolve() for rel, _ in _checkpoint_rows()}
    untabled = sorted(str(p.relative_to(RUNTIME)) for p in _runtime_files() if p.resolve() not in tabled)
    assert not untabled, f"files under the runtime tree without a CHECKPOINT.md hash row: {untabled}"


def test_closure_chain_is_append_only() -> None:
    present = {int(CLOSURE_NAME.match(p.name).group(1)) for p in _closures()}
    missing = sorted(n for n in COMMITTED_CLOSURES if n not in present)
    assert not missing, f"committed exclusion closures are missing: {missing}"
    tail_name, tail_sha = COMMITTED_TAIL
    assert _sha256(CONTROL / tail_name) == tail_sha, f"{tail_name} no longer has its committed digest"
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
            declared = list(data.get("new_actual_contexts") or []) + list(data.get("new_provisional_contexts") or [])
            assert sorted(declared) == sorted(ids[len(prev_ids) :]), (
                f"{path.name}: declared new contexts != appended ids"
            )
            assert sorted(data.get("new_context_roles") or {}) == sorted(declared), (
                f"{path.name}: new_context_roles keys != new ids"
            )
            resolved = data.get("provisional_labels_resolved") or {}
            unknown = sorted(label for label in resolved if label not in prev_ids)
            assert not unknown, f"{path.name}: resolves labels never registered: {unknown}"
        previous = (path, _sha256(path), data)


def test_checkpoint_and_appointments_are_stamped_after_the_newest_closure() -> None:
    newest = json.loads(_closures()[-1].read_text(encoding="utf-8"))
    closure_stamp = _stamp(newest["recorded_at"])
    header = HEADER_STAMP.search(CHECKPOINT.read_text(encoding="utf-8"))
    assert header, "CHECKPOINT.md header carries no '(updated YYYY-MM-DDTHH:MM:SSZ)' stamp"
    assert _stamp(header.group(1)) >= closure_stamp, "CHECKPOINT.md is stamped earlier than the newest closure"
    appointments = json.loads(APPOINTMENTS.read_text(encoding="utf-8"))
    assert _stamp(appointments["updated_at"]) >= closure_stamp, (
        "APPOINTMENTS.json is stamped earlier than the newest closure"
    )


def test_decisions_are_numbered_contiguously() -> None:
    section = _section(CHECKPOINT.read_text(encoding="utf-8"), DECISIONS_HEADING)
    entries = [line for line in section.splitlines()[1:] if line.strip()]
    malformed = [line for line in entries if not DECISION_LINE.match(line)]
    assert not malformed, f"decisions section lines that are not numbered entries: {malformed}"
    numbers = [int(match.group(1)) for match in map(DECISION_LINE.match, entries) if match]
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
        text = path.read_text(encoding="utf-8", errors="replace")
        needles = FORBIDDEN_IN_CONTROL if (path == CHECKPOINT or CONTROL in path.parents) else FORBIDDEN_EVERYWHERE
        for needle in needles:
            if needle in text:
                offenders.append(f"{path.relative_to(RUNTIME)}: {needle!r}")
    assert not offenders, f"private or local-machine strings in the records: {offenders}"
