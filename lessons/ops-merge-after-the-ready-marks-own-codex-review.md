# Merge only once the ready mark's own Codex review of the head has completed with no unresolved finding

Date: 2026-10-21   Area: ops / review

**Context**: #1469 (records) had Codex's clean review of its head `60210176` (requested, completed at 22:11Z) and CI
green, and was marked ready at 22:24:41Z. The ready mark starts a second Codex review of the same head, its summary row's
trigger "Draft marked ready". `review-gate` ran at 22:24:43Z, read the summary while it still showed the earlier
completed review, and passed at 22:24:51Z; the session merged at 22:26:52Z. The ready mark's review had posted a P2 at
22:26:35Z (4342609972: D-053's row left out the reservation at a pull request's opening), so the merge landed with a
finding no one had read. `backend/scripts/review_gate.py` passes once the summary row for the head reads Completed: it
does not read whether that review found anything, and it cannot tell the ready mark's review from an earlier one of the
same head.

**Rule**:
- Before a merge, read the Codex summary comment's `codex-review-state` for the head: `status` completed and
  `has_unresolved_findings` false, on the review the ready mark started when the pull request was a draft, and every Codex
  thread on the head answered. The F58 `review-gate` checks that machine state and cycle evidence; answering every thread remains
  part of the reviewer's disposition. The marker is an HTML comment at the top of the Codex summary, its braces escaped as `&#123;` and `&#125;` in the raw text; decoded, a clean read of #1476's head was
  `codex-review-state:v1 {"code_review":{"commit_sha":"b001bcab…","has_any_findings":true,"has_unresolved_findings":false,"status":"completed"},…}`
  (findings it raised earlier, all resolved).
- A pull request opened ready has no ready-mark review; the latest review of its head is the one to read.
- A push made once the pull request is ready, to answer a finding, moves the head past the ready mark's review. The
  review of the new head that the push's `@codex review` requests is then the one to read, the same way; the pull
  request stays ready.
- A finding that lands after the merge gets its fix in the next pull request, with a reply on its thread naming it.
- While Codex cannot review (credits exhausted, service down), AGENTS.md §5's `Review override:` line, naming the tier and
  the substitute review, stands in for that read, as it does for `review-gate`; it is never written while Codex can review.

**Evidence**: #1469's Codex summary (comment 6327567665, the trigger "Draft marked ready"), the finding 4342609972 and
the reply 4342632073; `review-gate` run 39686282032 (passed 22:24:51Z); the merge `1c6dd6bf` at 22:26:52Z;
`backend/scripts/review_gate.py:178-180` at the incident revision (a Completed row passed, findings or not). #1476's ready-mark
review of `900065d3` completed at 03:58:34Z on 2026-10-22 with a finding unresolved (4344402620, the case the
rule's third line answers), and `review-gate` passed on it at 03:58:51Z (run 39719618842).

**Gate**: The founder approved F58 on 2026-10-22. `backend/scripts/review_gate.py` reads the
summary's full-head machine state, the live PR head/draft flag, GitHub's ready-transition timeline,
and the trusted bot's comment edit history. A completion is paired with its nearest preceding
running state, whose start must follow the relevant request. An earlier clean review, a manual
review while the ready review is still pending, missing history, or contradictory API snapshots
cannot satisfy the gate. Unresolved findings fail it.

For a PR marked ready, the ready-triggered cycle must have completed. A later manual review of a
different head may supersede that cycle's findings once its own current-head state is clean; this
preserves the correction path above without requiring another draft/ready transition. A manual
review of the same head requires the ready-triggered cycle itself to be clean. A PR opened ready
uses its creation time instead. Missing or changed service formats fail closed; the existing
service-unavailability override remains the only documented exception. The bot exposes no unique
review-run ID, so overlapping distinct starts that cannot be paired unambiguously also wait.
Marking ready already requests a review: let that automatic review finish before making another
manual request. If two requests overlap, wait for them to settle before requesting a fresh review;
if the ready cycle's required history is missing, create a fresh ready transition after pending
reviews settle and let its automatic review finish. This recovery does not change the normal
new-head correction path, which keeps a PR ready when its completed ready cycle is provable.

`backend/tests/unit/test_review_gate.py` covers these boundaries alongside the existing closing
reference, draft, identity and short-SHA ambiguity guards. The workflow continues to load the gate
from the trusted base branch, so this PR's own required check uses the previous implementation
until the change lands. The separate F55 paid-evaluation reservation remains review-checked.
