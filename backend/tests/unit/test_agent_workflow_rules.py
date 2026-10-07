"""Machine gates for the agent-workflow rules of #1118 (CLAUDE.md rule 12).

Four prose rules from AGENTS.md §5 and §7 would otherwise rot:

- ``tasks/todo.md`` is one page of open items, never a dated ledger again (§7). The old file grew
  to 6,406 lines because every session prepended a ``## <date> — …`` section.
- Every ``agent(`` call in ``.claude/workflows/*.js`` names its ``model`` in its options object
  (§5), and every tier of the review script names a lens model and, when it refutes, a refuter
  model, so no review stage inherits the session's premium model.
- ``lessons/README.md`` lists every lesson exactly once and nothing that does not exist, so a
  lesson cannot fall out of session reading by accident.
- Founder deliberations never enter this public repository (§7): no new file under
  ``.claude/council-transcripts/`` and no council transcript anywhere else in the tree.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TODO = ROOT / "tasks" / "todo.md"
WORKFLOWS = ROOT / ".claude" / "workflows"
LESSONS = ROOT / "lessons"
TRANSCRIPTS = ".claude/council-transcripts/"

TODO_MAX_LINES = 120
TODO_TITLE = "# Open items — EarningsNerd"
# The only sections the open-items file may carry, each exactly once (AGENTS.md §7). The first
# one carries the date of the last refresh; a second copy is a ledger entry, not a refresh.
TODO_SECTIONS = ("Where things stand — ", "Open items", "What to doubt first")
# A date in any form a ledger entry has used: ISO, "7 October 2026", "October 7", "Oct 7".
DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b"
    r"|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b",
    re.IGNORECASE,
)
INDEX_ENTRY = re.compile(r"^- (archive/)?([a-z0-9-]+\.md) — ", re.MULTILINE)
# Transcripts committed before the rule (AGENTS.md §7); the set only shrinks.
EXISTING_TRANSCRIPTS = frozenset(
    TRANSCRIPTS + name
    for name in (
        "council-2026-06-28-q2-moat.md",
        "council-transcript-2026-06-28-q3-pricing.md",
        "council-transcript-2026-06-28-q4-beta-scope.md",
        "council-transcript-2026-06-28-q5-distribution.md",
        "council-transcript-2026-06-28-q6-fundraising.md",
        "council-transcript-2026-06-28-q7-dormant-features.md",
    )
)


def test_todo_is_one_page_of_open_items():
    lines = TODO.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= TODO_MAX_LINES, (
        f"tasks/todo.md has {len(lines)} lines; it is the open-items page, not the ledger "
        "(AGENTS.md §7 — closed items leave the file, history goes to tasks/archive/)"
    )
    headings = [line for line in lines if line.startswith("#")]
    assert headings and headings[0] == TODO_TITLE, f"tasks/todo.md must start with '{TODO_TITLE}'"
    sections = [h[3:].strip() for h in headings[1:] if h.startswith("## ")]
    others = [h for h in headings[1:] if not h.startswith("## ")]
    assert not others, f"tasks/todo.md allows only '## ' sections; found: {others}"
    for name in TODO_SECTIONS:
        count = sum(1 for s in sections if s.startswith(name))
        assert count == 1, f"tasks/todo.md must carry '{name}' exactly once, found {count}"
    stray = [s for s in sections if not s.startswith(TODO_SECTIONS)]
    assert not stray, f"tasks/todo.md carries sections outside the open-items format: {stray}"
    dated = [h for h in headings if DATE.search(h) and not h.startswith("## " + TODO_SECTIONS[0])]
    assert not dated, f"tasks/todo.md has ledger-style dated headings: {dated}"


def _strip_comments(source: str) -> str:
    """Blank out // and /* */ comments outside strings and template literals, keeping offsets."""
    out, i, quote = [], 0, None
    while i < len(source):
        ch = source[i]
        if quote:
            out.append(ch)
            if ch == "\\":
                out.append(source[i + 1] if i + 1 < len(source) else "")
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
            out.append(ch)
        elif source.startswith("//", i):
            end = source.find("\n", i)
            end = len(source) if end == -1 else end
            out.append(" " * (end - i))
            i = end - 1
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = len(source) if end == -1 else end + 2
            out.append(" " * (end - i))
            i = end - 1
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _split_top_level(args: str) -> list[str]:
    """Split an argument list on commas at depth zero, outside strings and template literals."""
    parts, depth, quote, start = [], 0, None, 0
    for i, ch in enumerate(args):
        if quote:
            if ch == "\\":
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(args[start:i])
            start = i + 1
    parts.append(args[start:])
    return [p.strip() for p in parts if p.strip()]


def _agent_calls(source: str):
    """Yield the argument text of every ``agent(`` call, comments removed, strings respected."""
    source = _strip_comments(source)
    for match in re.finditer(r"(?<![\w.])agent\(", source):
        i = match.end()
        depth, quote, start = 1, None, i
        while i < len(source) and depth:
            ch = source[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "'\"`":
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        yield source[start : i - 1]


def _options_name_a_model(call: str) -> bool:
    """True when the call's last argument is an object literal with a top-level ``model`` key."""
    args = _split_top_level(call)
    if len(args) < 2 or not args[-1].startswith("{"):
        return False
    body = args[-1][1:].rsplit("}", 1)[0]
    return any(re.match(r"^\s*(\.\.\.)?\s*model\s*:", entry) for entry in _split_top_level(body))


def test_every_workflow_agent_call_names_its_model():
    scripts = sorted(WORKFLOWS.glob("*.js"))
    assert scripts, f"no workflow scripts under {WORKFLOWS}"
    unnamed = []
    for script in scripts:
        calls = list(_agent_calls(script.read_text(encoding="utf-8")))
        assert calls, f"{script.name} has no agent() call"
        unnamed += [f"{script.name}: agent({c[:60]}…" for c in calls if not _options_name_a_model(c)]
    assert not unnamed, (
        "workflow agent() calls whose options do not name a model inherit the session's premium "
        f"model (AGENTS.md §5): {unnamed}"
    )


def test_review_tiers_name_lens_and_refuter_models():
    source = _strip_comments((WORKFLOWS / "premerge-review.js").read_text(encoding="utf-8"))
    tiers = re.search(r"const TIERS = \{(.*?)\n\}", source, re.DOTALL)
    assert tiers, "premerge-review.js must define `const TIERS = {...}` on its own lines"
    entries = re.findall(r"^\s*(\w+):\s*\{(.*?)\},?\s*$", tiers.group(1), re.MULTILINE)
    assert len(entries) >= 3, f"expected records/routine/high tiers, found {[e[0] for e in entries]}"
    problems = []
    for name, body in entries:
        if not re.search(r"\blensModel\s*:\s*'(sonnet|opus|haiku|claude-[\w.-]+)'", body):
            problems.append(f"{name}: no literal lensModel")
        refuters = re.search(r"\brefuters\s*:\s*(\d+)", body)
        if refuters and int(refuters.group(1)) > 0 and not re.search(
            r"\brefuterModel\s*:\s*'(sonnet|opus|haiku|claude-[\w.-]+)'", body
        ):
            problems.append(f"{name}: refuters > 0 without a literal refuterModel")
    assert not problems, f"review tiers would run an agent on an undefined model: {problems}"


def test_lessons_index_lists_every_lesson_exactly_once():
    index = (LESSONS / "README.md").read_text(encoding="utf-8")
    listed = [f"{'archive/' if prefix else ''}{name}" for prefix, name in INDEX_ENTRY.findall(index)]
    files = sorted(
        [p.name for p in LESSONS.glob("*.md") if p.name != "README.md"]
        + [f"archive/{p.name}" for p in (LESSONS / "archive").glob("*.md")]
    )
    duplicates = sorted({name for name in listed if listed.count(name) > 1})
    assert not duplicates, f"lessons/README.md lists these more than once: {duplicates}"
    unlisted = sorted(set(files) - set(listed))
    assert not unlisted, f"lessons not in lessons/README.md: {unlisted}"
    ghosts = sorted(set(listed) - set(files))
    assert not ghosts, f"lessons/README.md lists files that do not exist: {ghosts}"


def _tracked_files() -> list[str]:
    # Tracked and staged paths: a transcript added but not yet committed is caught too.
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)  # noqa: S603, S607
    return [p for p in out.stdout.decode().split("\0") if p]


def test_no_new_council_transcripts_in_the_repository():
    tracked = _tracked_files()
    new_in_folder = sorted(p for p in tracked if p.startswith(TRANSCRIPTS) and p not in EXISTING_TRANSCRIPTS)
    elsewhere = sorted(
        p for p in tracked
        if not p.startswith(TRANSCRIPTS) and re.search(r"(^|/)council-transcript[^/]*\.md$", p)
    )
    assert not new_in_folder and not elsewhere, (
        "founder deliberations never enter this public repository (AGENTS.md §7); the llm-council "
        f"skill writes to ~/.claude/earningsnerd/council/. New transcripts: {new_in_folder + elsewhere}"
    )
    gone = sorted(EXISTING_TRANSCRIPTS - set(tracked))
    if gone:
        raise AssertionError(f"remove these from EXISTING_TRANSCRIPTS, the set only shrinks: {gone}")
