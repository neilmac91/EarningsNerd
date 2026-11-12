# When the founder waits on the work, mark ready once the affected suites pass and run the review round beside CI; only a blocker it finds holds the merge

Date: 2026-11-11, aligned 2026-11-12   Area: ops, review

**Context**: On 11 November the screenshot activation sitting waited on two ops pull requests, #2031 (inspect's
execution evidence) and #2032 (the verifier's first-run blockers). Each ran its rounds in series: the high-tier
review, one fix push, the full local gates, round 2 of the fix diff, and only then the ready mark, CI and Codex. A
first-run dry-run ran beside #2032's round 1 and found two more blockers, so #2032 sat in review for about two hours
while the founder waited. The founder wrote: "this is taking too much time. please work pragmatically to progress
this effort". #2032 was then marked ready with round 2 still running and merged 13 minutes later, when CI and Codex
were clean. Round 2 found no blocker, only test-coverage gaps, which went to this lesson's follow-up pull request.
The same evening #2036 (the verifier's Cloud SQL volume name) was marked ready once its affected suites passed, and
its round 1 ran beside CI and Codex. The review workflow ran two agents at a time on a four-CPU machine, so its third
lens also ran as its own Opus agent. #2036 merged when CI, Codex and the gate were clean and every lens had reported
no blocker; its should-fixes went to #2037. On 12 November the founder limited reviews to one round unless round 1
finds a blocker (`ops-converge-a-review-in-one-fix-round.md`), so a second round now runs only on a blocker's fix.

**Rule**:
- When the founder is waiting on the work (an activation sitting, a production fix), do not hold the ready mark for a
  review round. Once the affected suites pass (the full gate runs in CI on the ready mark), mark ready and run round 1
  beside CI and Codex; when round 1 finds a blocker, run round 2 on its fix beside CI the same way.
- Merge once CI, Codex and the review gate are clean and the round has reported. Only a blocker it finds holds the
  merge. A should-fix or a nit goes to a follow-up pull request opened right after, which waits until the founder's
  operation is done if it changes what that operation runs; the full gate and Codex's review of its head cover it.
- When the review workflow's concurrency cap queues a lens behind the others, run that lens as its own agent with the
  workflow's own prompt and the tier's model, so the round reports with CI rather than after it.
- Proof on the real path (an offline end-to-end harness, a reproduction on the real code) is worth more than another
  review round of the same diff; run it first.
- Say the trade in the pull request body: what ran before the ready mark, what ran beside CI, and what went to the
  follow-up.

**Evidence**: #2032's body, "Review" and "Full local gates"; #2036's body, "Review"; #2037; the founder's messages of
2026-11-11 and 2026-11-12.
