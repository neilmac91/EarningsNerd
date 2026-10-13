# Read a bare "proceed" as the founder's last instruction on that work; your recommendation counts only when there is none

Date: 2026-10-13 · Area: ops / working style

**Context.** A records PR (#1287) was green, and the founder had written "proceed when ready"
about merging it. Codex then flagged the report under `AGENTS.md` §7. The agent put a two-option
decision to the founder: keep the report out of the repository (recommended) or merge it anyway.
The founder replied "proceed". The agent read that as the recommended option, closed the PR and
posted on it that the founder had chosen to keep the report out. The founder had meant merge
("wait, i meant merge it, not close it"). The PR was reopened, and a correcting reply was posted
under that comment.

**Rule.** A reply that names no option ("proceed", "ok", "go") continues the founder's last
instruction on that work, even when you have since recommended something else. Act on that
instruction without asking again: a second question is not one of the pauses `AGENTS.md` §3
allows. Only when the founder gave no earlier instruction on that work does the reply accept the
option you recommended.

**Evidence.** PR #1287 was closed on the misread at 2026-10-13 19:26:57Z. It was reopened at
19:34:23Z, after the founder's correction in chat, and the agent's correcting reply is on the
PR's Codex review thread (19:34:53Z). It was squash-merged as `65000ec`. That commit's message
records the founder's approval as an exception to `AGENTS.md` §7 and says it is not a precedent
for other strategy or pricing documents. Codex's review of this lesson's first version (#1313)
found that asking again would add a pause §3 does not list. No machine gate is possible, because
the rule governs how a chat reply is read.
