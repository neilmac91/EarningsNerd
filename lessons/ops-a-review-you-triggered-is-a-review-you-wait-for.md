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

**Enforcement.** My first draft of this lesson claimed the rule could not be gated, and that was
wrong — review found it. Nothing in the repository can observe the gap between "review requested"
and "merged", because merge timing is not a property of the tree; but GitHub branch protection
requiring a pull-request review before merge enforces it exactly, at the only layer that can see
it. That is a repository setting, so it is a founder action, recorded in
`tasks/handover-astra-2026-09-14.md` §5. Until it is enabled the discipline carries the rule —
which is a gap to close, not an exception to rule 12.

The general form is worth keeping: when a rule looks ungateable, check whether the enforcement
simply lives at a layer you do not control. "No gate is possible" and "the gate is someone else's
to enable" look identical from inside the repository and are not the same claim.

**Evidence**: PR #856 timeline (ready 18:19:34Z, Codex start 18:19:39Z, merge 18:19:45Z,
finding 18:23:03Z); the corrected pointer in `tasks/handover-astra-2026-09-14.md`; PR #853,
where waiting for the same reviewer surfaced three real defects.
