# Check the PR's mergeable state before diagnosing missing `pull_request` workflow runs

**Date:** 2026-10-02  
**Area:** Operations & workflow / CI

**Context:** Two pushes to a PR branch produced Vercel and `pull_request_target` runs (the review
gate) but no `CI` or `Copilot filing fidelity` run, although every earlier push had started
both. The workflow triggers, path filters and concurrency settings were unchanged. The PR's
`mergeable_state` was `dirty`: `main` had restyled a line that the branch deleted. GitHub
builds `pull_request` runs against the test merge commit and creates none when that merge
fails, while `pull_request_target` runs from the base branch and still fires.

**Rule:** When a `pull_request`-triggered workflow does not start on a push, read the PR's
`mergeable_state` first. `dirty` means a merge conflict: merge the base branch into the PR
head, resolve, push; the next synchronize event starts the runs. Only when the PR is mergeable
and runs are still missing look at triggers, filters, quotas or an incident.

**Evidence:** PR #1069, pushes `21d2457e` and `29e47ac7` (no `ci.yml` run); merge commit
`755427a6` resolved `frontend/features/waitlist/components/WaitlistStatus.tsx` and the next
push started every job.
