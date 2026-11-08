# When every CI job slows at once, read the runner and the repository's settings before calling a cancellation a flake, and ask before calling a setting's change a mistake

Date: 2026-11-04 · Area: ops / CI

**Context.** The founder made the repository private on 2026-11-03, at about 23:25 UTC, on purpose ("i intentionally
switched the repo to private", 2026-11-04). GitHub's hosted runners have 2 vCPUs for a private repository where a
public one's have 4, and from that minute every CI job ran at about half its pace:
- pytest-xdist made 2 workers instead of 4, and the backend suite took 24 minutes instead of 13;
- the frontend unit suite took 15 to 26 minutes instead of 9;
- Playwright ran one worker instead of two, so `e2e-tests` was cut at F59's 35-minute limit, with no test failed, on
  every pull request that was not records-only: #1990, #1994, #1996, #1997 and #2000 among them.

Two reads went wrong on the way:
- the first read of #1994's cancellation called it a slow runner and spent the one re-run;
- the second took `tasks/todo.md`'s status line ("Repository is intentionally public") as standing, inferred that the
  change might be an accident, and asked the founder to undo it or work around it. The founder had made it on purpose.

**Rule.**
1. When jobs slow together across unrelated pull requests, read the worker counts their logs print (pytest-xdist's
   `created: N/N workers`, Playwright's `Running N tests using N worker`) and the repository's visibility before
   anything else. A halved count is the runner, not the code and not a flake, and a re-run spends itself on it.
2. A record of a setting (visibility, plan, runner, ruleset) is a dated observation. When the setting changes, ask the
   founder what they intend before calling the change a mistake, then correct the record in a records PR.
3. Size a time-limited job to the runner it now gets, from measured time:
   `lessons/ops-a-required-check-that-sums-other-jobs-never-skips.md` says how the browser suite's shards do it.

**Evidence.**
- #1994, comments 6618727371 and 6619711164: the two cancellations, the halved worker counts, and a local benchmark on
  2 CPUs in which two Playwright workers ran 221 of the suite's tests in 6.7 minutes against one worker's 7.2.
- #2002, closed for #1990: two shards' jobs took 28.9 and 30.1 minutes of the 35-minute limit on the 2-vCPU runners.
- #1990 (`78e129541`): five shards, each 11.7 to 14.7 minutes, the founder's choice on 2026-11-04.
- `tasks/todo.md`'s status line and F15 record the visibility since this lesson.
