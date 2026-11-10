# GitHub Actions cost: where it goes and the plan to cut it (November 2026)

Written 2026-11-10 from the run and job history of 1–10 November 2026. All prices are GitHub's
list prices on that day: USD 0.006 a minute for the standard Linux runner, USD 0.002 for the 1-core
runner, USD 0.005 for the arm64 runner, USD 0.25 a GB-month for artifact storage
([runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing),
[Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
GitHub bills each job rounded up to a whole minute. "Billed minutes" below are computed that way
from each job's start and end time.

## Summary

- The bill is real and matches the history: 43,665 billed minutes, USD 261.99, against GitHub's
  USD 261.67 gross for the same ten days.
- `ci.yml` is 94% of it. One CI run cost about 57 billed minutes while the repository was public
  and costs about 112 since it went private on 3 November, because a private repository's runners
  have 2 CPUs where a public one's have 4. A run still takes about 25 minutes of waiting, so the
  change shows only on the bill.
- A pull request runs CI about 3.6 times before it merges and once more on `main` after. At
  today's prices a merged pull request costs about USD 2.95 of Actions.
- At the pace of 1–3 November (182 CI runs a day, 36 merges a day), a month costs about
  USD 3,300 at today's runner speed. The pull request that adds this file cuts that by about a
  third, to about USD 2,200. That is still far above the USD 40 budget.
- No tuning of the workflow files reaches USD 40 at that pace. USD 40 buys 6,667 minutes, which
  is 6 billed minutes for the whole life of each pull request; the backend tests alone take 23
  for one run. Reaching the budget needs cheaper compute (a
  runner service or a self-hosted runner), fewer full runs for each pull request, or both. Those
  are decisions for the founder, listed under "The plan".

## Where the minutes go

By workflow, 1–10 November 2026:

| Workflow | Billed minutes | Share | Runs | What it is |
|---|---:|---:|---:|---|
| `ci.yml` | 41,151 | 94.2% | 664 | tests, browser tests, deploy |
| `review-gate.yml` | 1,976 | 4.5% | 2,355 | waits for the Codex review of a pull request |
| `copilot-eval.yml` | 215 | 0.5% | 174 | paid Copilot evaluation |
| `ops.yml` | 154 | 0.4% | 83 | manual production operations |
| `deepseek-balance.yml` | 88 | 0.2% | 77 | manual balance read |
| Dependabot's own jobs | 43 | 0.1% | 14 | |
| The four scheduled workflows | 38 | 0.1% | 14 | production smoke test, weekly and monthly jobs |

The export shows 40,000 minutes for `ci.yml`; the history gives 41,151, so the export rounds.
Of the 2,355 `review-gate.yml` runs, 1,101 are comment events that skip at once and bill nothing.

Inside one CI run, at the private repository's runner speed (5–10 November):

| Job | Billed minutes | Share of a run | Main cause |
|---|---:|---:|---|
| Browser tests (`e2e-shard`, 5 jobs) | 61 | 55% | 1,300 Playwright tests on one worker, 48 minutes; each of the 5 jobs also installs and builds, about 2 minutes |
| `backend-tests` | 23 | 21% | 22,000 pytest tests on 2 CPUs, 21 minutes |
| `frontend-tests` | 15 | 13% | 362 vitest files, 13 minutes |
| `migrations-postgres` | 4 | 4% | |
| `lighthouse` | 4 | 3% | advisory |
| `ci-scope`, `secret-scan`, `e2e-tests`, `eval-baseline` | 4 | 4% | seconds of work each, billed a full minute |
| **One full run** | **112** | | **USD 0.67** |

By what started the run (share of all CI minutes, 1–10 November):

| Trigger | Runs | Billed minutes | Share |
|---|---:|---:|---:|
| A push to a draft pull request | 329 | 16,723 | 41% |
| A pull request marked ready | 127 | 9,060 | 22% |
| A push to a ready pull request | 69 | 5,781 | 14% |
| A merge to `main` | 138 | 9,513 | 23% |

139 of these runs were cancelled by a newer push or a ready mark after they had already used
5,607 minutes (14%).

## The two hunches

**"CI on pull requests takes too long": confirmed.** A run bills about 112 minutes. It doubled on
3 November without getting slower to watch, because five browser jobs now run side by side on
slower machines.

**"Pull requests are reviewed too often": mostly rejected as a cost.** The review gate is 4.5% of
the minutes (about USD 12 in ten days). Of the 129 pull requests that were marked ready, 91 had no
commit after the mark, and the average was 0.5. The pushes happen before review, on drafts: 6.5
commits and 3.6 CI runs a pull request. Codex was asked for a review 153 times on 77 pull
requests; each request re-runs the gate for one minute. What review does cost is the 19 gate runs
that waited the full 20 minutes for a review that did not arrive (399 minutes).

## Other drivers

1. **The ready mark re-ran all of CI.** 127 runs, 9,060 minutes. 57 of them repeated a run that
   had already passed on the same commit (4,059 minutes). 61 cancelled a run that was in progress
   and started it again (1,167 minutes thrown away).
2. **Browser tests ran on changes that cannot affect them.** The browser jobs run the built
   frontend with no backend. 196 runs changed only backend, `ops/` and record files, and still
   spent 5,999 minutes on browser jobs.
3. **Every merge runs CI again on `main`.** 138 runs, 9,513 minutes. 86 of them deployed nothing.
4. **Dependabot.** 12 pull requests in ten days used about 2,500 minutes (PR runs plus `main`
   runs), about USD 55 a month at today's prices: more than the whole budget.
5. **Stored artifacts.** The repository holds 63 GB of artifacts. 818 of the 978 are
   `copilot-fidelity-*` from `copilot-eval.yml`, about 77 MB each, kept for GitHub's default of
   90 days. At USD 0.25 a GB-month that is about USD 15 a month, and it is the USD 0.49 a day
   that the bill shows on days with no runs.
6. **Jobs with no time limit.** `backend-tests`, `frontend-tests`, `lighthouse` and
   `eval-baseline` had none, so a hung job could run for GitHub's default of 6 hours (360
   minutes, USD 2.16). Nine jobs show more than an hour between start and end in these ten days,
   all on 1 November.

No workflow calls a paid AI review. Two call the DeepSeek API for evaluation, at about USD 0.73
(`eval-baseline`) and USD 0.06 (`copilot-eval`) a run by the repository's own records; that
spend is not on the GitHub bill.

## What the pull request with this file changes

Each change is one revert away from undone. Savings are for a month at the 1–3 November pace.

| Change | Saves a month | Risk it adds | What still catches a problem | Undo |
|---|---:|---|---|---|
| Browser jobs skip their steps when a change touches no file they read: records (as before), and now `backend/` and `ops/` files other than the three the frontend reads | 107,000 min, USD 640 | A browser check starts to read a backend file that is not on the list | `test_ci_cost_controls.py` scans the frontend for every path that leaves `frontend/` and fails until the scope runs the browser jobs for it; an unknown scope runs everything | Revert the `ci-scope` case in `ci.yml` |
| A ready mark starts only the paid `eval-baseline` job (`eval-baseline-ready.yml`), not a whole CI run | 79,000 min, USD 470 | None for the required checks: they are the ones the head's last push ran. A ready mark no longer works as a free re-run | The last push's run; a test holds the copy of the job equal to CI's | Add `ready_for_review` back to `ci.yml` and delete the new workflow |
| `ci-scope`, `secret-scan` and `e2e-tests` run on the 1-core runner | 8,700 min-equivalent, USD 50 | The runner stops a job at 15 minutes and runs no containers | A test holds those limits; the jobs fail closed | Change the three `runs-on` lines |
| Time limits on the four CI jobs that had none (50, 40, 20 and 45 minutes) | Caps a hang at USD 0.30, not 2.16 | A very slow runner could hit a limit | Limits are about twice the usual time; re-run | Remove the lines |
| `copilot-eval` artifacts kept 30 days, not 90 | About USD 8 of storage | Evidence older than 30 days is gone unless downloaded | The run page keeps the readable report | Remove the line |

Modelled together, the first three changes take an active month from about 549,000 billed
minutes (USD 3,300) to about 370,000 (USD 2,220).

## The plan beyond this pull request

Ordered by saving against risk. Dollar figures are for an active month after this pull request,
at GitHub's price unless the row says otherwise. They overlap, so they do not add up.

| # | Step | Saves a month | Risk | What still catches a problem | Effort | Undo |
|---|---|---:|---|---|---|---|
| 1 | **Delete the stored `copilot-fidelity-*` artifacts older than 30 days.** Founder approval. | USD 10–13, at once | Old evaluation evidence is gone | Download first what an open audit needs | Minutes | Not possible |
| 2 | **Push in batches.** One push for each unit of work; no push while a run that will pass is in progress; put a review round's fixes in one push. | Up to 38,000 min, USD 230 | None | Unchanged | An agent rule | Drop the rule |
| 3 | **Run the heavy jobs on cheaper machines.** Founder decision. Either a runner service (Ubicloud lists a 2-CPU runner at USD 0.00125 a minute, about a fifth of GitHub's price; Blacksmith about USD 0.004) or one self-hosted server. Keep `deploy-backend`, the paid evaluation jobs and `review-gate` on GitHub's runners, so no production or provider credential leaves them. | USD 1,600 with a service at Ubicloud's price; nearly all of the bill with a self-hosted server, which costs about USD 50–100 a month itself | The code, and the test jobs, run on a third party's machines, or on a server you must patch and keep clean. GitHub postponed a USD 0.002-a-minute fee on such runners; it may return | Checks are unchanged; only where they run changes | Service: an hour. Server: a day, then upkeep | Change `runs-on` back |
| 4 | **Run only quick checks on drafts; run everything when a pull request is marked ready and on each push after.** Founder decision: it changes what a green draft means. The safe form makes the required checks fail on a draft, as `review-gate` already does, and needs the ready mark to start CI again. | About 109,000 min, USD 650 | A draft's CI no longer proves the full suite passes; agents rely on the local gate until the ready mark | The full suite runs before any merge, on the ready mark and on `main` | 1–2 days, high review tier | Revert |
| 5 | **If the jobs stay on GitHub: try the arm64 runner** (17% cheaper) on `frontend-tests` and the browser jobs, then `backend-tests`. Measure speed first. | Up to 58,000 min-equivalent, USD 340 | Tests run on a different CPU type than production (amd64) | `deploy-backend` still builds and health-checks the amd64 image | Half a day | Change `runs-on` back |
| 6 | **Batch the `main` run for merges that deploy nothing.** A merge that changes deployable backend code keeps its own full run, which gates the deploy. Other merges share one run every hour or two. | About 33,000 min, USD 200 | A break between two frontend merges shows up to two hours later. Vercel has deployed it either way, as today | The pull request's own run; the batched run; the daily production smoke test | 1 day, high tier | Revert |
| 7 | **Make the suites faster.** Browser: six chart specs take 22 of the 48 minutes. Backend: about 40 tests each scan the whole repository (5–24 seconds each); share one parsed copy. Frontend: vitest reports 31% of its time importing the same modules again for each of 362 files and 21% starting a browser-like environment for each. | Unknown until profiled; 20% would be 70,000 min, USD 420 | Low if the tests' assertions stay | The same tests | Days | Revert |
| 8 | **Review gate.** Stop a runner waiting up to 20 minutes for Codex: fail fast and re-run when the review arrives, on the 1-core runner. | About 8,000 min, USD 50 | A re-run that does not start leaves the gate red, never green | The gate still fails closed | 1 day, high tier | Revert |
| 9 | **Dependabot version updates monthly, not weekly.** Founder decision, because the public `/security` page says the dependencies are checked every week, and `legalTruth.spec.tsx` holds `dependabot.yml` to that sentence. The change is the schedule and the sentence together. | About 4,300 min, USD 26 | Non-security updates arrive up to a month later | Security updates do not follow the schedule | An hour | Revert both |

Smaller items, not worth a step of their own: `eval-baseline` bills one minute on every pull
request to find that it has nothing to do (about 1% of CI); `data-quality-weekly.yml`'s `report`
job and `refresh-index-membership.yml` have no time limit; Lighthouse uploads its reports of this
private repository's build to public temporary storage.

## Projected cost of a month

| | Active month (1–3 November pace) | Quiet month (5–10 November pace) |
|---|---:|---:|
| Today | USD 3,300 | USD 160 |
| After this pull request | USD 2,200 | about USD 110 |
| After the full plan, on GitHub's runners | about USD 1,100 | about USD 55 |
| After the full plan, heavy jobs on a runner service at Ubicloud's price | about USD 280 | about USD 20 |
| After the full plan, heavy jobs on a self-hosted server | about USD 60, plus the server | about USD 10, plus the server |

The quiet month is the bill's own USD 5.34 a day for 5–10 November, storage included.

The USD 40 budget holds in a quiet month once the heavy jobs leave GitHub's meter. In an active
month it holds only with a self-hosted server, whose own cost is on another bill.

## What to change in GitHub settings now

1. **The budget has stopped all usage; decide its amount.** The Actions budget reached USD 40 on
   10 November at about 23:21 UTC, and it is set to stop usage. Since then GitHub starts no job
   in this account ("The job was not started because an Actions budget is preventing further
   use"). That stops CI on every pull request, so nothing can merge; `deploy-backend` (it did not
   start on `main`'s run 42918680435, whose commit had nothing to deploy); the review gate; and
   the daily production smoke test. It lasts until the budget is raised or the month ends. Set
   an amount you mean, with alerts, in Settings → Billing and licensing → Budgets and alerts.
   This pull request's own CI run (42924151172) did not start for the same reason, so its
   checks need a re-run once jobs start again.
2. **Approve deleting the old `copilot-fidelity-*` artifacts** (step 1 above).
3. **Set the repository's artifact and log retention to 30 days** (repository Settings → Actions →
   General). It covers every upload that names no retention of its own.
4. **Merge or close the four open Dependabot pull requests together.** Each one costs two runs.
5. **To read billing through the API**, a session needs a token with the account permission
   "Plan: read" (`GET /users/{username}/settings/billing/usage`). This session's token is bound
   to the repository and could not read it.

## How the numbers were made

- The run list and every job of every run for 1–10 November 2026 (3,390 runs) came from the
  GitHub REST API. A job's billed minutes are its run time rounded up; a skipped job bills none.
- Pull request facts (pushes, ready marks, comments, changed files) came from the 150 pull
  requests updated since 1 November and their timelines.
- The monthly figures re-price the 546 CI runs of 1–3 November at the job times measured on
  5–10 November, then apply each change to the runs it would have affected. Other workflows are
  added at their 1–3 November rate. They are estimates of a month at that pace, not forecasts.
- A third-party price is that vendor's list price on 2026-11-10. Check it before relying on it.
