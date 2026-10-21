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
  thread on the head answered. A green `review-gate` is not that read.
- A pull request opened ready has no ready-mark review; the latest review of its head is the one to read.
- A finding that lands after the merge gets its fix in the next pull request, with a reply on its thread naming it.

**Evidence**: #1469's Codex summary (comment 6327567665, the trigger "Draft marked ready"), the finding 4342609972 and
the reply 4342632073; `review-gate` run 39686282032 (passed 22:24:51Z); the merge `1c6dd6bf` at 22:26:52Z;
`backend/scripts/review_gate.py:178-180` (a Completed row passes, findings or not).

**Gate**: none yet; review-checked. A `review-gate` that waits for the ready mark's review and fails on
`has_unresolved_findings` would change the merge gate every session uses, so it was put to the founder on 2026-10-21
(`tasks/todo.md` F58).
