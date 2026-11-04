# When every CI job slows at once, read the runner before calling a cancellation a flake, and size a time-limited job to the runner it now gets

Date: 2026-11-04   Area: ops / CI

**Context**: The founder made the repository private on 2026-11-03, at about 23:25 UTC, on purpose ("i intentionally
switched the repo to private", 2026-11-04). GitHub-hosted runners for a private repository have 2 vCPUs where a public
one's have 4, and from that minute every CI job ran at about half its pace:
- pytest-xdist made 2 workers instead of 4, and the backend suite took 24 minutes instead of 13;
- the frontend unit suite took 23 minutes instead of 9;
- Playwright ran one worker instead of two, so the browser suite needed about 40 minutes against `e2e-tests`' 35-minute
  limit (F59).

Every e2e run that was not records-only was then cancelled at the limit with no test failed: #1990, #1994, #1996,
#1997 and #2000 among them. Two reads went wrong on the way:
- the first read of #1994 called its first cancellation a slow runner, and spent the one re-run;
- the second inferred from record 76's "Repository is intentionally public" that the change might be an accident, and
  asked the founder to undo it or work around it. The founder had made it on purpose.

**Rule**:
- When jobs slow together across unrelated pull requests, read the worker counts the logs print (pytest-xdist's
  `created: N/N workers`, Playwright's `Running N tests using N worker`) and the repository's visibility before anything
  else. A halved count is the runner, not the code and not a flake.
- A record of a setting (visibility, plan, runner) is a dated observation. When the setting changes, ask the founder
  what they intend before calling the change a mistake.
- Size a time-limited job to the runner it now gets by splitting it, never by assuming the old pace. CI's browser suite
  runs in `e2e-shard`'s matrix, each shard under F59's 35-minute limit, and `e2e-tests`, the required check, passes only
  when every shard passed. A shard that nears 30 minutes takes another shard: the run step reads the shard count from
  the matrix, and `backend/tests/unit/test_ci_cost_controls.py` pins both.

**Evidence**:
- `.github/workflows/ci.yml`: the jobs `e2e-shard` and `e2e-tests`.
- `backend/tests/unit/test_ci_cost_controls.py`: `test_each_e2e_shard_keeps_the_founders_35_minute_limit` and
  `test_browser_checks_report_records_and_reject_failed_or_missing_scope`.
- #1994, comments 6618727371 and 6619711164: the cancellations, the worker counts, and a local benchmark on 2 CPUs in
  which two Playwright workers ran 221 of the suite's tests in 6.7 minutes against one worker's 7.2.
- The shards' first runs on 2-vCPU runners: the pull request that added them, whose body gives each shard's time.
