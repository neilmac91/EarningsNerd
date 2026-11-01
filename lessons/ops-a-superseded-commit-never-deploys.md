# Never let an older commit deploy after a newer one: `deploy-backend` skips a commit main has moved past with deployable backend changes

Date: 2026-11-01 · Area: ops / deploy

**Context.** On 2026-10-31 Agent E merged Agent C's batch 1 back to back, under the founder's approval of two or three PRs per deploy turn:
- #1848 at 19:42:44 UTC (`b4863c8`);
- #1863 at 19:42:58 (`6cf4efa`);
- #1713 at 19:43:11 (`b994da4`).

Each push ran its own CI and its own `deploy-backend`. Each deploy built and shipped its own commit's image, and routed all traffic to it. The `deploy-backend` concurrency group (`cancel-in-progress: false`, `queue: max`) runs waiting deploys in the order their runs reach the job, not in merge order:
- #1713's run, the newest commit, deployed first, at 20:11:54.
- #1863's older commit deployed next, at 20:14:52. Production then ran without #1713's backend changes.
- #1848's still older deploy waited last.

Agent E cancelled #1848's run (41235496493) before any deploy step ran. It then re-ran #1713's `deploy-backend` job (run 41235529857, attempt 2), which put `b994da4` back at 20:17:46. Production ran the older tree for about three minutes. Health checks stayed green throughout: a rollback like this one reads healthy.

**Rule.**
1. **The detector skips a superseded commit.** `deploy-backend`'s "Detect backend changes" step first finds this commit's deployable change. It then reads main's tip by its full ref (`git fetch --no-tags --depth=1 origin refs/heads/main`, up to three attempts), and applies the same path rule to `git diff HEAD <tip>`.
   - If main has moved past this commit with deployable backend changes, the deploy is skipped, with a "Superseded deploy skipped" notice on the run: a newer backend commit's run deploys them.
   - If main has moved only with changes outside the image (frontend, records, `backend/tests/`), this commit still deploys.
   - A failed read of main fails the step ("Deploy not attempted"), and nothing deploys.
   - The full ref matters: for the short name `main`, git would take a tag named `main` over the branch.
2. **A superseded skip concludes success.** A superseded run's `deploy-backend` concludes success (green), with every deploy step skipped and no `apply_migrations: applied=` line. So a commit has deployed only when its own run shows that line and health, or a newer deploy that carries it does. A change that must be live before the next one merges (step 1 of `lessons/ops-drop-a-mapped-column-in-two-deploys.md`) waits for such a deploy, not for its own job's colour.
3. **Back-to-back backend merges usually deploy once, as the newest commit.** Batch only under the founder's approval. Each run's tests take about 25 minutes before its deploy reads main, so merges made minutes apart are all on main by then, and every older commit's deploy is skipped. A merge that lands after an older deploy has read main deploys after it, which is still merge order. Verify the deploy that ran, and record the older runs' skips. The next backend merge waits for that verification (`AGENTS.md` §6, one unverified backend deploy at a time).
4. **Never roll back by re-running an old deploy.** Rule 1 skips a re-run of an older commit's deploy once main has moved past it with deployable backend changes. Roll back by moving traffic to a prior revision (`docs/DEPLOYMENT.md`, "Rollback"), or forward with a revert on main.
5. **When the newest deployable commit's run deploys nothing, act on that run.** The newest deployable commit is the newest that changed `backend/` outside `backend/tests/`. The older runs skipped as superseded, so production keeps the image from before the batch.
   - **A test job failed, so its `deploy-backend` was skipped.** Re-running `deploy-backend` alone keeps the failed job's result and skips again. For a flake, use "Re-run failed jobs" on that run. For a real break, land a fix or a revert on main; its own run deploys if it changes deployable files. A fix confined to `backend/tests/` deploys nothing, so the batch waits for the next deployable merge.
   - **The deploy failed or was cancelled before "Deploy Cloud Run service".** Re-run that run's `deploy-backend`: its commit carries every change before it.
   - **It failed after traffic moved** (a job-image update or "Verify health"). The newest image is serving. If the image is bad, a re-run ships it again: roll back by traffic (rule 4) and revert on main.
6. **A run from before the guard has no guard.** Each run uses the `ci.yml` of its own commit, and GitHub lets a run be re-run for 30 days after it first ran. Never re-run a pre-guard run whose commit main has moved past with deployable backend changes: it would deploy the older commit. Re-running the newest deployable commit's run is safe either way, as no newer deployable commit is on main.

**Evidence.**
- **The gate.** `.github/workflows/ci.yml`, `deploy-backend` → "Detect backend changes". Gated by `backend/tests/unit/test_backend_deploy_scope.py`:
  - the stubbed path cases, superseded and not, with main read only after a deployable change, by its full ref, and the skip's notice;
  - each failed read of main (the fetch, three times; the tip; the diff), which fails the step with no decision written;
  - in real git, in workspaces made as `actions/checkout` makes them: the three-merge order, newest deploying first; a runtime file main moved under `backend/tests/`; a tag named `main` on origin; and an unreachable origin with the checkout's own `FETCH_HEAD` left in place.
- **The incident.** The verification and incident record, comment 6548630313 on #1848; runs 41235496493 (cancelled), 41235514263 (`6cf4efa`'s deploy) and 41235529857 (attempt 2, the re-deploy of `b994da4`).
- **What is review-checked.** No gate sees these operator steps:
  - batching only under the founder's approval;
  - reading a commit as deployed from its own migration line or a newer deploy's (rule 2);
  - waiting for verification before the next backend merge, and recording the skips (rule 3);
  - rolling back by traffic or a revert, not a re-run (rule 4);
  - choosing what to re-run or fix when the newest run deploys nothing (rule 5);
  - not re-running a superseded pre-guard run (rule 6).
