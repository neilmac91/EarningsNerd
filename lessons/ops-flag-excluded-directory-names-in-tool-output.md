# In a CODE RED clone, turn on the excluded-directory output guard, record each flag as a lapse, and never read its silence as clearance

Date: 2026-10-30
Area: ops / CODE RED

**Context**: A CODE RED context (a long-running chief and its agents) must never carry the contents
of the two directories CODE RED keeps out of its agents' contexts, and treats printing either
directory's name — plain, masked, cut or truncated — as a lapse to disclose. That was a hand check:
the chief masked outputs and listed its lapses by hand. CODE RED closure 220 approved a machine gate
for it (CLAUDE.md rule 12, AGENTS.md section 4: one gate behind every "never again" rule).

**Rule**: A CODE RED session takes three steps that no gate takes for it:

1. Turn the guard on in its clone before the work starts:
   `touch "$(git rev-parse --git-common-dir)/code-red-excluded-dir-guard"`. The git common
   directory is the main checkout's `.git`, which every linked worktree shares; a worktree's own
   gitdir (`.git/worktrees/<name>`) is the wrong place and leaves the guard silently off. The marker
   is never committed, and other clones and other writers' sessions stay untouched.
2. Record each flag as a lapse, with the tool call's time, and never repeat the flagged text; record
   each "could not check" notice the same way, as a possible lapse.
3. Never read the guard's silence as clearance: it stays silent in the fail-open modes below, so the
   hand check still applies.

These steps are gated by nothing, so this lesson stays in session reading.

**Gate**: `.claude/hooks/excluded_dir_output_guard.py`, an opt-in PostToolUse / PostToolUseFailure
hook (`backend/tests/unit/test_excluded_dir_output_guard.py`), inspects a tool result after the tool
runs and states, factually, when the result carries a form of either excluded directory's name:
plain, per-digit or whole-token date-masked, or a cut or truncated form that spans a name junction,
is at least eight characters long after normalisation (an escaped slash counts as one character, a
mask token as its own characters, however long the date it stands for) and has clean ends. A '/' at
a name segment start, an ASCII `...` run and any non-path character (a Unicode ellipsis included)
count as clean borders, at the date's masked digits too: a dotted year reads as masked digits while a
truncation marker or an elision anywhere in the date still ends a cut, and an ellipsis that stands
for the whole date reads as the date and ends a cut after it. So the dated parent with a dotted or
elided date is flagged even in a sibling path, by design. It is a detector, not a filter: it leaves
the result unchanged and never echoes the matched text. It acts only when the marker sits in the git common
directory of the clone that holds the event's `cwd` OR of the clone that `$CLAUDE_PROJECT_DIR` names
(either suffices). It never scans `tool_input` (the CODE RED git commands carry the names as
exclusion pathspecs). Its flag, and its "could not check" notice for an input it cannot parse, reach
Claude as `additionalContext` and the user as `systemMessage` on both events: the registration
passes the event (`--event PostToolUse`, `--event PostToolUseFailure`), so the hook knows it even
when the input is unreadable.

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
