# Read-only Cloud Run observation — September 14, 2026

Signed-in native Chrome, project earnings-nerd, us-west1. No job execution, configuration save, shell command, credential or permission change.

Inspected existing execution `earningsnerd-filing-scan-wm88t`: UI status Succeeded, one of one task completed; execution displayed September14 21:00:02–21:00:33, task21:00:14–21:00:32, exit0/retries0 (console local display, UTC+2 context). The visible preceding hourly rows also reported Succeeded; this is a bounded page, not all historical runs.

Its execution Containers view showed tasks1, parallelism1, timeout30min, maximum retries3, CPU1, memory1GiB; `python scripts/filing_scan.py`; image digest `sha256:4433fbc9cd35b23141a156cd7edd48f0288f3d516c0b82f7f07f7df67c60feac`; safe numeric environment rows DB_POOL_SIZE3/DB_MAX_OVERFLOW2. This is the inspected execution configuration, not an assertion about a subsequent job-image update.

Job Triggers view links scheduler `filing-scan-hourly`, schedule `0 * * * *`, timezone Etc/UTC, region us-west1. Scheduler state and retry policy were not yet read; recent execution alone does not prove current scheduler state.

The same console overview still lists another service `earningsnerd` in us-central1. Its chart legend value was1, but this does not establish ownership, served traffic, database use or safe capacity. Those remain unverified.

## Existing pregenerate execution

The Jobs history also shows `earningsnerd-pregenerate-xzsgm` Succeeded on September14, displayed08:00:02–08:00:40 (local UTC+2 context), one of one task completed. Containers: tasks1, parallelism1, timeout1hour, maximum retries3, CPU1, memory1GiB, DB_POOL_SIZE3/DB_MAX_OVERFLOW2; same image digest4433fbc9… as the inspected filing-scan execution. Command is `python scripts/pregenerate_examples.py`, no extra arguments. Safe flags shown include NOTABLE_FILINGS_ENABLED=false and CALENDAR_INDEX_FILTER_ENABLED=false.

The repository script, byte-identical between the recorded deployment source812a49d3 and current main, defaults to eight homepage tickers and force=false, skips already-cached summaries, and resolves annual/quarterly examples. It is not the universe-wide workload. Actual generated-versus-cached counts were not read, so this observation does not claim zero model calls or approve a replay. The weekly job was already scheduled and was not invoked by this session. Earlier September13's last-execution date is superseded by this read-only observation, not rewritten.

## Existing backfill job history (read-only, September 14)

The latest listed execution, `earningsnerd-backfill-facts-hqj8p`, succeeded on September 8, 11:44:11–11:44:31 CEST, one task with exit 0. Its task logs are a readout of `total_liabilities` rows, ending with `rows: 78`, `since: 2026-09-08T05:25:00Z`, `until: 2026-09-08T05:40:00Z`, and `Container called exit(0)`. This is historical liability-audit evidence, not a newly completed companyfacts warm-up or a cohort-wide acceptance count. No execution was started. The startup COOKIE_DOMAIN warning belongs to that historical job; it does not establish the current web service's cookie configuration.
