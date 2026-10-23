# Read the pull request's new activity in the turn that merges it, and merge only when every actionable finding or request has its answer

Date: 2026-10-23 · Area: ops / merging

**Context.** #1533 (F61 call 1's records) merged at 2026-10-23T21:03:10Z from `851f014`, with CI green
and `review-gate` passed on Codex's clean review of the ready mark. A records review of that head had
posted at 20:58:50Z, four minutes earlier (review 5634381118). Its one thread (4364177476) asked, before
merge, that call (1) stop saying "done" and "no stored row needs a fix", because the count never read
five of the 72 summaries. The merge turn read the pull request with `get_status` and `get` at
21:02:56Z, after the review had posted, but neither call returns a review or a thread. The session's
last read of its notifications, at 20:58:38Z, came twelve seconds before the review. The review's
notification, queued at 20:58:54Z, was read at 21:07:00Z, after the merge. So the merge went over an
unanswered request. The reviewer's own follow-up, #1536, made the correction after the merge.

**Rule.** Immediately before the merge call, in the same turn, read:
- the reviews (`pull_request_read` with `get_reviews`);
- the review threads (`get_review_comments`);
- the conversation comments (`get_comments`);
- the notifications queued for the session (`ReadNotifications`).

Every finding or request those reads show needs an explicit answer before the merge: a review thread, a
review that asks for a change, or a comment that asks for something. An answer is either a fix pushed,
which restarts the merge conditions, or a reply that says why not. A request made "before merge" stops
the merge until it is answered, whatever CI and `review-gate` say. Clean review receipts, bot status
updates and informational comments need no reply. Go by the reads, not by memory: a compacted session
has lost its last read.

**Gate.** Review-checked. `review-gate` reads Codex's summary and the issue comments, never a review or
a review thread (`backend/scripts/review_gate.py`, `fetch_state`), and no review event starts it
(`.github/workflows/review-gate.yml`, its `on:` triggers). Main's rules could refuse a merge while an
inline review thread is unresolved, with "Require conversation resolution before merging", and turning
that on is the founder's call (`tasks/todo.md` row F63). Review bodies, conversation comments and
notifications would stay review-checked even then.

**Evidence.** #1533: review 5634381118 and thread 4364177476 at 20:58:50Z, and the merge at 21:03:10Z.
The correction is in #1536. This rule extends two rules to every reviewer: `AGENTS.md` §6 ("Read the
head SHA from the PR before merging; never type one from memory") and
`lessons/ops-merge-after-the-ready-marks-own-codex-review.md` ("every Codex thread on the head
answered").
