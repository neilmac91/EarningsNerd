# Mechanical proofs must run against committed state — a proof that cannot fail proves nothing

Date: 2026-07-06   Area: test

**Context**: During F3.1, the first "pure move proof" ran `git diff origin/main..HEAD`
while the file moves were still **uncommitted** — the two refs were identical commits, so
the diff was empty and the proof "passed" vacuously. It could not have failed no matter
what the working tree contained. The catch: commit first, then re-run the proof against
the committed range (which then showed the real 21-file / 25-25 import-only diff).

**Rule**: Before trusting any mechanical verification (diff proofs, grep gates, rg → 0
checks), confirm it runs against the state that will actually merge — committed HEAD vs
the merge base — and sanity-check that it CAN fail (perturb one line; the proof must go
red). A green check that was never able to go red is not evidence.

**Evidence**: PR #561 delta-log entry ("Vacuous-proof catch"): first proof compared
identical commits pre-commit; re-run post-commit produced the real 25/25 symmetric
import-only result.
