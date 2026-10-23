# Merge only once the ready mark's own Codex review of the head has completed with no unresolved finding

Date: 2026-10-21, updated 2026-10-22 (#1496) and 2026-10-23 (F58 call 1)   Area: ops / review

**Context**: #1469 (records) had Codex's clean review of its head `60210176` (requested, completed at 22:11Z) and CI
green, and was marked ready at 22:24:41Z. The ready mark starts a second Codex review of the same head, its summary row's
trigger "Draft marked ready". `review-gate` ran at 22:24:43Z, read the summary while it still showed the earlier
completed review, and passed at 22:24:51Z; the session merged at 22:26:52Z. The ready mark's review had posted a P2 at
22:26:35Z (4342609972: D-053's row left out the reservation at a pull request's opening), so the merge landed with a
finding no one had read. `backend/scripts/review_gate.py` then passed once the summary row for the head read Completed:
it did not read whether that review found anything, and it could not tell the ready mark's review from an earlier one of
the same head (F58 changed both; **Gate** below).

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
- A finding answered without a push (one about the pull request's body) leaves the ready review's unresolved state on
  the same head. Resolving its thread does not clear that state, and a manual review of the same head cannot replace it.
  Answer and resolve the thread, then make one fresh draft-to-ready transition, its two steps a few seconds apart, with
  no manual request, and read that review. On #1523 the ready review's P1 (the body listed sixteen mutation proofs
  where AGENTS.md §4 asks for one) was fixed in the body. The summary still read unresolved two minutes after the
  thread was resolved, and review-gate failed on it. The fresh transition's review completed clean, and review-gate
  passed.
- A finding that lands after the merge gets its fix in the next pull request, with a reply on its thread naming it.
- Make no draft-to-ready transition and no `@codex review` while any Codex review of the pull request shows Running,
  the ready mark's own review included, after a push too: the gate's advice to comment `@codex review` holds once the
  running review completes or is an hour old. The summary carries no run id, so the gate replays its history (F58 call
  1): a completion pairs with the open start of its head and trigger, a start begun while another of its head and
  trigger was open never takes a completion (it could be either run's), and any start still open makes the gate wait
  until that review completes or is an hour old. A transition or request made while a review runs therefore costs the
  hour: its start stays open until then, and the gate then needs one fresh review. An overlap hidden behind another
  completion no longer passes while a review still runs (B1 in review 6341504879), whichever run finishes first. That
  replay is this rule's machine gate (rule 12), and the gate prints each reason as it polls. Once the summary reads
  Completed (it shows only the newest review, so a superseded run may stay Running behind it):
  - if the gate names a review still open, wait for the time its message names: the job times out after 20 minutes,
    so once that review completes or turns an hour old, re-run the timed-out job (re-run its failed jobs; a review
    request would start another overlap);
  - if it names a completion it cannot pair, or one paired with a start before the latest ready mark, or a missing
    history, make one fresh draft-to-ready transition once no review is open, its two steps a few seconds apart (the
    gate refuses a draft and a ready mark in the same second), with no manual request, and let its review finish. On a
    head copilot-eval has drawn on, the transition draws nothing more (`lessons/ops-copilot-eval-red-is-triaged-never-rerun.md`);
  - otherwise a gate job still waiting decides on its own, and a timed-out one is re-run.
- A review still Running an hour after it started counts as abandoned (F58 call 1; the founder on 2026-10-23: "Call 1
  approved"). The hour is review 6341504879's recommendation: all 242 single runs in PRs 1380–1486 finished within 21
  minutes. The gate stops waiting for it and never pairs a completion with it, so a completion that comes an hour or
  more after its start pairs with nothing, at any later poll. When it was the ready mark's own review, make one fresh
  draft-to-ready transition as above once it is an hour old (the gate's Running message names that time), with no
  manual request: its review pairs and passes. A clean manual review still cannot stand in for it (F58 call 2, open).
  The one risk call 1 accepts: if the hung run does complete after its hour while that fresh review is still running,
  the replay cannot tell the two apart and pairs the completion with the fresh start, so the gate can pass before the
  fresh review ends.
- While Codex cannot review (credits exhausted, service down), AGENTS.md §5's `Review override:` line, naming the tier and
  the substitute review, stands in for that read, as it does for `review-gate`; it is never written while Codex can review.

**Evidence**: #1469's Codex summary (comment 6327567665, the trigger "Draft marked ready"), the finding 4342609972 and
the reply 4342632073; `review-gate` run 39686282032 (passed 22:24:51Z); the merge `1c6dd6bf` at 22:26:52Z;
`backend/scripts/review_gate.py:178-180` at the incident revision (a Completed row passed, findings or not). #1476's ready-mark
review of `900065d3` completed at 03:58:34Z on 2026-10-22 with a finding unresolved (4344402620, the case the
rule's third line answers), and `review-gate` passed on it at 03:58:51Z (run 39719618842). #1496's ready review of
`cb86536c` started at 20:28:50Z on 2026-10-22 and had not completed when `review-gate` timed out at 20:49:10Z (job
120070504428). A draft-to-ready flip at 20:58:18–22Z, while it still showed Running, recorded a second start at
20:58:28Z, so the clean completion at 21:01:14Z could not be paired (the correction, comment 6351182186). Once the
summary read Completed, one fresh transition at 21:03:58–59Z with no manual request started a review at 21:04:05Z that
completed clean at 21:06:17Z; `review-gate` passed at 21:06:49Z (run 39854178499), and the merge is `e8be8ba7`. Every
line the gate printed in the timed-out job carries its exit time, and run 39853388960, cancelled at 21:04:56Z, printed
none (the S1 note, comment 6351439364). On 2026-10-23 four merges waited on the founder's word for a hung review: #1495
(`b7d4b164`, a manual review Running from 23:12 the night before, merged on a review override), #1497 (`383b6f73`,
Running from 22:38, treated as abandoned on the founder's call), #1507 (`cdf9ee04`, Running from 00:49, marked ready on
the founder's word) and #1519 (`89b469dc`, its ready review Running from 13:27:56Z, merged on a review override). The
founder then approved call 1.

**Gate**: The founder approved F58 on 2026-10-22. `backend/scripts/review_gate.py` reads the
summary's full-head machine state, the live PR head/draft flag, GitHub's ready-transition timeline,
and the trusted bot's comment edit history. A completion is paired with its start by the replay
below. That start must reach the next whole second after GitHub's event/request timestamp,
which has only second precision; a start within that same second cannot prove ordering. An earlier clean review, a manual
review while the ready review is still pending, missing history, or contradictory API snapshots
cannot satisfy the gate. Unresolved findings fail it.

For a PR marked ready, the ready-triggered cycle must have completed. A later manual review of a
different head may supersede that cycle's findings once its own current-head state is clean; this
preserves the correction path above without requiring another draft/ready transition. A manual
review of the same head requires the ready-triggered cycle itself to be clean. A PR opened ready
uses its creation time instead. Missing or changed service formats fail closed; the existing
service-unavailability override remains the only documented exception. The bot exposes no unique
review-run ID, so the gate replays the edit history: a completion pairs with the open start of its head and
trigger, never with one begun while another of them was open; a start still open blocks until it completes or is
an hour old, when it counts as abandoned; and a completion within the hour after an unreadable version never pairs
(F58 call 1, 2026-10-23).
Marking ready already requests a review: let that automatic review finish before making another
manual request. If two manual requests overlap after a clean ready cycle, the later one's review never pairs: an
hour after it started (the gate's message names the time), request a fresh review. If the ready review was one of
the overlapping pair, or the ready cycle's required history is missing, only a fresh ready transition clears it:
make it once pending reviews have completed or are an hour old, and let its automatic review finish. This recovery does not change the normal
new-head correction path, which keeps a PR ready when its completed ready cycle is provable.

`backend/tests/unit/test_review_gate.py` covers these boundaries alongside the existing closing
reference, draft, identity and short-SHA ambiguity guards. The workflow loads the gate from the
trusted base branch, so #1486's own required check ran the previous implementation. The separate
F55 paid-evaluation reservation remains review-checked.
