# Run a required check that sums other jobs with `if: ${{ always() }}` and fail it unless they all passed

Date: 2026-11-04 · Area: ops / CI

**Context.** Since 2026-11-03 the repository's CI jobs have run on 2-vCPU runners, so Playwright ran one worker and
the browser suite needed about 52 minutes. Every `e2e-tests` run was cut at F59's 35-minute limit, which held every
pull request, and on main `deploy-backend`, which needs `e2e-tests`, would have skipped its deploy. The founder chose
shards on 2026-11-04 (#1990). A matrix job reports one check per leg (`e2e-shard (1)`, `e2e-shard (2)` and so on),
never the bare name the ruleset requires, so `e2e-tests` became a job that sums the shards.

GitHub reports a job skipped by its `if:` as passing a required check, and a job under
`if: ${{ always() && !cancelled() }}` skips on a cancelled run. A summing job that can skip can let a pull request
merge with a shard red or missing.

**Rule.**
1. A required check that sums other jobs runs with `if: ${{ always() }}`. Its one step fails unless the needed job's
   result is exactly `success`; failure, cancelled, skipped and an empty result all fail it.
2. Only the summing job needs the summed jobs. The deploy and any other gate need the summing job, so the result
   reaches them through one place.
3. A matrix of shards numbers its legs 1 to N on its only axis and passes `matrix.shard/strategy.job-total`, so the
   legs cover the whole suite. Each leg keeps the per-job time limit, and its failure artifacts carry its number,
   since a run holds one artifact per name.
4. Choose the shard count from measured time, not test counts. Playwright splits shards by test count, keeps a file
   whole unless it runs in parallel mode, and orders files by their worker settings, so a slow block of files can
   land in one shard.

**Evidence.**
- `.github/workflows/ci.yml`: the `e2e-shard` matrix and the `e2e-tests` job that sums it.
- Gates in `backend/tests/unit/test_ci_cost_controls.py`:
  - `test_e2e_tests_passes_only_when_every_browser_shard_passed` runs the summing step for each result and checks that
    only it needs the shards;
  - `test_the_browser_shards_cover_the_suite_and_keep_their_evidence_apart`;
  - `test_e2e_tests_keeps_the_founders_35_minute_limit`.
- The sizing, measured for #1990 on 2026-11-04:
  - one-worker runs had passed 960 of the 1,300 tests after 28.6 minutes when the limit cut them;
  - calibrated to that run (×1.29), the Nov 1 HTML report's per-test durations give a 52-minute suite, about 22
    minutes of it in the six chart-heavy specs, which run last;
  - `npx playwright test --list --shard=k/n` gave the worst shard, installs included, as 29.1, 27.5, 24.9, 21.4 and
    17.2 minutes for two to six shards. Five were chosen: six leave one shard 18 tests.
