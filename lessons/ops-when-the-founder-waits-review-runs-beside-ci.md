# When the founder waits on the work, mark ready once round 1's fixes pass and run the delta review beside CI; only a blocker it finds holds the merge

Date: 2026-11-11   Area: ops, review

**Context**: On 11 November the screenshot activation sitting waited on two ops pull requests, #2031 (inspect's
execution evidence) and #2032 (the verifier's first-run blockers). Each ran its rounds in series: the high-tier
review, one fix push, the full local gates, round 2 of the fix diff, and only then the ready mark, CI and Codex. A
first-run dry-run ran beside #2032's round 1 and found two more blockers, so #2032 sat in review for about two hours
while the founder waited. The founder wrote: "this is taking too much time. please work pragmatically to progress
this effort". #2032 was then marked ready with round 2 still running and merged 13 minutes later, when CI and Codex
were clean. Round 2 found no blocker, only test-coverage gaps, which went to this lesson's follow-up pull request.

**Rule**:
- When the founder is waiting on the work (an activation sitting, a production fix), do not hold the ready mark for
  the delta round. Once round 1's findings are fixed and the affected suites pass (the full gate runs in CI on the
  ready mark), mark ready and let round 2 of the fix diff run beside CI and Codex.
- Only a blocker that round 2 finds before the merge holds it. A should-fix or a nit goes to a follow-up pull request
  opened right after, which waits until the founder's operation is done if it changes what that operation runs.
- Proof on the real path (an offline end-to-end harness, a reproduction on the real code) is worth more than another
  review round of the same diff; run it first.
- Say the trade in the pull request body: what ran before the ready mark, what runs beside CI, and what went to the
  follow-up.

**Evidence**: #2032's body, "Review" and "Full local gates"; the follow-up pull request that carries this lesson; the
founder's message of 2026-11-11.
