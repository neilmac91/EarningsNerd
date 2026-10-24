# Before a backend merge, read main's newest push runs and every slot claim: another session can hold the deploy slot

Date: 2026-10-24 · Area: ops / release

**Context.** On 2026-10-24 a serial backend train (#1549, then #1545, #1548 and #1546) met a merge
from another session.
- At 00:54:25 #1547's session posted on #1547 that it was taking the next free backend slot, and asked
  that later backend merges wait until it posted its deploy's verification. It merged at 00:54:47
  (`a97e5271`).
- At 00:59 #1549 merged (`3aec67e0`). Its merge-turn reads covered #1549's own reviews, threads and
  comments, and the session's notifications, so none of them carried #1547's claim. Its trial merge had
  been built on the main before #1547.
- `deploy-backend` kept the deploys apart: one concurrency group, `cancel-in-progress: false`
  (`.github/workflows/ci.yml`). #1547's deploy ran from 01:17:48 to 01:20:29. #1549's started at 01:20:32
  and read healthy at 01:22:51. Both verified healthy, but #1549 had merged while #1547's deploy was
  unverified.

**Rule.** Immediately before merging a pull request that changes `backend/` outside `backend/tests/`:
1. **Main's newest push runs.** Read `ci.yml`'s newest runs on `main` (event `push`). If the newest
   backend-changing push's `deploy-backend` has not finished, or its health is not yet verified, wait.
2. **Slot claims.** Read the comments of every open pull request updated since the last verified backend
   deploy for a slot claim: a comment that it is taking the slot, or that asks later merges to hold.
   Honour the claim until that pull request posts its verification.
3. **The trial merge's base.** Confirm main is still the commit the trial merge was built on. If it moved,
   build the trial merge again on the new main and run the gates there.
4. **Your own claim.** Post a claim on the pull request when it merges, and the verification when its
   deploy is healthy, so the next merger can read both.

**Why the concurrency group is not enough.**
- **It does not stop a merge.** It orders deploy jobs, so two never run at once, but a second merge can
  still land while the first deploy is unverified.
- **A failed deploy is not retried.** So a merge stacked behind one ships on a base nobody verified.
- **It can skip a deploy.** GitHub keeps one running and one pending job per group: "By default, any
  existing `pending` job or workflow in the same concurrency group will be canceled," and "the new queued
  job or workflow will take its place" (GitHub's concurrency documentation). With three backend merges in
  quick succession, the middle merge's `deploy-backend` is cancelled, and its run reads as cancelled.

**Gate.** Review-checked. No check on a pull request can see main's deploy state at the moment of the
merge, and the merge call carries no such condition. The concurrency group is the machine part, and it
covers only overlapping deploys.

**Evidence.**
- #1547's claim and merge: comments 6377804402 (00:54:25) and 6377811629 (00:54:59). The mistake was
  posted there at 01:06 (6377942170).
- The two runs: 40047306851 (`a97e5271`) and 40047643613 (`3aec67e0`).
- The two verifications: 6378105580 on #1547 and 6378118828 on #1549.
- #1545 then merged at 01:24 after all four reads, on the main its trial merge had used.
