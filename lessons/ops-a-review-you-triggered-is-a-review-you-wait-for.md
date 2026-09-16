# A review you triggered is a review you wait for; merging inside it discards what you asked for

Date: 2026-09-14 (gate added 2026-09-16)   Area: ops

**Context**: On #856 the pull request was marked ready at 18:19:34Z, which is what triggers Codex
here; Codex began at 18:19:39Z; the merge landed at 18:19:45Z, six seconds into the review, and the
finding arrived four minutes later: the handover itself pointed the next agent at the wrong ESLint
lines (#857). An audit of the sixteen merges from #878 to #893 on 2026-09-16 found the quieter form
of the same failure: none merged before a review completed, but eight merged a head Codex had never
reviewed, because the commits that addressed its findings were pushed and merged without an
`@codex review` re-request (#879 to #884, #890, #892). Until 2026-09-16 the rule was prose only,
and the repository has no branch protection at all, so no CI check is required at merge time either.

**Rule**: A review you triggered, by opening a non-draft pull request, marking it ready, or
commenting `@codex review`, returns for the pull request's current head before you merge, or you
record why you did not as a line `Review override: <reason>` in the pull request body. After pushing
commits that address findings, comment `@codex review` immediately: a push alone re-triggers
nothing here, and that comment also re-runs the gate. The `review-gate` check (`.github/workflows/review-gate.yml`,
`backend/scripts/review_gate.py`) enforces exactly this once a ruleset on `main` requires it; a
required status check needs no approver, so it cannot lock a solo-administrator repository, whereas a
required pull-request review would (authors cannot approve their own pull requests and there is one
collaborator).

**Evidence**: #856 timeline and #857; the 2026-09-16 merge audit in `tasks/todo.md`;
`backend/tests/unit/test_review_gate.py` (a completed review of another head is `wait`, never
`pass`); GitHub docs on required status checks versus required reviews and administrator bypass.
