# Never let an older commit deploy after a newer one: `deploy-backend` skips a commit main has moved past with backend changes

Date: 2026-11-01 · Area: ops / deploy

**Context.** On 2026-10-31 Agent C's batch 1 merged back to back under the founder's approval of two or three PRs per deploy turn:
- #1848 at 19:42:45 UTC (`b4863c8`);
- #1863 at 19:43:00 (`6cf4efa`);
- #1713 at 19:43:12 (`b994da4`).

Each push ran its own CI and its own `deploy-backend`. Each deploy built and shipped its own commit's image, and routed all traffic to it. The `deploy-backend` concurrency group (`cancel-in-progress: false`, `queue: max`) runs waiting deploys in the order their runs reach the job, not in merge order:
- #1713's run, the newest commit, deployed first, at 20:11:54.
- #1863's older commit deployed next, at 20:14:52. Production then ran without #1713's backend changes.
- #1848's still older deploy waited last.

Agent E cancelled #1848's run (41235496493) before any deploy step ran. It then re-ran #1713's `deploy-backend` job (run 41235529857, attempt 2), which put `b994da4` back at 20:17:46. Production ran the older tree for about three minutes. Health checks stayed green throughout: a rollback like this one reads healthy.

**Rule.**
1. **The detector skips a superseded commit.** `deploy-backend`'s "Detect backend changes" step first finds this commit's deployable change. It then reads main's tip (`git fetch --no-tags --depth=1 origin main`) and applies the same path rule to `git diff HEAD <tip>`.
   - If main has moved past this commit with deployable backend changes, the deploy is skipped: that newer commit's own run deploys them.
   - If main has moved only with changes outside the image (frontend, records, `backend/tests/`), this commit still deploys.
   - A failed read of main fails the step, and nothing deploys.
2. **Back-to-back backend merges deploy once, as the newest commit.** Every older commit's deploy is skipped once the newer ones are on main. Verify that one deploy, and record the older runs' skips ("skipping this superseded deploy" in their detector logs). The next backend merge still waits for that verification (`AGENTS.md` §6, one unverified backend deploy at a time). Whether to batch at all stays the founder's call.
3. **Never roll back by re-running an old deploy.** A re-run of an older deploy job, after main has moved past it with backend changes, is skipped by rule 1. Roll back by moving traffic to a prior revision (`docs/DEPLOYMENT.md`, "Rollback"), or forward with a revert on main.
4. **A failed newest deploy is the one to re-run.** If an older deploy skipped as superseded and the newest run's deploy then fails or is cancelled, production keeps the image from before them all. Re-run the newest backend commit's `deploy-backend`: its commit carries every change before it.
5. **Runs on commits from before the guard don't have it.** Each run uses the `ci.yml` of its own commit, so a re-run of a pre-guard run can still deploy an older commit. Don't re-run those.

**Evidence.**
- **The gate.** `.github/workflows/ci.yml`, `deploy-backend` → "Detect backend changes". Gated by `backend/tests/unit/test_backend_deploy_scope.py`:
  - the stubbed path cases, superseded and not, with a fetch only after a deployable change;
  - the three-merge order in real git, newest deploying first;
  - the failed read of main, which fails the step.
- **The incident.** The verification and incident record, comment 6548630313 on #1848; runs 41235496493 (cancelled), 41235514263 (`6cf4efa`'s deploy) and 41235529857 (attempt 2, the re-deploy of `b994da4`).
- **What is review-checked.** Waiting for the deploy's verification before the next backend merge.
