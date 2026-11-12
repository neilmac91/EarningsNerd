# Run the suites locally and mark the pull request ready to have CI run them: a draft's push tests nothing, and a draft never shows every required check green

Date: 2026-11-11 · Area: ops / CI

**Context.** From 2026-11-03 to 2026-11-10 the repository was private, and GitHub billed its Actions minutes: USD 261.67
gross for 1–10 November, 94% of it `ci.yml` (`docs/ops/actions-cost-plan-2026-11.md`). A pull request ran CI about 3.6
times before it merged and once more on main:
- pushes to drafts used 41% of CI's minutes, and the run a ready mark started used 22%, 57 of those 127 runs repeating a
  run that had already passed on the same commit;
- the run on main after each merge used 23%, and 86 of those 138 runs deployed nothing.

On 2026-11-10 the Actions budget stopped every job in the account, and the founder asked for CI to cost as little as it
can on GitHub's own runners ("for the moment, make things as economical as possible for me, while staying on Github").

**Rule.**
1. Run the local gates before every push (`CLAUDE.md`, "Commands"). A draft's push runs no test job in CI: `ci-scope`
   reads the pull request's live draft flag and writes `tests=false`, and `backend-tests`, `frontend-tests`,
   `migrations-postgres`, `lighthouse` and the browser shards skip. `secret-scan` still runs.
2. Mark the pull request ready to test it. The ready mark starts the first run that tests the head, and each push while
   it is ready starts another, about 112 billed minutes on a private repository: put a review round's fixes in one push.
3. Read a red `e2e-tests` on a draft as "not tested", not as a failure. GitHub counts a skipped job as passing a required
   check, so on a draft the shards skip as a whole job and `e2e-tests`, which always runs, fails. A draft therefore never
   shows every required check green, and a ready pull request whose run GitHub never started cannot merge untested. Never
   make a draft's checks all green: no `if:` on `e2e-tests`, no step-level skip of the shards on a draft, no softened sum.
4. A job skips only where `ci-scope` succeeded and wrote the exact value (`tests == 'false'`, `draft == 'true'`). A scope
   that failed, or wrote nothing or anything else, runs every job; an unreadable draft flag runs them too.
5. A push to main runs the test jobs only when it deploys the backend (a change under `backend/` outside
   `backend/tests/`), where they gate `deploy-backend`. Any other merge was tested as its pull request's merge commit and
   runs none. The nightly run (04:17 UTC) tests main's tip unless a completed push or nightly run already ran
   `backend-tests` on that commit, which it reads from the runs themselves, since GitHub can drop a scheduled run and a
   push can get no run at all; a failed job there opens the issue "Nightly CI on main failed". Hold `ci-scope`'s rule
   for a push that deploys to `deploy-backend`'s own: a push the scope calls idle skips the deploy.
6. Let a run you dispatched on a pull request's branch finish; never cancel it by hand. A run cancelled before
   `ci-scope` ends skips its test jobs, and those skips sit on the head beside the pull request's own results.

**Evidence.**
- `.github/workflows/ci.yml`: `ci-scope`'s `tests` and `draft` outputs, the test jobs' `if:`, `e2e-shard`'s, the
  `schedule:` trigger and `report-failure`.
- `docs/ops/actions-cost-plan-2026-11.md`: the measurements, and what each change saves.
- `lessons/ops-a-required-check-that-sums-other-jobs-never-skips.md`: why `e2e-tests` fails on a skipped shard.
- `lessons/ops-a-ready-mark-runs-ci-on-the-merge-commit-of-the-last-push.md`: 2026-11-04, when a ready mark and a merge
  each started no run.

**Gate**: `backend/tests/unit/test_ci_cost_controls.py` runs the scope step on real Git histories with a stubbed draft
flag (`test_a_draft_runs_no_test_job_and_the_ready_pull_request_runs_them`), holds a push's rule to the deploy job's
(`test_a_push_to_main_runs_the_test_jobs_exactly_when_it_deploys`), pins the job conditions and the draft's red
`e2e-tests` (`test_a_draft_never_shows_every_required_check_green`), runs the nightly rule against stubbed runs
(`test_the_nightly_run_tests_main_unless_a_run_already_tested_its_tip`), and runs the nightly report's step
(`test_the_nightly_run_reports_a_failed_job_in_an_issue`). Running the local gates before a push, one push for a
review round, and rule 6 are review-checked.
