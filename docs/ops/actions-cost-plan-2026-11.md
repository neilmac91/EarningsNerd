# GitHub Actions cost: where it goes and the plan to cut it (November 2026)

Written 2026-11-10 from the run and job history of 1–10 November 2026. All prices are GitHub's
list prices on that day: USD 0.006 a minute for the standard Linux runner, USD 0.002 for the 1-core
runner, USD 0.005 for the arm64 runner, USD 0.25 a GB-month for artifact storage
([runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing),
[Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
GitHub bills each job rounded up to a whole minute. "Billed minutes" below are computed that way
from each job's start and end time.

## Update, 11 November: public again, and the founder's brief

Late on 10 November the Actions budget reached USD 40 and GitHub stopped starting jobs. The
founder then made the repository public (about 23:35 UTC). A public repository's standard runners
and artifact storage are free, and its runners have 4 CPUs, so jobs start again and the bill stops
growing while it stays public. Everything below measures the private week and applies again the
day the repository returns to private.

The founder's brief of that night: make CI as economical as it can be on GitHub's own runners;
machines outside GitHub are not an option for now. The pull request that adds this file was
reworked to that brief. It now holds every step of the plan that needs no outside machine and no
change to the site, and "The plan" lists what is left.

## Summary

- The bill is real and matches the history: 43,665 billed minutes, USD 261.99, against GitHub's
  USD 261.67 gross for the same ten days.
- `ci.yml` is 94% of it. One CI run cost about 57 billed minutes while the repository was public
  and costs about 112 since it went private on 3 November, because a private repository's runners
  have 2 CPUs where a public one's have 4. A run still takes about 25 minutes of waiting, so the
  change shows only on the bill.
- A pull request ran CI about 3.6 times before it merged and once more on `main` after. At
  private-repository prices a merged pull request cost about USD 2.95 of Actions.
- At the pace of 1–3 November (182 CI runs a day, 36 merges a day), a private month costs about
  USD 3,300. The pull request cuts that by about two thirds, to about USD 1,100, and a merged
  pull request to about USD 0.91.
- That is still far above a USD 40 budget. USD 40 buys 6,667 minutes, which is 6 billed minutes
  for the whole life of each pull request; the backend tests alone take 23 for one run. On
  GitHub's runners a private repository reaches USD 40 only in a month with few pull requests.
  While the repository is public, Actions cost nothing.

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

Each change is one revert away from undone. Savings are for a private month at the 1–3 November
pace. No required check is removed, and none changes what it tests when it runs.

| Change | Saves a month | Risk it adds | What still catches a problem | Undo |
|---|---:|---|---|---|
| **A draft's push runs no test job.** `ci-scope` reads the pull request's live draft flag. The ready mark starts the run that tests the head, and each push while ready runs it again | 258,000 min, USD 1,550 | CI no longer tests a draft. A failure the local gates miss shows only after the ready mark, where a second push also repeats the paid evaluation | The full suite runs on the ready pull request before any merge. `e2e-tests` fails on a draft on purpose, so a draft never shows every required check green and a ready mark whose run GitHub never started cannot merge untested | Remove the three test jobs' `if:` and `e2e-shard`'s draft condition |
| **A merge that deploys nothing runs no test job on `main`.** A push that changes `backend/` outside `backend/tests/` still runs every job, and they still gate `deploy-backend`. A nightly run tests `main`'s tip unless a completed run already tested that commit, and opens an issue when a job fails | 60,000 min, USD 360; the nightly run costs up to USD 20 back | A break that only shows when two merges meet is found by the next pull request's run or the nightly run, not within the half hour. Vercel had deployed such a frontend merge either way | The pull request's own run on its merge with `main`; the nightly run; the daily production smoke test. The scope's rule for a push that deploys is held to `deploy-backend`'s own by a test | Drop the `push)` case in `ci-scope` and the `schedule:` trigger |
| **Browser jobs skip a change that cannot affect them**: records (as before), and `backend/` and `ops/` files other than the three the frontend reads | 45,000 min, USD 270 on the runs that still test | A browser check starts to read a backend file that is not on the list | A test scans the frontend for every path that leaves `frontend/` and fails until the scope runs the browser jobs for it; an unknown scope runs everything | Revert the browser case in `ci-scope` |
| **Jobs that run seconds of shell use the 1-core runner**, a third of the price: `ci-scope`, `secret-scan`, `e2e-tests`, the nightly report, and a browser leg that has nothing to run | About USD 50 | The runner stops a job at 15 minutes and runs no containers | A test holds those limits; the jobs fail closed. All three fixed jobs passed on it in run 42924687021 | Change the `runs-on` lines |
| **Time limits** on the four CI jobs that had none (50, 40, 20 and 45 minutes) | Caps a hang at USD 0.30, not 2.16 | A very slow runner could hit a limit | Limits are about twice the usual time; re-run | Remove the lines |
| **`copilot-eval` artifacts kept 30 days**, not 90 | About USD 8 of storage | Evidence older than 30 days is gone unless downloaded | The run page keeps the readable report | Remove the line |

An earlier version of the pull request stopped the ready mark from starting a CI run. That is
gone: with drafts untested, the ready mark's run is the one that tests the head.

Modelled together, the changes take an active private month from about 549,000 billed minutes
(USD 3,300) to about 182,000 (USD 1,100). The model keeps each pull request's pushes as they
were; it cannot know how many more pushes a ready pull request will need now that drafts are
untested.

What a run costs after the pull request, in standard-runner minutes:

| Run | Before | After |
|---|---:|---:|
| A push to a draft | 112 | 2 |
| A ready pull request that changes the frontend | 112 | 110 |
| A ready pull request that changes only backend, `ops/` or records | 112 | 47 |
| A merge to `main` that deploys the backend | 112 | 47 to 110 |
| A merge to `main` that deploys nothing | 112 | 3 |

## The plan: what is left

Ordered by saving against risk. Dollar figures are for an active private month after the pull
request, at GitHub's price. They overlap, so they do not add up.

| # | Step | Saves a month | Risk | What still catches a problem | Effort | Undo |
|---|---|---:|---|---|---|---|
| 1 | **Delete the stored `copilot-fidelity-*` artifacts older than 30 days.** Founder approval. Free while the repository is public; do it before a return to private. | USD 10–13 | Old evaluation evidence is gone | Download first what an open audit needs | Minutes | Not possible |
| 2 | **Dependabot version updates monthly, not weekly.** The public `/security` page says the dependencies are checked every week, `legalTruth.spec.tsx` holds `dependabot.yml` to that sentence, and a change to the page's text needs a dated row in the legal ledger on the day it merges. So it is a small pull request of its own. | About USD 15 | Non-security updates arrive up to a month later | Security updates do not follow the schedule | An hour | Revert both |
| 3 | **Try the arm64 runner** (17% cheaper) on `frontend-tests` and the browser jobs. Measure speed and a week of results first; keep `backend-tests` on the CPU type production runs. | Up to USD 110 | Browser tests that measure layout may differ with the runner image's fonts | The same tests; `deploy-backend` still builds and health-checks the amd64 image | Half a day, then a week's watch | Change `runs-on` back |
| 4 | **Make the suites faster.** Browser: six chart specs take 22 of the 48 minutes. Backend: about 40 tests each scan the whole repository (5–24 seconds each); share one parsed copy. Frontend: vitest reports 31% of its time importing the same modules again for each of 362 files and 21% starting a browser-like environment for each. | Unknown until profiled; 20% would be about USD 180 | Low if the tests' assertions stay; sharing state between test files can hide a failure | The same tests | Days | Revert |
| 5 | **Review gate.** Stop a runner waiting up to 20 minutes for Codex: fail fast and re-run when the review arrives, on the 1-core runner. The gate's workflow runs from `main`, so a pull request cannot test a change to it, and a mistake there blocks every merge, its own repair included. | About USD 50 | A broken gate needs the founder to lift the ruleset | The gate fails closed | 1 day, high tier, with the founder present | Revert |
| 6 | **Machines outside GitHub**, when they become an option. A runner service lists a 2-CPU runner at about a fifth of GitHub's price (Ubicloud, USD 0.00125 a minute). A self-hosted server suits a private repository only: on a public one a pull request from a fork can run code on it. | Most of what is left | The code and the test jobs run on a third party's machines. GitHub postponed a USD 0.002-a-minute fee on such runners; it may return | Checks are unchanged; only where they run changes | An hour for a service | Change `runs-on` back |

Smaller items, not worth a step of their own: `eval-baseline` bills one minute on every pull
request to find that it has nothing to do; `data-quality-weekly.yml`'s `report` job and
`refresh-index-membership.yml` have no time limit; Lighthouse uploads its reports to public
temporary storage.

## Projected cost of a month

| | Active month (1–3 November pace) | Quiet month (5–10 November pace) |
|---|---:|---:|
| Public repository | USD 0 | USD 0 |
| Private, before the pull request | USD 3,300 | USD 160 |
| Private, after the pull request | about USD 1,100 | about USD 90 |
| Private, after steps 1 to 5 as well | about USD 800 | about USD 65 |

The quiet month before the pull request is the bill's own USD 5.34 a day for 5–10 November,
storage included; after it, the same six days' runs re-priced under the new rules. A private repository on GitHub's runners meets a USD 40 budget only in a month
quieter than that one.

## What to change in GitHub settings

1. **Decide the budget's amount before the repository returns to private.** The Actions budget
   reached USD 40 on 10 November at about 23:21 UTC, and it is set to stop usage. For about a
   quarter of an hour GitHub started no job in the account ("The job was not started because an
   Actions budget is preventing further use"): no CI, so no merge; no `deploy-backend` (it did
   not start on `main`'s run 42918680435, whose commit had nothing to deploy); no review gate.
   Making the repository public ended that, because a public repository's usage is free. A
   return to private in November stops every job again, the daily production smoke test
   included, unless the budget is raised first (Settings → Billing and licensing → Budgets and
   alerts).
2. **Approve deleting the old `copilot-fidelity-*` artifacts** (step 1 above).
3. **Set the repository's artifact and log retention to 30 days** (repository Settings → Actions →
   General). It covers every upload that names no retention of its own.
4. **While the repository is public**: keep "Require approval for all outside collaborators" on
   for workflows from forks (Settings → Actions → General), and turn on secret scanning and push
   protection, which are free for a public repository (Settings → Code security).
5. **Merge or close the open Dependabot pull requests together.** On a private repository each
   one costs two runs.
6. **To read billing through the API**, a session needs a token with the account permission
   "Plan: read" (`GET /users/{username}/settings/billing/usage`). The review's token was bound
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
