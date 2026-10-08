"""Machine gates for the agent-workflow rules of #1118 (CLAUDE.md rule 12).

Five prose rules from AGENTS.md §5 and §7 would otherwise rot:

- ``tasks/todo.md`` is one page of open items, never a dated ledger again (§7). The old file grew
  to 6,406 lines because every session prepended a ``## <date> — …`` section.
- Every ``agent(`` call in ``.claude/workflows/*.js`` names its ``model`` in its options object
  with one of the aliases ``sonnet``, ``opus`` or ``haiku`` or a tier key the script defines (§5),
  and every tier of the review script names a lens model and, when it refutes, a refuter model, so
  no review stage inherits the session's premium model, names it by its full ID, or runs on
  ``undefined``.
- Workflow scripts validate their inputs before ``pipeline()``/``parallel()`` (a throw inside a
  stage, inline or in a stage function bound by name, is a silent drop) and never count a missing
  vote as a refutation (``lessons/ops-validate-workflow-inputs-before-pipeline.md``). These text
  checks catch the recorded shapes only, so every script must also have a behavioural spec under
  ``frontend/tests/unit/`` that loads it (``premergeReviewWorkflow.spec.ts`` runs the review script
  with stubbed agents and asserts what each stage actually receives); a second script is never
  guarded by the regexes alone.
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
MONTH = (
    r"(January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?"
)
DATE = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}\s+{MONTH}\s+\d{{4}}\b|\b{MONTH}\s+\d{{1,2}}\b",
    re.IGNORECASE,
)
HEADING = re.compile(r"^ {0,3}#{1,6}\s")
SETEXT_UNDERLINE = re.compile(r"^ {0,3}(=+|-+)\s*$")
# One of the three aliases AGENTS.md §5 names, quoted, or the tier key the review script binds as
# `const T = TIERS[...]`. A full model ID is refused on purpose: the aliases cannot spell the premium
# session model, so a stage cannot be pinned to it by name either (the same set as
# `frontend/tests/unit/premergeReviewWorkflow.spec.ts` allows).
MODEL_ALIAS = "(sonnet|opus|haiku)"
MODEL_VALUE = re.compile(rf"^(?:'{MODEL_ALIAS}'|\"{MODEL_ALIAS}\"|T\.(lensModel|refuterModel))$")
TIER_BINDING = re.compile(r"\bconst T = TIERS\[")
MODEL_LITERAL = re.compile(rf"'{MODEL_ALIAS}'")
# The vote-counting bug shape: a `.length` guard (bare, `> 0`, `>= 1`, `!== 0`, parenthesised or
# not, on the array, an optional chain or a `.filter(…)` of it) joined by `&&` or `?` to an
# `.every(` or `!….some(`, in either order, means a missing vote silently counts as a refutation.
# Whitespace may span lines; a `.filter(…)` may hold one level of nested parentheses.
_ARR = r"[\w.?]+(?:\.filter\((?:[^()]|\([^()]*\))*\))?"
_LENGTH_GUARD = rf"\(?\s*{_ARR}\.length\s*(?:>\s*0|>=\s*1|!==?\s*0)?\s*\)?"
_ALL_VOTES = rf"!?\s*{_ARR}\.(?:every|some)\("
MISSING_VOTE_IS_REFUTATION = re.compile(
    rf"{_LENGTH_GUARD}\s*(?:&&|\?)\s*{_ALL_VOTES}|{_ALL_VOTES}.*?\)\s*&&\s*{_LENGTH_GUARD}(?!\s*=)"
)
SPECS = ROOT / "frontend" / "tests" / "unit"
# `- file.md — rule` or the older link form `- [`file.md`](./file.md) — rule`.
INDEX_ENTRY = re.compile(r"^- (?:\[`?)?(archive/)?([a-z0-9-]+\.md)(?:`?\]\([^)]*\))?\s+—\s", re.MULTILINE)
# Council files committed before the rule (AGENTS.md §7), pinned to their blob hashes: each may
# stay unchanged, move (a same-content rename, as the `tasks/` retention proposal would do) or be
# deleted (no test edit needed; a stale entry may be removed at leisure), never grow a new
# deliberation. The set only shrinks.
EXISTING_TRANSCRIPTS = {
    TRANSCRIPTS + "council-2026-06-28-q2-moat.md": "52999e16463a49bf1fb4dbf5b89658d45ddac0f5",
    TRANSCRIPTS + "council-transcript-2026-06-28-q3-pricing.md": "6e757761061fa3229f1db62912f8256bbb08525a",
    TRANSCRIPTS + "council-transcript-2026-06-28-q4-beta-scope.md": "80754636095c5cf440be4310ded61d74743e93ac",
    TRANSCRIPTS + "council-transcript-2026-06-28-q5-distribution.md": "1e246498440e29ca59a3920a120a68a17ce1b2b3",
    TRANSCRIPTS + "council-transcript-2026-06-28-q6-fundraising.md": "886ce79d4fcd6ead43df6603329bebd7cfcf2ae9",
    TRANSCRIPTS + "council-transcript-2026-06-28-q7-dormant-features.md": "30f8013f91c1a6edece216ea8dc2c60ffb13ce82",
    "tasks/council-prep.md": "ff41f8caebbc7db62b9b239cbb29bc282b0bb63d",
}
# Either naming style the frozen set itself uses, in any text format.
COUNCIL_FILE = re.compile(r"(^|/)council-[^/]*\.(md|txt|json)$")


def test_todo_is_one_page_of_open_items():
    lines = TODO.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= TODO_MAX_LINES, (
        f"tasks/todo.md has {len(lines)} lines; it is the open-items page, not the ledger "
        "(AGENTS.md §7 — closed items leave the file, history goes to tasks/archive/)"
    )
    headings, fenced = [], False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and HEADING.match(line):
            headings.append(line.lstrip())
        elif (not fenced and line.strip() and not line.lstrip().startswith(("-", "*", "#"))
              and i + 1 < len(lines) and SETEXT_UNDERLINE.match(lines[i + 1])):
            headings.append("## " + line.strip())  # a setext heading counts like an ATX one
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
    parts, depth, quote, start, skip = [], 0, None, 0, False
    for i, ch in enumerate(args):
        if skip:
            skip = False
            continue
        if quote:
            if ch == "\\":
                skip = True
            elif ch == quote:
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
    for match in re.finditer(r"(?<![\w.])agent\s*\(", source):
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
    """True when the call's last argument is an object literal whose top-level ``model`` value is a
    quoted alias or a tier key the script defines (``T.lensModel`` / ``T.refuterModel``), so a
    misspelled key cannot evaluate to ``undefined`` and inherit the session model."""
    args = _split_top_level(call)
    if len(args) < 2 or not args[-1].startswith("{"):
        return False
    body = args[-1][1:].rsplit("}", 1)[0]
    values = [m.group(1) for m in (re.match(r"^\s*model\s*:\s*(.+?)\s*$", e, re.DOTALL) for e in _split_top_level(body)) if m]
    # A JavaScript object literal keeps the LAST duplicate key, so every `model` entry must be sound.
    return bool(values) and all(MODEL_VALUE.match(v) for v in values)


def test_every_workflow_agent_call_names_its_model():
    scripts = sorted(WORKFLOWS.glob("*.js"))
    assert scripts, f"no workflow scripts under {WORKFLOWS}"
    unnamed = []
    for script in scripts:
        source = _strip_comments(script.read_text(encoding="utf-8"))
        calls = list(_agent_calls(source))
        assert calls, f"{script.name} has no agent() call"
        if any("T." in c for c in calls):
            assert TIER_BINDING.search(source), f"{script.name} uses T.<model> without `const T = TIERS[...]`"
        unnamed += [f"{script.name}: agent({c[:60]}…" for c in calls if not _options_name_a_model(c)]
    assert not unnamed, (
        "workflow agent() calls whose options do not name a model inherit the session's premium "
        f"model (AGENTS.md §5): {unnamed}"
    )


def _balanced(source: str, start: int, open_ch: str = "{", close_ch: str = "}") -> str:
    """The text between the bracket at ``start`` and its match, strings and templates respected."""
    depth, quote, i = 0, None, start
    while i < len(source):
        ch = source[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return source[start + 1 : i]
        i += 1
    raise AssertionError("unbalanced brackets")


def test_review_tiers_name_lens_and_refuter_models():
    source = _strip_comments((WORKFLOWS / "premerge-review.js").read_text(encoding="utf-8"))
    head = re.search(r"const TIERS = \{", source)
    assert head, "premerge-review.js must define `const TIERS = {...}`"
    block = _balanced(source, head.end() - 1)
    entries = []
    for raw in _split_top_level(block):
        match = re.match(r"^\s*(\w+)\s*:\s*\{(.*)\}\s*$", raw, re.DOTALL)
        assert match, f"TIERS entry is not `name: {{...}}`: {raw[:60]!r}"
        entries.append((match.group(1), match.group(2)))
    assert {e[0] for e in entries} >= {"records", "routine", "high"}, [e[0] for e in entries]
    problems = []
    for name, body in entries:
        if not re.search(r"\blensModel\s*:\s*" + MODEL_LITERAL.pattern, body):
            problems.append(f"{name}: no literal lensModel")
        refuters = re.search(r"\brefuters\s*:\s*(\d+)", body)
        if not refuters:
            problems.append(f"{name}: no numeric refuters count")
        elif int(refuters.group(1)) > 0 and not re.search(r"\brefuterModel\s*:\s*" + MODEL_LITERAL.pattern, body):
            problems.append(f"{name}: refuters > 0 without a literal refuterModel")
    assert not problems, f"review tiers would run an agent on an undefined model: {problems}"


def _call_bodies(source: str, name: str):
    for match in re.finditer(rf"(?<![\w.]){name}\s*\(", source):
        yield _balanced(source, match.end() - 1, "(", ")")


def _stage_bodies(source: str, call_body: str):
    """The call's inline text plus the body of every stage it passes by name (an arrow function or
    a `function` bound to that name; one level, the shape the lesson records)."""
    yield call_body
    for arg in _split_top_level(call_body):
        if not re.fullmatch(r"\w+", arg):
            continue
        for match in re.finditer(
            rf"(?:\b(?:const|let|var)\s+{arg}\s*=\s*(?:async\s*)?(?:(?:\([^)]*\)|\w+)\s*=>|function\s*\([^)]*\))\s*"
            rf"|\b(?:async\s+)?function\s+{arg}\s*\([^)]*\)\s*)",
            source,
        ):
            rest = source[match.end():]
            yield _balanced(source, match.end()) if rest.startswith("{") else rest.split("\n", 1)[0]


def test_workflow_scripts_validate_before_pipeline_and_count_every_vote():
    # The shapes the gate must see (and the sound shapes it must not flag), so a widening is checked.
    for shape in (
        "v.length > 0 && v.every(", "(v.length > 0) && v.every(", "v.length > 0 ? v.every(x) : false",
        "v.length > 0 && v.filter(Boolean).every(", "votes.filter(Boolean).length > 0 && votes.filter(Boolean).every(",
        "votes.filter((x) => x).length > 0 && votes.every(", "v?.length > 0 && v.every(",
        "v.every((x) => !x.refuted) && v.length > 0", "v.length > 0 && !v.some((x) => x.refuted)",
        "v.length && v.every(", "v.length\n  >= 1 && v.every(", "v.length !== 0 && v.every(",
    ):
        assert MISSING_VOTE_IS_REFUTATION.search(shape), shape
    for shape in (
        "complete && v.every(", "v.length === T.refuters && v.every(", "v.length === 2 && v.every(",
        "v.every((x) => !x.refuted) && v.length === T.refuters",
    ):
        assert not MISSING_VOTE_IS_REFUTATION.search(shape), shape
    for probe in (
        "const stage = async (pr) => { if (!TIERS[pr.tier]) throw new Error('x') }\nawait pipeline(PRS, stage)\n",
        "const stage = async function (pr) { throw new Error('x') }\nawait pipeline(PRS, stage)\n",
        "async function stage(pr) { throw new Error('x') }\nawait parallel(PRS.map((p) => () => stage(p)))\nawait pipeline(PRS, stage)\n",
    ):
        assert any(re.search(r"\bthrow\b", t) for b in _call_bodies(probe, "pipeline") for t in _stage_bodies(probe, b)), probe
    problems = []
    for script in sorted(WORKFLOWS.glob("*.js")):
        source = _strip_comments(script.read_text(encoding="utf-8"))
        for name in ("pipeline", "parallel"):
            for body in _call_bodies(source, name):
                if any(re.search(r"\bthrow\b", text) for text in _stage_bodies(source, body)):
                    problems.append(f"{script.name}: `throw` inside a {name}() stage is a silent drop; validate before the call")
        if MISSING_VOTE_IS_REFUTATION.search(source):
            problems.append(f"{script.name}: `.length > 0 && ….every(` counts a missing vote as a refutation; require the expected count")
    assert not problems, "\n".join(problems)


def _spec_reads(spec_source: str, script_name: str) -> bool:
    """True when the spec names the script's path in code (not a comment) and reads a file."""
    code = _strip_comments(spec_source)
    return bool(re.search(rf"['\"`][^'\"`\n]*\.claude/workflows/{re.escape(script_name)}['\"`]", code)) and bool(
        re.search(r"\breadFile(?:Sync)?\s*\(", code)
    )


def test_every_workflow_script_has_a_behavioural_spec():
    # The same files vitest runs: tests/unit/**/*.spec.ts?(x).
    specs = [p.read_text(encoding="utf-8") for ext in ("*.spec.ts", "*.spec.tsx") for p in SPECS.rglob(ext)]
    assert not _spec_reads(" * see .claude/workflows/premerge-review.js\nreadFileSync(x)", "premerge-review.js")
    assert _spec_reads("const S = path.join(root, '.claude/workflows/premerge-review.js')\nreadFileSync(S)", "premerge-review.js")
    missing = [s.name for s in sorted(WORKFLOWS.glob("*.js")) if not any(_spec_reads(text, s.name) for text in specs)]
    assert not missing, (
        "every workflow script needs a spec under frontend/tests/unit/ that loads it and runs it with "
        f"stubbed agent/pipeline/parallel (the text checks above catch recorded shapes only): {missing}"
    )


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


def _tracked_blobs() -> dict[str, str]:
    # Tracked and staged paths with their blob hashes: a transcript added or edited but not yet
    # committed is caught too.
    out = subprocess.run(["git", "ls-files", "-s", "-z"], cwd=ROOT, capture_output=True, check=True)  # noqa: S603, S607
    blobs = {}
    for record in out.stdout.decode().split("\0"):
        if record:
            meta, path = record.split("\t", 1)
            blobs[path] = meta.split()[1]
    return blobs


def test_no_new_or_grown_council_transcripts_in_the_repository():
    blobs = _tracked_blobs()
    # Keyed by content, not path: every file in the transcripts folder and every council-named file
    # anywhere must carry a pinned blob. A new file or an edit is a new blob; a rename is not.
    pinned = set(EXISTING_TRANSCRIPTS.values())
    council = sorted(p for p in blobs if p.startswith(TRANSCRIPTS) or COUNCIL_FILE.search(p))
    unpinned = [p for p in council if blobs[p] not in pinned]
    assert not unpinned, (
        "founder deliberations never enter this public repository (AGENTS.md §7); the llm-council "
        f"skill writes to ~/.claude/earningsnerd/council/. New or edited: {unpinned}"
    )
