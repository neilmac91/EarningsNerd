# A review you triggered is a review you wait for — merging inside it discards what you asked for

Date: 2026-09-14   Area: ops

**Context**: On #856 I marked the PR ready for review at 18:19:34, which is the action that
triggers Codex in this repo. Codex began reviewing at 18:19:39. I merged at 18:19:45 — six
seconds into the review I had just requested, and before any finding could exist.

Codex posted its finding at 18:23:03, four minutes after the merge: a P1 on the handover
document itself. The document told the next agent to read `eslint.config.mjs:83-86` for the
warning that flat-config overrides REPLACE rather than merge `no-restricted-syntax` options.
That warning is at `:155-160`. A
handover whose explicit pointer sends the reader to the wrong invariant is worse than one that
says nothing, and it had already landed on main.

The same reviewer had found three real defects on #853 one day earlier, every one a genuine
bug. The evidence that the review was worth waiting for was a day old and mine.

The tempting excuse was that #856 was documentation only, so the risk was low. That reasoning
is wrong twice over: the defect rate in prose that other agents act on is not lower than in
code, and "low risk" was a prediction made *before* the finding existed, which is exactly the
judgement the review exists to replace.

**Rule**: If you take an action that requests a review — marking a draft ready, pushing to a
reviewed PR, asking for one explicitly — do not merge until that review returns or you have
decided, in writing and for a stated reason, to proceed without it. "Documentation only",
"trivial" and "green CI" are not that reason; CI does not read prose.

Where the review is cheap and already running, waiting costs minutes. Where it is paid, the
spend is already committed the moment you trigger it — merging early wastes the money AND the
finding.

**Enforcement, and what it does not cover.** This took two rounds of review to state correctly,
and both corrections are worth keeping.

My first draft claimed the rule could not be gated. Wrong: nothing in the repository can observe
merge timing, because it is not a property of the tree, but GitHub branch protection requiring a
pull-request review before merge operates at the layer that can see it. That is a repository
setting, so it is a founder action, recorded in `tasks/handover-astra-2026-09-14.md` §5.

My second draft claimed that setting enforces the rule *exactly*. Also wrong. Required-approval
protection is satisfied by ANY qualifying approval — a pre-existing one, or one that arrives while
the triggered review is still running — so it blocks "merge with no review at all" and not "merge
while the review I just requested is in flight", which is the incident this lesson exists for.
Measured, not assumed: no file under `.github/workflows/` mentions Codex, and across #853, #856 and
#857 Codex never published a check run, so there is no head-specific status check available to
require today. Closing the remainder would mean building a workflow that blocks on review
completion for the current head; that does not exist and is not built here.

The setting also has to include administrators and disable bypass, or it constrains nobody: the
account that merges here is the repository administrator, and classic protection lets an
administrator straight through.

**So this is not a rule-12 gated rule, and it should not be presented as one.** Three review rounds
pushed me toward claiming enforcement I did not have; the honest classification is an operating
discipline with a partial, setting-level mitigation.

Building the full enforcement — a required check that waits for a review of the current head —
was considered and rejected on this repository's own evidence. `handover-astra-2026-09-11-prompt.md`
records the Codex bot out of credits and reviewing nothing. A required check waiting on it would
have blocked every merge for that whole period, and a bypass for that case reopens the hole. A gate
that deadlocks the repository when a third-party service is unavailable is worse than the discipline
it replaces.

That is the generalisable part: **rule 12's mechanisms are static checks over the tree** — an ESLint
rule, an allowlist spec, an AST test, a CI grep. They enforce invariants the repository can see.
A rule about the order of two events outside the tree is not that kind of invariant, and forcing a
gate onto it produces either theatre or a deadlock. Say which kind of rule you have written, and if
it cannot be gated, say that plainly instead of dressing a mitigation up as enforcement
(`test-gates-must-be-as-wide-as-their-rule.md` — a gate described as complete stops anyone looking
for the hole).

The general form is worth keeping: when a rule looks ungateable, check whether the enforcement
simply lives at a layer you do not control. "No gate is possible" and "the gate is someone else's
to enable" look identical from inside the repository and are not the same claim.

**Evidence**: PR #856 timeline (ready 18:19:34Z, Codex start 18:19:39Z, merge 18:19:45Z,
finding 18:23:03Z); the corrected pointer in `tasks/handover-astra-2026-09-14.md`; PR #853,
where waiting for the same reviewer surfaced three real defects.
