"""Gate for the CODE RED runtime records under ``tasks/code-red-20261004/runtime/`` (CLAUDE.md rule 12).

Every record PR's independent reviewer re-derived the same invariants by hand before merge. This test derives them in CI so
a broken record never reaches a reviewer:

* every row of ``CHECKPOINT.md``'s deliverables table carries a well-formed SHA-256 and names a file whose digest equals it,
  every file under the runtime tree has a row (the checkpoint is the durable index of the records), the off-tree deliverable
  rows tabled at this commit stay tabled, and the tree holds no symbolic links;
* the ``control/source-context-exclusion-NNN.json`` closures form an append-only chain anchored to the committed tail (closures
  136–164 present, closure 164 pinned by digest) and numbered without gaps through the newest: each one's ``prior_record``
  hash equals the previous file, its ``recorded_at`` is later than its predecessor's, its counts equal its lists, the previous
  ids are a prefix, nothing is duplicated, and the new entries are the ones it declares;
* the checkpoint header and ``APPOINTMENTS.json`` are stamped no earlier than the newest closure, compared at the closure's
  fractional precision (they are written last), and every stamp compared carries an explicit UTC offset (``Z`` or ``+00:00``;
  a stamp without one is malformed, never repaired);
* every non-blank line of the decisions section is a numbered entry and the numbers run contiguously from 1;
* every JSON file parses, and so does every line of a JSON-lines file;
* no private artifact link (either link form), home-directory path (``/Users/``) or, anywhere under the chief's ``control/``
  tree, session upload-area path is written into the records — every file in the tree is scanned, whatever its suffix, and
  each text (the raw file and every string of a decoded JSON document) is first read the way a browser or Markdown renderer
  reads it, to a fixed point: percent-encoding and HTML character references decoded, Unicode compatibility forms folded,
  invisible characters dropped, backslashes and ideographic full stops read as slashes and dots, case folded. A respelled
  link or path (another case, an explicit port or a trailing dot on the host, repeated slashes, an escape of any of these
  kinds) therefore does not evade the check; the home path is matched as a leading path segment, so the product's own
  ``/api/users/…`` routes may still be cited.

Records-only PRs touch nothing under ``backend/``, yet CI runs the backend gate on every PR, so this test runs on each record PR;
it lives under ``backend/tests/`` and therefore never triggers ``deploy-backend`` (the detector ignores that directory). The tree's
absence fails the module rather than skipping it.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

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
# The off-tree rows tabled at this commit; later records may add rows but may not drop these (the hash gate on those
# deliverables would otherwise disappear unnoticed, since completeness is checked for runtime-tree files only).
COMMITTED_OFF_TREE_ROWS = (
    "../../readiness-2026-09-21/beta/file_export_to_v1.py",
    "../../readiness-2026-09-21/beta/fixture_check.py",
    "../../readiness-2026-09-21/beta/export_operator.py",
    "../../readiness-2026-09-21/beta/OPERATOR-RUNBOOK.md",
)

# Strings that must never appear in the chief's own records (the repository is public; these belong to private stores).
# Every haystack is case-folded and percent-decoded first: host names are case-insensitive, a path in another case is the
# same path, and ``%2F`` is a slash.
# A private artifact link in either form, with or without an explicit port or a trailing dot on the host and with repeated
# slashes tolerated; the session link form (``claude.ai/code/session_…``) is not a match.
ARTIFACT_LINK = re.compile(r"claude\.ai\.?(?::\d{1,5})?/+(?:code/+)?artifact")
# The session upload area, forbidden anywhere under the chief's ``control/`` tree and in the checkpoint.
UPLOAD_AREA = ".claude/uploads"
# A home-directory path is matched as a leading path segment (nothing word-like before the slash), so the product's own
# ``/api/users/…`` routes, which a record may legitimately cite, are not caught; ``file:///Users/x``, a quoted path and a
# Windows ``C:\\Users\\x`` (read with forward slashes) are.
HOME_PATH = re.compile(r"(?<!\w)/users/")
# Unicode Default_Ignorable_Code_Point (DerivedCoreProperties.txt): characters a renderer or an IDNA mapping drops silently.
IGNORABLE = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f\u3164"
    "\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufff8\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff]"
)

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
    """Parse a ``…Z`` or ``…+00:00`` stamp, keeping any fractional seconds (a stamp without a fraction is the exact second).

    A stamp without an offset, or with a non-UTC offset, is malformed and fails here rather than being read as UTC.
    """
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    assert parsed.tzinfo is not None, f"stamp {value!r} carries no UTC offset"
    assert parsed.utcoffset() == timedelta(0), f"stamp {value!r} is not UTC"
    return parsed


def _runtime_files() -> set[Path]:
    return {p for p in RUNTIME.rglob("*") if p.is_file() and p != CHECKPOINT}


def test_runtime_tree_is_present() -> None:
    missing = [str(p.relative_to(REPO_ROOT)) for p in (RUNTIME, CONTROL, CHECKPOINT, APPOINTMENTS) if not p.exists()]
    assert not missing, f"the CODE RED runtime records are missing from the tree: {missing}"
    # Records are plain files: a symbolic link is neither hashed nor scanned, so none may exist in the tree (a link to a directory or
    # to an absent target would otherwise escape every other test while storing its target path in Git).
    links = sorted(str(p.relative_to(RUNTIME)) for p in RUNTIME.rglob("*") if p.is_symlink())
    assert not links, f"symbolic links are not permitted in the runtime tree: {links}"


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
    rows = _checkpoint_rows()
    tabled = {(RUNTIME / rel).resolve() for rel, _ in rows}
    untabled = sorted(str(p.relative_to(RUNTIME)) for p in _runtime_files() if p.resolve() not in tabled)
    assert not untabled, f"files under the runtime tree without a CHECKPOINT.md hash row: {untabled}"
    present = {rel for rel, _ in rows}
    dropped = sorted(rel for rel in COMMITTED_OFF_TREE_ROWS if rel not in present)
    assert not dropped, f"committed off-tree deliverable rows are missing from CHECKPOINT.md: {dropped}"


def test_closure_chain_is_append_only() -> None:
    present = sorted(int(CLOSURE_NAME.match(p.name).group(1)) for p in _closures())
    missing = sorted(n for n in COMMITTED_CLOSURES if n not in present)
    assert not missing, f"committed exclusion closures are missing: {missing}"
    expected = list(range(COMMITTED_CLOSURES.start, present[-1] + 1))
    assert present == expected, (
        f"exclusion closure numbers are not {expected[0]}..{expected[-1]} without gaps: "
        f"missing {sorted(set(expected) - set(present))}, unexpected {sorted(set(present) - set(expected))}"
    )
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
            assert _stamp(data["recorded_at"]) > _stamp(prev_data["recorded_at"]), (
                f"{path.name}: recorded_at is not later than {prev_path.name}'s"
            )
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


def _fold(text: str) -> str:
    """Read ``text`` the way a browser or Markdown renderer would, repeated until it no longer changes.

    Each pass decodes percent-encoding and HTML character references, folds Unicode compatibility forms (NFKC: full-width
    letters, ligatures), drops default-ignorable characters (zero-width characters, soft hyphens, variation selectors),
    reads backslashes as slashes and ideographic full stops as dots (as URL parsers and IDNA do) and folds case, so a
    nested or mixed encoding is read in full. Decoding only shortens the text and the other steps settle after one pass;
    a text still changing after 64 passes fails rather than being matched half-read.
    """
    folded = text
    for _ in range(64):
        decoded = unicodedata.normalize("NFKC", html.unescape(unquote(folded)))
        decoded = IGNORABLE.sub("", decoded).replace("\u3002", ".").replace("\\", "/").lower()
        if decoded == folded:
            return folded
        folded = decoded
    raise AssertionError(f"text did not settle after 64 decoding passes: {text[:80]!r}")


def _json_documents(path: Path, text: str) -> list[str]:
    """The JSON documents a consumer decodes from ``path``: the whole file for ``.json``, each non-blank line for ``.jsonl``."""
    if path.suffix == ".json":
        return [text]
    if path.suffix == ".jsonl":
        return [line for line in text.splitlines() if line.strip()]
    return []


def _decoded_strings(document: str) -> list[str]:
    """Every string a JSON consumer decodes from ``document`` — keys and values at any depth."""
    found: list[str] = []
    stack = [json.loads(document)]
    while stack:
        value = stack.pop()
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            stack.extend(value.keys())
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return found


def test_every_runtime_json_file_parses() -> None:
    broken = []
    for path in sorted(p for p in RUNTIME.rglob("*") if p.suffix in (".json", ".jsonl")):
        for index, document in enumerate(_json_documents(path, path.read_text(encoding="utf-8")), start=1):
            try:
                json.loads(document)
            except ValueError as exc:  # pragma: no cover - the message is the point
                where = f" line {index}" if path.suffix == ".jsonl" else ""
                broken.append(f"{path.relative_to(RUNTIME)}{where}: {exc}")
    assert not broken, f"JSON documents under the runtime tree do not parse: {broken}"


def test_records_carry_no_private_urls_or_local_machine_paths() -> None:
    offenders = []
    for path in sorted(_runtime_files() | {CHECKPOINT}):
        text = path.read_text(encoding="utf-8", errors="replace")
        # The raw text catches every file; a JSON document is scanned again after decoding, so a forbidden string spelled
        # with escapes (``\/``, ``\uXXXX``) is caught as the consumer would read it. A document that does not decode fails here
        # as well as in the parse test.
        haystacks = [
            _fold(s)
            for s in (text, *(s for document in _json_documents(path, text) for s in _decoded_strings(document)))
        ]
        if any(ARTIFACT_LINK.search(haystack) for haystack in haystacks):
            offenders.append(f"{path.relative_to(RUNTIME)}: private artifact link")
        if any(HOME_PATH.search(haystack) for haystack in haystacks):
            offenders.append(f"{path.relative_to(RUNTIME)}: home-directory path")
        if (path == CHECKPOINT or CONTROL in path.parents) and any(UPLOAD_AREA in haystack for haystack in haystacks):
            offenders.append(f"{path.relative_to(RUNTIME)}: {UPLOAD_AREA!r}")
    assert not offenders, f"private or local-machine strings in the records: {offenders}"
