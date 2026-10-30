# Flag a CODE RED-excluded directory name in any tool result, opt-in, so no leak goes unnoticed

Date: 2026-10-30
Area: ops / CODE RED

**Context**: A CODE RED context (a long-running chief and its agents) must never carry the contents
of the two directories CODE RED keeps out of its agents' contexts, and treats printing either
directory's name — plain, masked, cut or truncated — as a lapse to disclose. That was a hand check:
the chief masked outputs and listed its lapses by hand. CODE RED closure 220 approved a machine gate
for it (CLAUDE.md rule 12, AGENTS.md section 4: one gate behind every "never again" rule).

**Rule**: The opt-in PostToolUse / PostToolUseFailure hook
`.claude/hooks/excluded_dir_output_guard.py` inspects a tool result after the tool runs and states,
factually, when the result carries a form of either excluded directory's name (plain, date-masked,
or a cut/truncated form spanning a name junction). It is a detector, not a filter: it leaves the
result unchanged and never echoes the matched text. It does anything only when the marker file
`code-red-excluded-dir-guard` exists in the git common directory of the clone that holds the event's
`cwd` (create it inside `.git`, so it is never committed and other clones and other writers'
sessions stay untouched); it is silent for everyone else. It never scans `tool_input` (the CODE RED
git commands carry the names as exclusion pathspecs). Its limits, which it does not cover: it does
not mask or replace the result (containment), does not see a subagent's hand-back message or a
workflow's completion notice (text that reaches the chief outside a tool result), and does not
pre-empt a command that would read either directory. The exclusion itself is a CODE RED rule only —
AGENTS.md and CLAUDE.md do not carry it, and other writers may work in those directories.

**Evidence**: `.claude/hooks/excluded_dir_output_guard.py`; gate
`backend/tests/unit/test_excluded_dir_output_guard.py`; CODE RED closure 220.
