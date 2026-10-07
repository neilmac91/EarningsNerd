"""Gate for the CODE RED runtime records under ``tasks/code-red-20261004/runtime/`` (CLAUDE.md rule 12).

Every record PR's independent reviewer re-derived the same invariants by hand before merge. This test derives them in CI so
a broken record never reaches a reviewer:

* every file under the runtime tree is UTF-8 text without NUL bytes, named in plain text (no invisible characters, no
  compatibility forms), so every other check reads what a consumer reads;
* ``CHECKPOINT.md`` (a leading byte-order mark aside) holds no HTML comment and no HTML heading, its first line is exactly
  ``# <title> (updated <stamp>)`` with no markup characters in the title, and its deliverables and decisions headings are
  each the only heading carrying that title (ATX at any level or setext, also inside a list item or a block quote), so the
  section checked is the one a reader sees under it (a renamed section is no longer that section);
* every row of the deliverables table carries a well-formed SHA-256 and names a distinct file, by its plain relative path
  (no ``.`` or ``..`` detour, repeated slash, absolute path or symbolic link), whose digest equals it; no other line of the
  checkpoint, the table's header included, pairs a table pipe with a 64-hex digest; every file under the runtime tree has a
  row (the checkpoint is the durable index of the records); the off-tree deliverable rows tabled at this commit stay
  tabled; and the tree holds no symbolic links;
* every ``control/`` entry named like a closure (case and punctuation aside) is a closure file named
  ``source-context-exclusion-N.json``, and the closures form an append-only chain anchored to the committed tail (closures
  136–164 present, closure 164 pinned by digest) and numbered without gaps through the newest: each one's ``prior_record``
  hash equals the previous file, its ``recorded_at`` is later than its predecessor's, its counts are integers equal to its
  lists, its ids are strings, the previous ids are a prefix, nothing is duplicated, and the new entries are the ones it
  declares;
* the checkpoint header and ``APPOINTMENTS.json`` are stamped no earlier than the newest closure, compared at the closure's
  fractional precision (they are written last); every stamp compared has the form ``YYYY-MM-DDTHH:MM:SS[.ffffff]``
  followed by ``Z`` or ``+00:00`` (any other form, a missing offset included, is malformed and never repaired);
* every non-blank line of the decisions section is a numbered entry and the numbers run contiguously from 1;
* every JSON file (``.json``) parses, and so does every line of a JSON-lines file (``.jsonl``, ``.ndjson``), suffixes
  matched in any case; a duplicate member name or a non-standard ``NaN``/``Infinity`` constant is an error;
* the records carry no claude.ai address other than the session link (``claude.ai/code/session_<id>``, ending there),
  so no private artifact link and no artifact gallery link by any route; no home-directory path (``/Users/…`` as a leading
  path segment, behind a ``file:``, ``smb:``, ``afp:``, ``nfs:`` or ``vscode:`` host, or under a ``/Volumes/<name>/``
  prefix; the product's own ``/api/users/…`` routes may still be cited); and, under the chief's ``control/`` tree and in
  the checkpoint, no session upload-area path (an ``uploads`` segment under ``.claude/``). Every file is scanned, whatever
  its suffix, as written and with HTML comments, tags and emphasis or code-span markers removed, each folded by ``_fold``
  once reading backslashes as path separators (for the paths) and once decoding JSON and Markdown escapes (for the paths
  and the address). A match in any reading fails. The gate guards against leaks, not a hostile writer: the name
  ``claude.ai`` alone in prose, an address split by whitespace, look-alike letters, a volume name containing a space and
  drive-form or container home paths such as ``/c/Users`` are outside it.

Records-only PRs touch nothing under ``backend/``, yet CI runs the backend gate on every PR, so this test runs on each record PR;
it lives under ``backend/tests/`` and therefore never triggers ``deploy-backend`` (the detector ignores that directory). The tree's
absence fails the module rather than skipping it.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
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
# The checkpoint's first line: a level-1 heading whose title has no markup characters, then exactly one stamp.
HEADER_LINE = re.compile(r"# [^\[\]()<>`*_&\\|#~]+ \(updated ([^()\s]+)\)[ \t]*")
# CommonMark headings, read inside list items and block quotes too (their markers and any indentation are stripped first):
# an ATX line (one to six #, optional closing #s), or a paragraph of one or more lines underlined with = or -. A list
# item's marker starts a new paragraph.
CONTAINER_MARKERS = re.compile(r"(?:[ \t]*(?:>|[-*+](?=[ \t])|[0-9]{1,9}[.)](?=[ \t])))*[ \t]*")
LIST_ITEM_START = re.compile(r"(?:[ \t]*>)*[ \t]*(?:[-*+]|[0-9]{1,9}[.)])(?=[ \t])")
ATX_HEADING = re.compile(r"#{1,6}(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*")
SETEXT_UNDERLINE = re.compile(r"(?:=+|-+)[ \t]*")
HTML_HEADING = re.compile(r"<[ \t]*/?[ \t]*h[1-6]\b", re.IGNORECASE)
# Every body row of the deliverables table must parse as | `path` | `digest` |, and its digest is then validated, so a
# malformed or unbackticked row fails instead of being dropped.
TABLE_ROW = re.compile(r"^\| `([^`]+)` \| `([^`]*)` \|")
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
# A 64-hex digest in either case; on a line with a table pipe outside the deliverables section it is a hash row that would
# be shown but never verified.
HEX64 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
# The one stamp form the records use: whole or fractional (to the microsecond) seconds, then ``Z`` or ``+00:00``.
STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", re.ASCII)
# Closure names: a control/ entry whose name, folded to lower-case letters and digits, starts with this key is a closure.
CLOSURE_KEY = "sourcecontextexclusion"
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
# Each pattern runs over the folded readings of ``_readings`` (lower case, decoded); slash runs and dot segments are
# tolerated inside a path, every path segment matched is non-empty (no backtracking over a run of slashes), and a path is
# followed for at most 64 segments, so each scan stays linear in the text.
# A claude.ai address that is not the session link: the host (a trailing dot or a port allowed) followed by a slash or a
# backslash and anything but ``code/session_<id>`` ending there. Every artifact and gallery route, dot segments, ports and
# escapes included, is therefore an offender, while the name alone in prose ("a private claude.ai artifact") is not.
PRIVATE_LINK = re.compile(r"claude\.ai\.?(?::\d*)?[/\\](?!code/session_[0-9a-z]+(?![0-9a-z_/?#%&=+-]|\.\w))")
# A home-directory path: ``/Users/`` as a leading path segment (nothing word-like before the slash, so the product's own
# ``/api/users/…`` routes may be cited; a ``file:///Users/x`` URL and a Windows ``C:\\Users\\x`` path, read with forward
# slashes, are leading segments), behind a ``file:``, ``smb:``, ``afp:``, ``nfs:`` or ``vscode:`` host, or under a macOS
# volume prefix whose segments hold no whitespace or prose punctuation (so a volume mentioned in a sentence or a table cell
# next to an ``/api/users/…`` route is not read as one path).
HOME_PATH = re.compile(
    r"(?<!\w)/users/"
    r"|(?<![\w+.-])(?:file|smb|afp|nfs|vscode)://[^/\s]+/+users/"
    r"|(?<!\w)/(?:system/+)?volumes/+(?:[^/\s|\"'`;,()<>]+/+){1,64}?users/"
)
# The session upload area: an ``uploads`` segment anywhere under ``.claude/``.
UPLOAD_AREA = re.compile(r"\.claude/+(?:[^/\s]+/+){0,64}?uploads(?![\w-])")
# Unicode Default_Ignorable_Code_Point (DerivedCoreProperties.txt): characters a renderer or an IDNA mapping drops silently.
IGNORABLE = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f\u3164"
    "\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufff8\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff]"
)
# Escapes: a backslash before a slash or a backslash (consumed when backslashes are read as separators), a JSON escape, and
# a Markdown backslash escape (CommonMark: a backslash before ASCII punctuation shows the punctuation alone).
SLASH_ESCAPE = re.compile(r"\\([\\/])")
JSON_ESCAPE = re.compile(r"\\(?:u([0-9a-fA-F]{4})|([\"\\/bfnrt]))")
JSON_SIMPLE_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
MARKDOWN_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
# What a renderer hides or consumes around visible text: HTML comments (an unclosed one hides the rest of the text), HTML
# tags, and emphasis, strikethrough or code-span markers (not the underscore, which is part of names and ids and is not
# emphasis inside a word).
MARKUP = re.compile(r"<!--.*?(?:-->|\Z)|</?[a-z][a-z0-9-]*(?:[\s/][^<>]*)?>|[*~`]", re.IGNORECASE | re.DOTALL)

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
    return LINE_END.split(_text(CHECKPOINT).removeprefix("\ufeff"))


def _heading_titles(lines: list[str]) -> list[tuple[int, str]]:
    """``(first line index, title)`` for every ATX or setext heading of ``lines``, inside list items and block quotes too.

    A setext title is the whole paragraph above its underline, its lines joined by single spaces.
    """
    content = [line[CONTAINER_MARKERS.match(line).end() :] for line in lines]
    titles = []
    for index, text in enumerate(content):
        atx = ATX_HEADING.fullmatch(text)
        if atx:
            titles.append((index, (atx.group(1) or "").strip(" \t")))
        elif (
            SETEXT_UNDERLINE.fullmatch(text)
            and index
            and content[index - 1].strip(" \t")
            and not ATX_HEADING.fullmatch(content[index - 1])
        ):
            first = index - 1
            while (
                first
                and not LIST_ITEM_START.match(lines[first])
                and content[first - 1].strip(" \t")
                and not ATX_HEADING.fullmatch(content[first - 1])
            ):
                first -= 1
            titles.append((first, " ".join(part.strip(" \t") for part in content[first:index])))
    return titles


def _section(lines: list[str], heading: str) -> tuple[int, int]:
    """The ``[start, end)`` line range of one ``## `` section, from its heading line to the next ``## `` heading.

    Nothing in the checkpoint may sit in an HTML comment or an HTML heading, and the heading's title is carried by that one
    heading line only (another heading level, a setext title, a heading in a list item or a block quote, or a copy in a code
    block fails), so the section checked is the one a reader sees.
    """
    assert not any("<!--" in line or HTML_HEADING.search(line) for line in lines), (
        "CHECKPOINT.md holds an HTML comment or an HTML heading"
    )
    title = heading.removeprefix("## ")
    copies = [index for index, text in _heading_titles(lines) if text == title]
    assert len(copies) == 1 and lines[copies[0]].rstrip(" \t") == heading, (
        f"CHECKPOINT.md must carry the title {title!r} on exactly one heading line, {heading!r}; heading lines with it: "
        f"{[lines[index] for index in copies]}"
    )
    start = copies[0]
    end = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    return start, end


def _checkpoint_rows() -> list[tuple[str, str]]:
    """Every body row of the deliverables table, each required to parse and to carry a well-formed digest."""
    lines = _checkpoint_lines()
    start, end = _section(lines, DELIVERABLES_HEADING)
    stray = [
        line for index, line in enumerate(lines) if not start <= index < end and "|" in line and HEX64.search(line)
    ]
    assert not stray, f"hash rows outside the deliverables section, never verified: {stray}"
    table_lines = [line for line in lines[start + 1 : end] if line.strip(" \t")]
    assert len(table_lines) >= 3, "the deliverables table has no body rows"
    _header, _separator, *body = table_lines
    assert _header.startswith("|") and not TABLE_ROW.match(_header) and not HEX64.search(_header), (
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
    """The closure files in chain order; an entry named like a closure but not exactly (case, suffix, zeros, punctuation,
    a directory) fails."""
    named = [
        path
        for path in CONTROL.iterdir()
        if re.sub(r"[^0-9a-z]", "", unicodedata.normalize("NFKC", path.name).lower()).startswith(CLOSURE_KEY)
    ]
    near_misses = sorted(path.name for path in named if not (CLOSURE_NAME.fullmatch(path.name) and path.is_file()))
    assert not near_misses, (
        f"control/ entries named like closures but not 'source-context-exclusion-N.json' files: {near_misses}"
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
    # Names are plain text, so no two records can look alike while differing in an invisible or compatibility character.
    names = [p.relative_to(RUNTIME).as_posix() for p in RUNTIME.rglob("*")]
    unplain = sorted(n for n in names if IGNORABLE.search(n) or unicodedata.normalize("NFKC", n) != n)
    assert not unplain, f"runtime-tree names with invisible characters or compatibility forms: {unplain}"


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
    repeated = sorted(rel for rel, count in Counter(rel for rel, _ in rows).items() if count > 1)
    assert not repeated, f"duplicate hash-row paths: {repeated}"
    escaped = []
    indirect = []
    missing = []
    mismatched = []
    for rel, recorded in rows:
        target = (RUNTIME / rel).resolve()
        if not (target.is_relative_to(RUNTIME) or any(target.is_relative_to(root) for root in ALLOWED_OFF_TREE)):
            escaped.append(rel)
        elif rel != Path(os.path.relpath(target, RUNTIME)).as_posix():
            indirect.append(rel)
        elif not target.is_file():
            missing.append(rel)
        elif _sha256(target) != recorded:
            mismatched.append(rel)
    assert not escaped, f"hash rows escape the permitted trees: {escaped}"
    # A row names its file by its plain relative path, so two rows naming one file are always caught as duplicates.
    assert not indirect, (
        "hash rows that do not name their file by its plain relative path (a '.' or '..' detour, a repeated slash, an "
        f"absolute path or a symbolic link): {indirect}"
    )
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
    gaps = [f"{low + 1}..{high - 1}" for low, high in zip(present, present[1:]) if high != low + 1]
    assert present[0] == COMMITTED_CLOSURES.start and not gaps, (
        f"exclusion closure numbers do not run {COMMITTED_CLOSURES.start}..{present[-1]} without gaps: "
        f"they start at {present[0]} and miss {gaps}"
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
            assert all(type(i) is str for i in declared), f"{path.name}: a declared new context is not a string"
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
    first_line = _checkpoint_lines()[0]
    header = HEADER_LINE.fullmatch(first_line)
    assert header, (
        "CHECKPOINT.md's first line must be '# <title> (updated <stamp>)', the title without markup characters: "
        f"{first_line!r}"
    )
    assert _stamp(header.group(1), "CHECKPOINT.md header") >= closure_stamp, (
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


def _decode_json_escapes(text: str) -> str:
    decoded = JSON_ESCAPE.sub(
        lambda match: chr(int(match.group(1), 16)) if match.group(1) else JSON_SIMPLE_ESCAPES[match.group(2)], text
    )
    # A surrogate pair spelled as two escapes is one character; a lone surrogate is unreadable.
    return decoded.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def _fold(text: str, *, escapes: bool) -> str:
    """Read ``text`` the way a browser or Markdown renderer would, repeated until it no longer changes.

    Each pass decodes percent-encoding and HTML character references, then either reads backslashes as path separators
    (``escapes=False``: a backslash before a slash or a backslash is consumed first, so ``\\/`` is one slash and ``\\\\`` one
    separator) or decodes JSON escapes and removes Markdown backslash escapes (``escapes=True``: backslashes otherwise
    kept), then folds Unicode compatibility forms (NFKC: full-width letters, ligatures), drops default-ignorable characters
    (zero-width characters, soft hyphens, variation selectors), reads ideographic full stops as dots (as IDNA does) and
    folds case, so a nested or mixed encoding is read in full. Decoding only shortens the text and the other steps settle
    after one pass; a text still changing after 64 passes fails rather than being matched half-read.
    """
    folded = text
    for _ in range(64):
        decoded = html.unescape(unquote(folded))
        if escapes:
            decoded = MARKDOWN_ESCAPE.sub(r"\1", _decode_json_escapes(decoded))
        else:
            decoded = SLASH_ESCAPE.sub(r"\1", decoded).replace("\\", "/")
        decoded = IGNORABLE.sub("", unicodedata.normalize("NFKC", decoded)).replace("\u3002", ".").lower()
        if decoded == folded:
            return folded
        folded = decoded
    raise AssertionError(f"text did not settle after 64 decoding passes: {text[:80]!r}")


def _readings(text: str) -> tuple[set[str], set[str]]:
    """``text`` as written and with the markup a renderer hides or consumes removed, folded with backslashes read as path
    separators (the first set) and with escapes decoded (the second)."""
    sources = (text, MARKUP.sub("", text))
    return {_fold(source, escapes=False) for source in sources}, {_fold(source, escapes=True) for source in sources}


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
        as_paths, decoded = _readings(_text(path))
        readings = as_paths | decoded
        # The address check reads escapes decoded: read as separators, a backslash after a session link (a Markdown hard
        # line break, a JSON line-break escape) would look like a path; an address written with backslashes still fails.
        if any(PRIVATE_LINK.search(reading) for reading in decoded):
            offenders.append(f"{path.relative_to(RUNTIME)}: claude.ai address other than the session link")
        if any(HOME_PATH.search(reading) for reading in readings):
            offenders.append(f"{path.relative_to(RUNTIME)}: home-directory path")
        if (path == CHECKPOINT or CONTROL in path.parents) and any(UPLOAD_AREA.search(reading) for reading in readings):
            offenders.append(f"{path.relative_to(RUNTIME)}: session upload area")
    assert not offenders, f"private or local-machine strings in the records: {offenders}"
