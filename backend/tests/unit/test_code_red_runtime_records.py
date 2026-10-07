"""Gate for the CODE RED runtime records under ``tasks/code-red-20261004/runtime/`` (CLAUDE.md rule 12).

Every record PR's independent reviewer re-derived the same invariants by hand before merge. This test derives them in CI so
a broken record never reaches a reviewer:

* every file under the runtime tree is UTF-8 text without NUL bytes, so every other check reads what a consumer reads;
* ``CHECKPOINT.md`` opens with its ``# `` header line, which carries exactly one ``(updated …)`` stamp and no markup, and
  writes its deliverables and decisions headings once each: any other line that reads as either title (another heading
  level or spelling, a setext title, a fenced or commented copy) fails, so the section checked is the one a reader sees;
* every row of the deliverables table carries a well-formed SHA-256 and names, in canonical form and without crossing a
  symbolic link, a distinct file whose digest equals it; no hash row sits outside that section; every file under the
  runtime tree has a row (the checkpoint is the durable index of the records); the off-tree deliverable rows tabled at this
  commit stay tabled; and the tree holds no symbolic links;
* the ``control/source-context-exclusion-N.json`` closures form an append-only chain anchored to the committed tail
  (closures 136–164 present, closure 164 pinned by digest), canonically named and numbered without gaps through the newest:
  each one's ``prior_record`` hash equals the previous file, its ``recorded_at`` is later than its predecessor's, its counts
  are integers equal to its lists, the previous ids are a prefix, nothing is duplicated, and the new entries are the ones
  it declares;
* the checkpoint header and ``APPOINTMENTS.json`` are stamped no earlier than the newest closure, compared at the closure's
  fractional precision (they are written last); every stamp compared has the form ``YYYY-MM-DDTHH:MM:SS[.ffffff]``
  followed by ``Z`` or ``+00:00`` (any other form, a missing offset included, is malformed and never repaired);
* every non-blank line of the decisions section is a numbered entry and the numbers run contiguously from 1;
* every JSON file (``.json``) parses, and so does every line of a JSON-lines file (``.jsonl``, ``.ndjson``), suffixes
  matched in any case; a duplicate member name or a non-standard ``NaN``/``Infinity`` constant is an error;
* no private artifact link, home-directory path (``/Users/``) or, anywhere under the chief's ``control/`` tree, session
  upload-area path is written into the records. Every file is scanned, whatever its suffix: its raw text and every string
  of each JSON document it holds (the whole file, or any single line), each read as written and again with HTML comments,
  tags and emphasis markers removed, and each reading folded the way a browser or Markdown renderer reads it (``_fold``).
  A respelled link or path therefore does not evade the check. The home path is matched as a leading path segment or
  after a macOS volume prefix, so the product's own ``/api/users/…`` routes may still be cited.

Records-only PRs touch nothing under ``backend/``, yet CI runs the backend gate on every PR, so this test runs on each record PR;
it lives under ``backend/tests/`` and therefore never triggers ``deploy-backend`` (the detector ignores that directory). The tree's
absence fails the module rather than skipping it.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import posixpath
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME = REPO_ROOT / "tasks" / "code-red-20261004" / "runtime"
CONTROL = RUNTIME / "control"
CHECKPOINT = RUNTIME / "CHECKPOINT.md"
APPOINTMENTS = CONTROL / "APPOINTMENTS.json"

# Markdown line endings (CommonMark): LF, CRLF or CR. Other Unicode separators (U+2028, U+0085, form feed) end no line.
LINE_END = re.compile(r"\r\n|\r|\n")
# Every body row of the deliverables table must parse as | `path` | `digest` |, and its digest is then validated, so a
# malformed or unbackticked row fails instead of being dropped.
TABLE_ROW = re.compile(r"^\| `([^`]+)` \| `([^`]*)` \|")
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
# A hash row anywhere else in the checkpoint (indented, or with an upper-case digest) would be shown but never verified.
STRAY_HASH_ROW = re.compile(r"^[ \t]*\| `[^`]+` \| `[0-9a-fA-F]{64}` \|")
# The one stamp form the records use: whole or fractional (to the microsecond) seconds, then ``Z`` or ``+00:00``.
STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", re.ASCII)
HEADER_STAMP = re.compile(r"\(updated ([^)]*)\)")
CLOSURE_PREFIX = "source-context-exclusion"
CLOSURE_NAME = re.compile(r"source-context-exclusion-([1-9][0-9]*)\.json", re.ASCII)
DELIVERABLES_HEADING = "## Deliverables and exact hashes (SHA-256)"
DECISIONS_HEADING = "## Decisions taken by the chief"
# Every non-blank line of the decisions section is one entry of the form ``N. text`` (a malformed entry fails, not vanishes);
# the number is a CommonMark ordered-list marker (one to nine ASCII digits).
DECISION_LINE = re.compile(r"^([0-9]{1,9})\. \S")
# JSON suffixes, matched in any case: True for one document per line.
JSON_SUFFIXES = {".json": False, ".jsonl": True, ".ndjson": True}
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
# Each pattern runs over folded readings (``_fold``): lower case, decoded, slash runs collapsed to one slash.
# A private artifact link: a claude.ai address, with or without a port or a trailing dot on the host, whose path names an
# artifact by any route (dot segments included). The session link (``claude.ai/code/session_…``) and the artifact gallery
# page (``claude.ai/code/artifacts``) are not matches. Tabs and line breaks are removed first, as URL parsers remove them.
ARTIFACT_LINK = re.compile(r"claude\.ai\.?(?::\d*)?/[^\s\"'<>`|]*?artifact(?!s(?![/\w]))")
URL_WHITESPACE = re.compile(r"[\t\n\r]")
# A home-directory path is matched as a leading path segment (nothing word-like before the slash), so the product's own
# ``/api/users/…`` routes, which a record may legitimately cite, are not caught; ``file:///Users/x``, a quoted path and a
# Windows ``C:\\Users\\x`` (read with forward slashes) are, and so is a home path behind a macOS volume prefix.
HOME_PATH = re.compile(r"(?<!\w)/users/|(?:file:/[^/\s]*|/system/volumes/data|/volumes/[^/\n]+)/users/")
# The session upload area, forbidden anywhere under the chief's ``control/`` tree and in the checkpoint (dot segments allowed).
UPLOAD_AREA = re.compile(r"\.claude/(?:\./|\.\./|(?!\.\.?/)[^/\s]+/\.\./)*uploads")
# Unicode Default_Ignorable_Code_Point (DerivedCoreProperties.txt): characters a renderer or an IDNA mapping drops silently.
IGNORABLE = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f\u3164"
    "\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufff8\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff]"
)
JSON_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")
# A Markdown backslash escape (CommonMark: a backslash before ASCII punctuation shows the punctuation alone).
MARKDOWN_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
SLASH_RUN = re.compile(r"/{2,}")
# What a renderer hides or consumes around visible text: HTML comments, HTML tags and emphasis or code-span markers.
MARKUP = re.compile(r"<!--.*?-->|</?[a-z][a-z0-9-]*(?:[\s/][^<>]*)?>|[*_~`]", re.IGNORECASE | re.DOTALL)

# The tree is a durable record: its absence is a failure, never a skip (a PR that deleted or renamed it would otherwise stay
# green). The closure chain is anchored to its committed tail so no suffix of the chain can be removed.
COMMITTED_CLOSURES = range(136, 165)
COMMITTED_TAIL = (
    "source-context-exclusion-164.json",
    "3e486add2a9c136d8b434a3544bb1fb6a9c4287a82bda5e88def112582802eec",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(path: Path) -> str:
    """A record's text, decoded as strict UTF-8 (a NUL byte or an undecodable byte fails, naming the file)."""
    data = path.read_bytes()
    where = path.relative_to(RUNTIME)
    assert b"\x00" not in data, f"{where}: contains NUL bytes (records are UTF-8 text)"
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(f"{where}: is not UTF-8 text ({exc.reason} at byte {exc.start})") from None


def _unique_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    repeated = sorted(name for name, count in Counter(name for name, _ in pairs).items() if count > 1)
    if repeated:
        raise ValueError(f"duplicate member names {repeated}")
    return dict(pairs)


def _reject_constant(name: str) -> object:
    raise ValueError(f"non-standard constant {name}")


def _strict_json(document: str) -> object:
    """Decode one JSON document strictly: a duplicate member name or a ``NaN``/``Infinity`` constant is an error."""
    return json.loads(document, object_pairs_hook=_unique_members, parse_constant=_reject_constant)


def _load_object(path: Path) -> dict:
    """A control file's JSON object, decoded strictly; anything else fails, naming the file."""
    try:
        data = _strict_json(_text(path))
    except (ValueError, RecursionError) as exc:
        raise AssertionError(f"{path.relative_to(RUNTIME)}: does not parse as JSON ({exc})") from None
    assert isinstance(data, dict), f"{path.relative_to(RUNTIME)}: is not a JSON object"
    return data


def _checkpoint_lines() -> list[str]:
    return LINE_END.split(_text(CHECKPOINT))


def _title_key(text: str) -> str:
    """``text`` reduced to its folded words, so every spelling or rendering of a heading's title compares equal."""
    return " ".join(re.findall(r"[0-9a-z]+", _fold(text)))


def _section(lines: list[str], heading: str) -> tuple[int, int]:
    """The ``[start, end)`` line range of one ``## `` section, from its heading line to the next ``## `` heading.

    The title is written once: any other line that reads as it (a heading at another level or with other punctuation, a
    setext title, a fenced or commented copy) fails, so the section checked is the one a reader sees.
    """
    key = _title_key(heading)
    copies = [index for index, line in enumerate(lines) if _title_key(line) == key]
    assert len(copies) == 1 and lines[copies[0]].rstrip(" \t") == heading, (
        f"CHECKPOINT.md must write {heading!r} once, as that heading line; lines reading as it: "
        f"{[lines[index] for index in copies]}"
    )
    start = copies[0]
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    return start, end


def _checkpoint_rows() -> list[tuple[str, str]]:
    """Every body row of the deliverables table, each required to parse and to carry a well-formed digest."""
    lines = _checkpoint_lines()
    start, end = _section(lines, DELIVERABLES_HEADING)
    stray = [line for index, line in enumerate(lines) if not start <= index < end and STRAY_HASH_ROW.match(line)]
    assert not stray, f"hash rows outside the deliverables section, never verified: {stray}"
    table_lines = [line for line in lines[start + 1 : end] if line.strip(" \t")]
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
    """The closure files in chain order; an entry named like a closure but not canonically (case, suffix, zeros) fails."""
    named = [path for path in CONTROL.iterdir() if _fold(path.name).startswith(CLOSURE_PREFIX)]
    near_misses = sorted(path.name for path in named if not CLOSURE_NAME.fullmatch(path.name))
    assert not near_misses, (
        f"control/ entries named like closures but not 'source-context-exclusion-N.json': {near_misses}"
    )
    return sorted(named, key=lambda path: int(CLOSURE_NAME.fullmatch(path.name).group(1)))


def _stamp(value: object, source: str) -> datetime:
    """Parse a ``YYYY-MM-DDTHH:MM:SS[.ffffff]`` stamp ending ``Z`` or ``+00:00`` (without a fraction, the exact second).

    Any other form (a missing or non-UTC offset, a seconds offset, more than six fraction digits, a missing value) is
    malformed and fails here, naming ``source``, rather than being read as UTC.
    """
    assert isinstance(value, str) and STAMP.fullmatch(value), (
        f"{source}: {value!r} is not a stamp of the form YYYY-MM-DDTHH:MM:SS[.ffffff] followed by Z or +00:00"
    )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AssertionError(f"{source}: {value!r} is not a valid date and time ({exc})") from None


def _member(data: dict, key: str, kind: type, where: str, *, optional: bool = False):
    """``data[key]``, required to be exactly ``kind`` (an optional member may be absent or null: then it is empty)."""
    value = data.get(key)
    if optional and value is None:
        return kind()
    assert type(value) is kind, f"{where}: {key} is {type(value).__name__}, expected {kind.__name__}"
    return value


def _runtime_files() -> set[Path]:
    return {p for p in RUNTIME.rglob("*") if p.is_file() and p != CHECKPOINT}


def test_runtime_tree_is_present() -> None:
    missing = [str(p.relative_to(REPO_ROOT)) for p in (RUNTIME, CONTROL, CHECKPOINT, APPOINTMENTS) if not p.exists()]
    assert not missing, f"the CODE RED runtime records are missing from the tree: {missing}"
    # Records are plain files: a symbolic link is neither hashed nor scanned, so none may exist in the tree (a link to a directory or
    # to an absent target would otherwise escape every other test while storing its target path in Git).
    links = sorted(str(p.relative_to(RUNTIME)) for p in RUNTIME.rglob("*") if p.is_symlink())
    assert not links, f"symbolic links are not permitted in the runtime tree: {links}"


def test_every_record_is_utf8_text() -> None:
    unreadable = []
    for path in sorted(_runtime_files() | {CHECKPOINT}):
        try:
            _text(path)
        except AssertionError as exc:
            unreadable.append(str(exc))
    assert not unreadable, f"records that are not UTF-8 text: {unreadable}"


def test_checkpoint_hash_rows_match_their_files() -> None:
    rows = _checkpoint_rows()
    assert rows, "CHECKPOINT.md has no hash rows"
    # A row names its file in canonical form (no '.' or '..' inside it, no repeated or trailing slash, no backslash), so a
    # respelled duplicate cannot pass; the duplicate check then compares the files the rows resolve to.
    noncanonical = [rel for rel, _ in rows if rel != posixpath.normpath(rel) or "\\" in rel]
    assert not noncanonical, f"hash-row paths that are not in canonical form: {noncanonical}"
    targets = Counter((RUNTIME / rel).resolve() for rel, _ in rows)
    duplicated = sorted(rel for rel, _ in rows if targets[(RUNTIME / rel).resolve()] > 1)
    assert not duplicated, f"hash rows naming the same file: {duplicated}"
    crossing = []
    mismatched = []
    missing = []
    escaped = []
    for rel, recorded in rows:
        target = (RUNTIME / rel).resolve()
        if Path(os.path.normpath(RUNTIME / rel)) != target:
            crossing.append(rel)
        elif not (target.is_relative_to(RUNTIME) or any(target.is_relative_to(root) for root in ALLOWED_OFF_TREE)):
            escaped.append(rel)
        elif not target.is_file():
            missing.append(rel)
        elif _sha256(target) != recorded:
            mismatched.append(rel)
    assert not crossing, f"hash rows that reach their file through a symbolic link: {crossing}"
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
    closures = _closures()
    present = [int(CLOSURE_NAME.fullmatch(p.name).group(1)) for p in closures]
    missing = sorted(n for n in COMMITTED_CLOSURES if n not in present)
    assert not missing, f"committed exclusion closures are missing: {missing}"
    expected = list(range(COMMITTED_CLOSURES.start, present[-1] + 1))
    assert present == expected, (
        f"exclusion closure numbers are not {expected[0]}..{expected[-1]} without gaps: "
        f"missing {sorted(set(expected) - set(present))}, unexpected {sorted(set(present) - set(expected))}"
    )
    tail_name, tail_sha = COMMITTED_TAIL
    assert _sha256(CONTROL / tail_name) == tail_sha, f"{tail_name} no longer has its committed digest"
    assert len(closures) >= 2, "expected at least two exclusion closures"
    previous: tuple[Path, str, dict] | None = None
    for path in closures:
        data = _load_object(path)
        ids = _member(data, "excluded_context_ids", list, path.name)
        assert all(type(i) is str for i in ids), f"{path.name}: excluded_context_ids holds a non-string id"
        assert len(ids) == len(set(ids)), f"{path.name}: duplicate context ids"
        count = _member(data, "exclusion_count", int, path.name)
        assert count == len(ids), f"{path.name}: exclusion_count {count} != {len(ids)} ids"
        recorded_at = _stamp(data.get("recorded_at"), f"{path.name} recorded_at")
        if previous is not None:
            prev_path, prev_sha, prev_data = previous
            prior = _member(data, "prior_record", dict, path.name)
            assert prior.get("path") == f"control/{prev_path.name}", (
                f"{path.name}: prior_record.path is {prior.get('path')}"
            )
            assert prior.get("sha256") == prev_sha, f"{path.name}: prior_record.sha256 does not equal {prev_path.name}"
            assert recorded_at > _stamp(prev_data.get("recorded_at"), f"{prev_path.name} recorded_at"), (
                f"{path.name}: recorded_at is not later than {prev_path.name}'s"
            )
            prev_ids = prev_data["excluded_context_ids"]
            previous_count = _member(data, "previous_count", int, path.name)
            assert previous_count == len(prev_ids), f"{path.name}: previous_count != len({prev_path.name} ids)"
            assert ids[: len(prev_ids)] == prev_ids, f"{path.name}: the previous closure's ids are not a prefix"
            assert data.get("all_previous_entries_preserved") is True, (
                f"{path.name}: all_previous_entries_preserved is not true"
            )
            declared = _member(data, "new_actual_contexts", list, path.name, optional=True) + _member(
                data, "new_provisional_contexts", list, path.name, optional=True
            )
            assert sorted(declared) == sorted(ids[len(prev_ids) :]), (
                f"{path.name}: declared new contexts != appended ids"
            )
            roles = _member(data, "new_context_roles", dict, path.name, optional=True)
            assert sorted(roles) == sorted(declared), f"{path.name}: new_context_roles keys != new ids"
            resolved = _member(data, "provisional_labels_resolved", dict, path.name, optional=True)
            unknown = sorted(label for label in resolved if label not in prev_ids)
            assert not unknown, f"{path.name}: resolves labels never registered: {unknown}"
        previous = (path, _sha256(path), data)


def test_checkpoint_and_appointments_are_stamped_after_the_newest_closure() -> None:
    newest_path = _closures()[-1]
    closure_stamp = _stamp(_load_object(newest_path).get("recorded_at"), f"{newest_path.name} recorded_at")
    header = _checkpoint_lines()[0]
    stamps = HEADER_STAMP.findall(header)
    assert header.startswith("# ") and "<" not in header and len(stamps) == 1, (
        f"CHECKPOINT.md's first line must be its '# ' header, without markup, carrying one '(updated …)' stamp: {header!r}"
    )
    assert _stamp(stamps[0], "CHECKPOINT.md header") >= closure_stamp, (
        "CHECKPOINT.md is stamped earlier than the newest closure"
    )
    appointments = _load_object(APPOINTMENTS)
    assert _stamp(appointments.get("updated_at"), "APPOINTMENTS.json updated_at") >= closure_stamp, (
        "APPOINTMENTS.json is stamped earlier than the newest closure"
    )


def test_decisions_are_numbered_contiguously() -> None:
    lines = _checkpoint_lines()
    start, end = _section(lines, DECISIONS_HEADING)
    entries = [line for line in lines[start + 1 : end] if line.strip(" \t")]
    malformed = [line for line in entries if not DECISION_LINE.match(line)]
    assert not malformed, f"decisions section lines that are not numbered entries: {malformed}"
    numbers = [int(match.group(1)) for match in map(DECISION_LINE.match, entries) if match]
    assert numbers, "no numbered decisions found"
    assert numbers == list(range(1, len(numbers) + 1)), f"decision numbering is not 1..{len(numbers)}: {numbers}"


def _fold(text: str) -> str:
    """Read ``text`` the way a browser or Markdown renderer would, repeated until it no longer changes.

    Each pass decodes percent-encoding, HTML character references and JSON ``\\uXXXX`` escapes, folds Unicode compatibility
    forms (NFKC: full-width letters, ligatures), drops default-ignorable characters (zero-width characters, soft hyphens,
    variation selectors), removes Markdown backslash escapes, reads the remaining backslashes as slashes and ideographic full
    stops as dots (as URL parsers and IDNA do), collapses slash runs to one slash and folds case, so a nested or mixed
    encoding is read in full. Decoding only shortens the text and the other steps settle after one pass; a text still
    changing after 64 passes fails rather than being matched half-read.
    """
    folded = text
    for _ in range(64):
        decoded = JSON_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), html.unescape(unquote(folded)))
        decoded = IGNORABLE.sub("", unicodedata.normalize("NFKC", decoded))
        decoded = MARKDOWN_ESCAPE.sub(r"\1", decoded).replace("\\", "/").replace("\u3002", ".")
        decoded = SLASH_RUN.sub("/", decoded).lower()
        if decoded == folded:
            return folded
        folded = decoded
    raise AssertionError(f"text did not settle after 64 decoding passes: {text[:80]!r}")


def _readings(source: str) -> list[str]:
    """``source`` folded as written and with the markup a renderer hides or consumes removed."""
    return [_fold(source), _fold(MARKUP.sub("", source))]


def _json_documents(path: Path, text: str) -> list[tuple[str, str]]:
    """The documents a JSON consumer decodes from ``path`` by its suffix: the whole file, or each non-blank line.

    JSON-lines are split at ``\\n`` only (a raw U+2028 inside a string is still one line) and a line is blank only when
    it holds nothing but JSON whitespace.
    """
    per_line = JSON_SUFFIXES.get(path.suffix.lower())
    if per_line is None:
        return []
    if not per_line:
        return [("", text)]
    return [(f" line {n}", line) for n, line in enumerate(text.split("\n"), start=1) if line.strip(" \t\r")]


def _json_strings(text: str) -> list[str]:
    """Every string a JSON consumer could decode from ``text``, whatever the file's suffix.

    The whole text and each of its lines is tried as a JSON document; from each that decodes, every key and value at any
    depth is collected, with every occurrence of a repeated member name kept.
    """
    found: list[str] = []
    for candidate in (text, *text.split("\n")):
        try:
            stack = [json.loads(candidate, object_pairs_hook=lambda pairs: [item for pair in pairs for item in pair])]
        except (ValueError, RecursionError):
            continue
        while stack:
            value = stack.pop()
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, list):
                stack.extend(value)
    return found


def test_every_runtime_json_file_parses() -> None:
    broken = []
    for path in sorted(_runtime_files()):
        if path.suffix.lower() not in JSON_SUFFIXES:
            continue
        for where, document in _json_documents(path, _text(path)):
            try:
                _strict_json(document)
            except (ValueError, RecursionError) as exc:  # pragma: no cover - the message is the point
                broken.append(f"{path.relative_to(RUNTIME)}{where}: {exc}")
    assert not broken, f"JSON documents under the runtime tree do not parse: {broken}"


def test_records_carry_no_private_urls_or_local_machine_paths() -> None:
    offenders = []
    for path in sorted(_runtime_files() | {CHECKPOINT}):
        text = _text(path)
        readings = [reading for source in (text, *_json_strings(text)) for reading in _readings(source)]
        if any(ARTIFACT_LINK.search(URL_WHITESPACE.sub("", reading)) for reading in readings):
            offenders.append(f"{path.relative_to(RUNTIME)}: private artifact link")
        if any(HOME_PATH.search(reading) for reading in readings):
            offenders.append(f"{path.relative_to(RUNTIME)}: home-directory path")
        if (path == CHECKPOINT or CONTROL in path.parents) and any(UPLOAD_AREA.search(reading) for reading in readings):
            offenders.append(f"{path.relative_to(RUNTIME)}: session upload area")
    assert not offenders, f"private or local-machine strings in the records: {offenders}"
