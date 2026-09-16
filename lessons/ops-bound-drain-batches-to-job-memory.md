# Bound a regeneration batch by the job container's memory, not by its time budget alone

Date: 2026-09-16   Area: ops

**Context**: The first D4 drain (`scripts/refresh_stale_summaries.py --execute --limit 48
--max-seconds 2400` on the 1 GiB pregenerate job, execution `earningsnerd-pregenerate-wf8mv`)
was killed by the container's out-of-memory event after 22 sequential regenerations at six
minutes, far inside its time budget. Cloud Run retried the task, the retry drained the remaining
26 rows in 434 seconds, and the killed attempt left a `running` row in `earningsnerd_job_runs`.
Memory grows across generations in one process (fetched documents, XBRL, excerpt caches); the
scheduled pregenerate run of about sixteen filings had never reached the limit.

**Rule**: Size a sequential-regeneration execution by the job's memory: on the 1 GiB job keep
`--limit` at or below 15 per execution and repeat executions, however generous the time budget.
Read `status.retriedCount` and the container's log for "Out-of-memory event" after every
execution before reading the JSON result, because the retry's result line reports only the
retry's own attempt, and treat a `running` ledger row as the signature of a killed attempt.
Raising the job's memory is a founder capacity decision.

**Evidence**: execution `earningsnerd-pregenerate-wf8mv` logs 16:17:30Z "Out-of-memory event
detected in container", 16:17:31Z "Container terminated on signal 9", retry result
`{"attempted": 26, "updated": 25, "kept_by_gate": 1}`; `scripts/refresh_stale_summaries.py`
`DEFAULT_LIMIT`; `docs/OPERATIONS.md` "Version-stale summary drain (D4)".
