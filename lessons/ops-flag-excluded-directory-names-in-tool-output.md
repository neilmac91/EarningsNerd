# Flag a CODE RED-excluded directory name in a tool result, opt-in, to surface leaks for disclosure

Date: 2026-10-30
Area: ops / CODE RED

**Context**: A CODE RED context (a long-running chief and its agents) must never carry the contents
of the two directories CODE RED keeps out of its agents' contexts, and treats printing either
directory's name — plain, masked, cut or truncated — as a lapse to disclose. That was a hand check:
the chief masked outputs and listed its lapses by hand. CODE RED closure 220 approved a machine gate
for it (CLAUDE.md rule 12, AGENTS.md section 4: one gate behind every "never again" rule).

**Rule**: The opt-in PostToolUse / PostToolUseFailure hook
`.claude/hooks/excluded_dir_output_guard.py` inspects a tool result after the tool runs and states,
factually, when the result carries a form of either excluded directory's name (plain, per-digit or
whole-token date-masked, or a cut/truncated form spanning a name junction with clean ends — a '/'
at a name segment start and an ASCII or Unicode ellipsis count as clean borders). It is a detector,
not a filter: it leaves the result unchanged and never echoes the matched text. It does anything
only when the marker file `code-red-excluded-dir-guard` exists in the git common directory of the
clone that holds the event's `cwd` OR of the clone that `$CLAUDE_PROJECT_DIR` names (create it
inside `.git`, so it is never committed and other clones and other writers' sessions stay
untouched). It never scans `tool_input` (the CODE RED git commands carry the names as exclusion
pathspecs).

It surfaces leaks; it does not guarantee catching every one. Fail-open modes, where it stays silent:
not opted in; a session that loads no repository hooks (a multi-repo cloud session, an untrusted
folder, `disableAllHooks` — as `ops-name-codex-without-its-at-mention.md` notes for the sibling
hook); and a run where Claude Code cancels the command at its ~10 s timeout and discards the output.
It is a detector only: it does not mask or replace the result (containment), does not see a
subagent's hand-back message or a workflow's completion notice (text that reaches the chief outside
a tool result), and does not pre-empt a command that would read either directory. Two further limits
its header states: whether a workflow agent's tool calls fire settings hooks is undocumented, and a
running session may not pick up a changed `.claude/settings.json` until it restarts. The exclusion
itself is a CODE RED rule only — AGENTS.md and CLAUDE.md do not carry it, and other writers may work
in those directories.

**Evidence**: `.claude/hooks/excluded_dir_output_guard.py`; gate
`backend/tests/unit/test_excluded_dir_output_guard.py`; CODE RED closure 220.
