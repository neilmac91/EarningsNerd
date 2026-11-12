# Converge a review in one round: write the done criteria first, fix round 1's findings once, run a second round only on the fix of a blocker round 1 found, and send a later finding outside that fix diff to the pull request's limits, or to a follow-up row AGENTS.md §7 admits

Date: 2026-11-03, tightened 2026-11-12   Area: ops, review

**Context**: Gate (d) of the CODE RED queue, the excluded-directory output hook (a high-tier change under
`.claude/hooks/`), had nine reviews between 2026-10-30 and 2026-11-03: the tier's full review, then a delta review
after each fix. Rounds 4 to 9 each found no blocker and called the change mergeable, and after each one the chief sent
its should-fix findings back for another fix round; the tenth was running when this lesson was written. Three things
kept the loop going. Each delta review read the whole change again, not only the fix. The bar was open-ended,
agreement with an independent reference matcher over millions of generated texts, so each round found a further class
of miss, often in code the previous fix had added. And every round's should-fixes were fixed and then reviewed again
in full, though the repository's own review workflow (`.claude/workflows/premerge-review.js`) counts only blockers
against a merge and had no second round; AGENTS.md §5 said how a review runs, but not when the reviewing ends. Gate
(c), the gh literal-path hook, was in its third review on the same course. The founder, the same day: "i'm getting
concerned with the pattern of multiple review rounds that i'm seeing with your work. please ensure to avoid endless
rounds of review where possible. after comments from the first round of review are addressed, it should be an
exceptional circumstance for an additional round of review to uncover findings that are significant enough to warrant
addressing."

On 2026-11-12 the founder tightened the rule. Under its earlier form a round 2 reviewed every fix diff, so #2039 and
#2040, whose round 1 found no blocker, each ran a second high-tier round over the fixes of their should-fix findings
while the founder's screenshot sitting waited on them. Neither second round found a blocker. The founder, the same
day: "avoid excessive review rounds (one review round max, unless critical comments need to be addressed in second
review)".

**Rule**:
- Before round 1, write the done criteria in the pull request body and the builder's brief: what the change must do and
  the cases it must cover. A case outside them is a limit the body names or a follow-up row, never another round.
- Round 1 is the tier's full review (AGENTS.md §5), and the only round unless it finds a blocker. Fix its findings in
  one fix round: every blocker, and every should-fix inside the done criteria. The full gate and Codex's review of the
  fix's head cover the fix of a should-fix or a nit; no second round reviews it.
- Run round 2 only when round 1 found a blocker (the founder's "critical comments"), and name that blocker under
  "Review" in the pull request body. Round 2 reviews only the fix diff, from round 1's head to the fix's head, with the
  tier's whole team: a smaller diff is no reason to cut agents
  (`ops-replace-a-redundant-review-stage-never-drop-it.md`).
- Bring the base into the branch, by merge or rebase, before round 1 or after the last round, never between rounds: a
  merge puts the base's changes into the fix diff, and a rebase leaves the previous round's head off the branch.
- Fix a round-2 finding that lies in the fix diff and inside the done criteria without another round; the full gate and
  Codex's review of that head cover the change. Name one outside the diff or beyond the criteria as a limit in the
  pull request body, or send it to a follow-up row in `tasks/todo.md` only where `AGENTS.md` §7 admits one
  (`ops-a-todo-row-needs-a-reader-a-launch-blocker-or-an-exposure.md`), unless it is a blocker.
- A third round needs the founder's go, whatever round 2 found; it reviews only its own fix diff.
- Give the review workflow (`.claude/workflows/premerge-review.js`) the round: `round` on each pull request, and
  from round 2 `fixBase` (the commit the previous round reviewed) and `reason` (the blocker whose fix it reviews),
  from round 3 `founderGo` (the founder's words). It refuses a round that is not a whole number from 1, a round
  without them, a field before its round, or a round field set on the batch, before any agent starts, and shows a
  later round's lenses and refuters only the fix diff.
- Codex's review of each head is not a round. Weigh each of its findings by the same test, and answer every thread
  with the fix, or with the row or limit the finding went to.
- A records pull request's same-context delta checks follow the rule: each covers only its head's fix commit.

**Evidence**: the founder's messages of 2026-11-03 and 2026-11-12, and the "Review" sections of #2039 and #2040.
The CODE RED closure chain (`tasks/code-red-20261004/runtime/control/`) registers gate (d)'s review workflows round
by round under its label `excluded-dir-output-hook-pr-01`, and gate (c)'s under `gh-literal-path-hook-pr-01`. The
founder chose on 2026-11-03 to gate the rounds in the same pull request as this lesson: the review workflow's
`round` input, each refusal proven by `frontend/tests/unit/premergeReviewWorkflow.spec.ts`. The workflow takes the
round and `fixBase` on the caller's word and checks only that a reason and a go are stated, so giving it the true
round and the previous round's head, and what a reason or a go says (that round 1 found the blocker it names),
stay review-checked, as do that `fixBase` is an ancestor of the head (a later round's prompt asks for one blocker
when it is not), the base's timing, writing the done criteria first, sending a finding to a follow-up row and
weighing Codex's findings.
