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
  thread on the head answered. A green `review-gate` is not that read. The marker is an HTML comment at the top of the
  Codex summary, its braces escaped as `&#123;` and `&#125;` in the raw text; decoded, a clean read of #1476's head was
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
`backend/scripts/review_gate.py:178-180` (a Completed row passes, findings or not). #1476's ready-mark
review of `900065d3` completed at 03:58:34Z on 2026-10-22 with a finding unresolved (4344402620, the case the
rule's third line answers), and `review-gate` passed on it at 03:58:51Z (run 39719618842).

**Gate**: none yet; review-checked until founder row F58 picks the gate's form. A `review-gate` that waits for the
ready mark's review and fails on `has_unresolved_findings` would change the merge gate every session uses, so it went
to the founder on 2026-10-21 (`tasks/todo.md` F58). The rule only adds a wait before a merge, so it lets through
nothing the gate refuses; `ops-reserve-eval-baseline-before-each-push.md` stays in force the same way, review-checked
until founder row F55 picks its gate's form.
