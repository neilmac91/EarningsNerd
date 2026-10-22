# A review you triggered is a review you wait for; merging inside it discards what you asked for

Date: 2026-09-14 (gate added 2026-09-16; its draft skip removed by #1331)   Area: ops

**Context**: On #856 the pull request was marked ready at 18:19:34Z, which is what triggers Codex
here; Codex began at 18:19:39Z; the merge landed at 18:19:45Z, six seconds into the review, and the
finding arrived four minutes later: the handover itself pointed the next agent at the wrong ESLint
lines (#857). An audit of the sixteen merges from #878 to #893 on 2026-09-16 found the quieter form
of the same failure: none merged before a review completed, but eight merged a head Codex had never
reviewed, because the commits that addressed its findings were pushed and merged without an
`@codex review` re-request (#879 to #884, #890, #892). Until 2026-09-16 the rule was prose only,
and the repository has no branch protection at all, so no CI check is required at merge time either.

On 2026-10-13 the gate itself read as passed without checking a review. One update set #1315's
body and marked it ready, which fired `ready_for_review` and an `edited` event whose payload still
said draft. The edited run started second, cancelled the ready run through the shared concurrency
group before it could wait, then skipped on its draft condition. GitHub reports a job skipped by its `if` as
success, which a required check counts as passing. So for about two minutes after the other checks
finished, the pull request could have merged with no review verified. Codex had already finished,
and the merge waited for a later run that logged the completed review. An audit of the seven
earlier programme merges (#1222 to #1245) found each one had merged on a run that logged a
completed review. Re-runs had produced the same skip. On #1319 and #1318 an `@codex review` around
the ready transition re-ran the draft run, and its new attempt replayed the draft payload. Each
attempt skipped and cancelled the ready run: runs 38483245956 and 38483284762 on #1319, and
38482584386 and 38482628083 on #1318.

**Rule**: A review you triggered, by opening a non-draft pull request, marking it ready, or
commenting `@codex review`, returns for the pull request's current head before you merge, or you
record why you did not as a line `Review override: <reason>` in the pull request body. After pushing
commits that address findings, comment `@codex review` immediately: a push alone re-triggers
nothing here, and that comment also re-runs the gate. The `review-gate` check (`.github/workflows/review-gate.yml`,
`backend/scripts/review_gate.py`) enforces this once a ruleset on `main` requires it, for a head whose first
review is the one you triggered: it passes on any completed review of the head, findings or not, and cannot tell
the ready mark's review from an earlier one of the same head, so that case is read by hand
(`ops-merge-after-the-ready-marks-own-codex-review.md`, #1469); a
required status check needs no approver, so it cannot lock a solo-administrator repository, whereas a
required pull-request review would (authors cannot approve their own pull requests and there is one
collaborator). The gate's job never skips on a pull-request event, and nothing in it may skip or
soften the gate step. On every pull-request event while the pull request is a draft it fails, reading
the flag as it is now rather than from the event, so the job passes only on a completed review of the
head or a recorded override.

**Evidence**: #856 timeline and #857; the 2026-09-16 merge audit in `tasks/archive/todo-ledger-through-2026-10-07.md`;
`backend/tests/unit/test_review_gate.py` (a completed review of another head is `wait`, never
`pass`; the job's condition is the event name alone, and the trigger set, the job set, the job's keys,
each step's keys and both steps' `with` maps are pinned, so no new trigger, second job, step `if`,
`continue-on-error`, `needs`, extra step or checkout input can skip or soften the gate, and no job in
another workflow may carry the check's name, written out or through an expression that can resolve to it;
a draft or an
unreadable draft flag fails, override or not); GitHub docs on required status checks versus required reviews and administrator
bypass, and on conditions ("a job that is skipped will report its status as 'Success'"); #1315's
gate runs [38478316282](https://github.com/neilmac91/EarningsNerd/actions/runs/38478316282)
(cancelled) and [38478317070](https://github.com/neilmac91/EarningsNerd/actions/runs/38478317070)
(skipped), and the run that passed, [38479137296](https://github.com/neilmac91/EarningsNerd/actions/runs/38479137296).
