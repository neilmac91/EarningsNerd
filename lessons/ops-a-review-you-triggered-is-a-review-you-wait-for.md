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

**Enforcement: what I got wrong, and where it actually stands.** Six review rounds went into this
paragraph and every one of them corrected me, so the history is worth more than the conclusion.

I claimed the rule could not be gated. Wrong — nothing in the repository can observe merge timing,
but GitHub operates at a layer that can.

I claimed required-approval branch protection enforces it exactly. Wrong — any qualifying approval
satisfies it, including one arriving while the triggered review is still in flight.

I claimed a required current-head check would deadlock during a review-service outage, citing
`handover-astra-2026-09-11-prompt.md` recording the Codex bot out of credits. Also wrong, and this
is the interesting one: the rule's own escape clause defeats my objection. A check that passes on
either an observable review for the head **or** an explicitly recorded override with a reason never
deadlocks, because the override branch stays open — and it enforces precisely what the rule says,
"wait, or write down why you did not". Relabelling the rule as an operating discipline did not make
rule 12 stop applying to it.

Where it stands: that check is buildable, is not built, and is a founder decision along with any
branch-protection change. The branch-protection route in particular must not be enabled as first
drafted — this repository has exactly one collaborator, who is the administrator and the author of
every pull request, so requiring an approval with bypass disabled would lock the repository
outright. Both are recorded in `tasks/handover-astra-2026-09-14.md` §5.

Until one exists the rule rests on discipline, and that is a gap, not an exemption.

**Evidence**: PR #856 timeline (ready 18:19:34Z, Codex start 18:19:39Z, merge 18:19:45Z,
finding 18:23:03Z); the corrected pointer in `tasks/handover-astra-2026-09-14.md`; PR #853,
where waiting for the same reviewer surfaced three real defects.
