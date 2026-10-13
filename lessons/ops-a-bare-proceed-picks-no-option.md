# Read a bare "proceed" as the founder's last instruction, not a pick of your recommended option; ask before an outward step when they differ

Date: 2026-10-13 · Area: ops / working style

**Context.** A records PR (#1287) was green, and the founder had written "proceed when ready" about merging it. Codex then flagged the report under `AGENTS.md` §7. The agent put a two-option decision to the founder: keep the report out of the repository (recommended) or merge it anyway. The founder replied "proceed". The agent read that as the recommended option, closed the PR and posted on it that the founder had chosen to keep the report out. The founder had meant merge ("wait, i meant merge it, not close it"). The PR had to be reopened and the public comment corrected.

**Rule.** A reply that names no option does not choose one. When a decision with options is pending and the founder answers with a bare "proceed", "ok" or "go", read it as continuing the founder's own last instruction on that work, not as accepting the agent's recommendation. If the two point at different options, ask in one line which option is meant before any step that changes state outside the session (closing, merging, commenting, publishing or deleting). Reversible preparation inside the session, such as readying both outcomes, may continue meanwhile. No machine gate is possible, because the rule governs how a chat reply is read.

**Evidence.** PR #1287: closed 2026-10-13 19:26 UTC on the misread and reopened 19:34 UTC after the correction. It was then squash-merged as `65000ec` with the founder's approval as an exception to `AGENTS.md` §7. The correction is recorded on the PR's Codex review thread.
