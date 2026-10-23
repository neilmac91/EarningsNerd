# Read the pull request's new activity in the turn that merges it, and merge only when every actionable finding or request has its answer

Date: 2026-10-23 · Area: ops / merging

**Context.** #1533 (F61 call 1's records) merged at 2026-10-23T21:03:10Z from `851f014`, with CI green
and `review-gate` passed on Codex's clean review of the ready mark. A records review of that head had
posted at 20:58:50Z, four minutes earlier (review 5634381118). Its one thread (4364177476) asked, before
merge, that call (1) stop saying "done" and "no stored row needs a fix", because the count never read
five of the 72 summaries. The merging session had last read the pull request before that review arrived.
The review's notification sat unread in the session's queue, so the merge went over an unanswered
request. The reviewer's own follow-up, #1536, made the correction after the merge.

**Rule.** In the turn that calls merge, read the pull request again, after the head SHA:
- its reviews;
- its open review threads;
- its conversation comments;
- any notifications queued for the session.

Every finding or request among what arrived since your last read needs an explicit answer before the
merge: a review thread, a review that asks for a change, or a comment that asks for something. An answer
is either a fix pushed, which restarts the merge conditions, or a reply that says why not. A request made
"before merge" stops the merge until it is answered, whatever CI and `review-gate` say. Clean review
receipts, bot status updates and informational comments need no reply.

**Gate.** Thread disposition stays review-checked. `review-gate` reads Codex's review only. Main's
rules could refuse such a merge with "Require conversation resolution before merging", and turning that
on is the founder's call (`tasks/todo.md` row F63).

**Evidence.** #1533: review 5634381118 and thread 4364177476 at 20:58:50Z, the merge at 21:03:10Z;
the correction in #1536.
`AGENTS.md` §6 ("Read the head SHA from the PR before merging; never type one from memory") is the rule
this one extends.
