"""Machine gates for the agent-workflow rules of #1118 (CLAUDE.md rule 12).

Three prose rules from AGENTS.md §5 and §7 would otherwise rot:

- ``tasks/todo.md`` is one page of open items, never a dated ledger again (§7). The old file grew
  to 6,406 lines because every session prepended a ``## <date> — …`` section.
- Every ``agent(`` call in ``.claude/workflows/*.js`` names its ``model`` (§5), so no review
  stage inherits the session's premium model.
- ``lessons/README.md`` lists every lesson exactly once and nothing that does not exist, so a
  lesson cannot fall out of session reading by accident.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TODO = ROOT / "tasks" / "todo.md"
WORKFLOWS = ROOT / ".claude" / "workflows"
LESSONS = ROOT / "lessons"

TODO_MAX_LINES = 120
# The only section headings the open-items file may carry (AGENTS.md §7).
TODO_SECTIONS = ("Where things stand — ", "Open items", "What to doubt first")
# A ledger entry: a dated or month-named heading at any level.
LEDGER_HEADING = re.compile(
    r"^#{1,6}\s+(\d{4}-\d{2}-\d{2}\b|(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2}\b)",
    re.MULTILINE,
)
INDEX_ENTRY = re.compile(r"^- (archive/)?([a-z0-9-]+\.md) — ", re.MULTILINE)


def test_todo_is_one_page_of_open_items():
    text = TODO.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) <= TODO_MAX_LINES, (
        f"tasks/todo.md has {len(lines)} lines; it is the open-items page, not the ledger "
        "(AGENTS.md §7 — closed items leave the file, history goes to tasks/archive/)"
    )
    headings = [line[3:].strip() for line in lines if line.startswith("## ")]
    stray = [h for h in headings if not h.startswith(TODO_SECTIONS)]
    assert not stray, f"tasks/todo.md carries sections outside the open-items format: {stray}"
    dated = LEDGER_HEADING.findall(text)
    assert not dated, f"tasks/todo.md has ledger-style dated entries: {[d[0] for d in dated]}"


def _agent_calls(source: str):
    """Yield the text of every ``agent(`` call, tracking strings and template literals."""
    for match in re.finditer(r"(?<![\w.])agent\(", source):
        i = match.end()
        depth, quote = 1, None
        start = i
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


def test_every_workflow_agent_call_names_its_model():
    scripts = sorted(WORKFLOWS.glob("*.js"))
    assert scripts, f"no workflow scripts under {WORKFLOWS}"
    unnamed = []
    for script in scripts:
        calls = list(_agent_calls(script.read_text(encoding="utf-8")))
        assert calls, f"{script.name} has no agent() call"
        for call in calls:
            if not re.search(r"\bmodel\s*:", call):
                unnamed.append(f"{script.name}: agent({call[:60]}…")
    assert not unnamed, "workflow agent() calls without a model: inherit the session's premium " \
        f"model (AGENTS.md §5): {unnamed}"


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
