# Read-only fleet, scheduler and database observations — September 15, 2026

Read with the founder's terminal `gcloud auth login` (September 15, project `earnings-nerd`). Every command was a describe, list, log read or Monitoring API read; nothing was invoked, changed or deleted. This extends the [September 14 observations](cloud-run-observations.md) and remains input to the E09 proposal, not a fleet decision.

## Cloud Run jobs (templates as deployed, image `backend:d39c3de`)

| Job | Tasks | Max retries | Task timeout | CPU | Memory |
|---|---:|---:|---:|---:|---:|
| earningsnerd-backfill-facts | 1 | 3 | 3600 s | 1 | 1 GiB |
| earningsnerd-earnings-calendar-refresh | 1 | 3 | 1800 s | 1 | 1 GiB |
| earningsnerd-earnings-day-alerts | 1 | 3 | 1800 s | 1 | 1 GiB |
| earningsnerd-filing-digest | 1 | 3 | 1800 s | 1 | 1 GiB |
| earningsnerd-filing-scan | 1 | 3 | 1800 s | 1 | 1 GiB |
| earningsnerd-notable-filings | 1 | 3 | 900 s | 1 | 1 GiB |
| earningsnerd-pregenerate | 1 | 3 | 3600 s | 1 | 1 GiB |
| earningsnerd-retention-purge | 1 | 3 | 1800 s | 1 | 512 MiB |

Every job is a single task with no parallelism; a scheduler-triggered run that fails is retried up to three times by Cloud Run itself. The deploy updates all eight images (the September 15 deploys moved them to `d39c3de`).

## Cloud Scheduler (all `ENABLED`, all `POST …/jobs/<job>:run`, attempt deadline 180 s)

| Scheduler | Schedule | Zone | Last attempt |
|---|---|---|---|
| filing-scan-hourly | `0 * * * *` | UTC | 2026-09-15T06:00:02Z |
| earningsnerd-pregenerate-weekly | `0 6 * * 1` | UTC | 2026-09-14T06:00:02Z |
| notable-filings-scan | `30 8,18 * * *` | America/New_York | 2026-09-14T22:30:01Z |
| filing-digest-daily | `0 8 * * *` | UTC | 2026-09-14T08:00:01Z |
| retention-purge-weekly | `0 3 * * 0` | UTC | 2026-09-13T03:00:00Z |
| earnings-day-alerts-daily | `0 6 * * *` | America/New_York | 2026-09-14T10:00:05Z |
| earnings-calendar-refresh-daily | `30 5 * * *` | America/New_York | 2026-09-14T09:30:05Z |

Scheduler retry config on the three inspected: min backoff 5 s, max backoff 3600 s, max doublings 5, unlimited retry duration; the scheduler only starts the job, so the job's own three retries govern outcome. Overlap: Monday 06:00 UTC starts pregenerate and the hourly filing-scan together (filing-scan executions today ran 20–37 s each, succeeded 1/1); the 06:00 New York alert and 05:30 calendar jobs fall at 09:30–10:00 UTC. No scheduler for backfill-facts exists; its runs are manual.

## Cloud SQL

Live instance `earningsnerd-db`: Postgres 15, `db-f1-micro`, zonal, us-west1, 10 GB disk, IAM authentication on, **automated backups and point-in-time recovery disabled**, created 2026-06-11. No `max_connections` flag is set, so the tier default applies (Cloud SQL documents 25 for `db-f1-micro`; not measured here). Seven-day Monitoring reads (hourly aggregation, 168 samples each): peak connections 13 (p95 12, median 4; peak hour ending 2026-09-14T18:59Z), CPU mean about 10% (hourly max peak 54.5%), memory utilization reported as 1.0 throughout, which on this shared-core tier reflects the page cache filling RAM rather than pressure.

Headroom reading for E09: the service alone can hold up to 20 connections per instance (`DB_POOL_SIZE=12`, `DB_MAX_OVERFLOW=8`) and each job 5 (`3+2`); the observed peak of 13 is well inside 25, but a Monday 06:00 UTC overlap of the service with pregenerate, filing-scan and a manual backfill (35 configured) would exceed the tier default. That is a design constraint for any fleet, not an observed incident.

A second instance, `earningsnerd` (Postgres 18, `db-g1-small`, us-central1, created 2026-02-04), is `STOPPED` with activation policy `NEVER`. It serves nothing and costs its 10 GB disk. Deleting it is a destructive founder decision; it is only recorded here.

## Analysis warm-up (companyfacts backfill) evidence

`earningsnerd-backfill-facts` last ran four times on September 8 (05:24, 05:29, 09:32, 09:44 UTC; 18–52 s each, all succeeded 1/1) and not since. The latest execution's Cloud Logging record contains only the startup `COOKIE_DOMAIN` warning and `Container called exit(0)`; the script's own outcome line (`Facts backfill complete: …`, `scripts/backfill_facts.py`) is absent, so the log carries no cohort, count or error evidence. Either the job's INFO output does not reach Cloud Logging under the script's logging setup or those runs processed nothing; the read-only evidence cannot say which. The Analysis warm-up cohort/count/error evidence the plan asks for therefore still does not exist in logs; the persisted job-outcome record (`lessons/ops-job-success-needs-outcome-evidence.md`) is in the database and was not read (no database access from this session). Pro frontend acceptance remains unperformed.

## Production AI calls, for the record

The service and every job made no provider call on September 13, 14 or 15 (`ai_call` lines: 0 from the structured service logger and 0 from the jobs' plain-text logs; the September 7 pregenerate calls match the same text filter). Raw reads are retained under `outputs/e09-readonly/` and `outputs/stall-window/` in the agent workspace.
