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

Scheduler retry config, inspected on all seven: min backoff 5 s, max backoff 3600 s, max doublings 5, unlimited retry duration (`maxRetryDuration=0s`), no explicit retry count; the scheduler only starts the job, so the job's own three retries govern outcome. Overlap: Monday 06:00 UTC starts pregenerate and the hourly filing-scan together (filing-scan executions today ran 20–37 s each, succeeded 1/1); the 06:00 New York alert and 05:30 calendar jobs fall at 09:30–10:00 UTC. No scheduler for backfill-facts exists; its runs are manual.

## Cloud SQL

Live instance `earningsnerd-db`: Postgres 15, `db-f1-micro`, zonal, us-west1, 10 GB disk, IAM authentication on, **automated backups and point-in-time recovery disabled**, created 2026-06-11. No `max_connections` flag is set, so the tier default applies (Cloud SQL documents 25 for `db-f1-micro`; not measured here). Seven-day Monitoring reads (hourly aggregation, 168 samples each): peak connections 13 (p95 12, median 4; peak hour ending 2026-09-14T18:59Z), CPU mean about 10% (hourly max peak 54.5%), memory utilization reported as 1.0 throughout, which on this shared-core tier reflects the page cache filling RAM rather than pressure.

Headroom reading for E09: the service is pinned to at most two instances (`--max-instances=2` in `ci.yml`) at up to 20 connections each (`DB_POOL_SIZE=12`, `DB_MAX_OVERFLOW=8`), so 40 configured before any job; each job adds 5 (`3+2`). The scheduled Monday 06:00 UTC overlap (service plus pregenerate and filing-scan) is therefore configured at 50, and a manual backfill run at the same time would make a hypothetical 55, both above the tier default of 25; the observed seven-day peak is 13. This matches the retained E09 package's 40-before-jobs budget and is a design constraint for any fleet, not an observed incident.

A second instance, `earningsnerd` (Postgres 18, `db-g1-small`, us-central1, created 2026-02-04), is `STOPPED` with activation policy `NEVER`. It serves nothing and costs its 10 GB disk. Deleting it is a destructive founder decision; it is only recorded here.

## Analysis warm-up evidence

The wave-3 plan's warm-up is `scripts/sync_companyfacts.py` on the seeded cohort, with deployment id, cohort and success/error counts as the evidence. No Cloud Run execution has run that script: the `earningsnerd-backfill-facts` job's four September 8 executions (05:24, 05:29, 09:32, 09:44 UTC; 18–52 s; succeeded 1/1) were the W3-9 reconciliation audit and listing recorded in `tasks/todo.md`, not the warm-up, and the job has not run since. Their Cloud Logging records carry only the startup `COOKIE_DOMAIN` warning and `Container called exit(0)`, so `backfill_facts.py`'s outcome line did not reach the log either; `backfill_facts.py` does persist a `track_job` record, but `sync_companyfacts.py` does not call `track_job`, so the database's job-outcome table cannot supply warm-up counters. The warm-up therefore remains pending until the named script is run (founder-executed, per the plan) and its logged counters are retained; nothing in this read is Analysis acceptance, and Pro frontend acceptance remains unperformed.

## Egress ownership (E09)

The service and every job run with Cloud Run's default internet egress: no VPC connector (the Serverless VPC Access API is not enabled on the project; the check's enable prompt was declined), no Cloud NAT router, no egress annotation, and only the built-in Cloud SQL connector to `earnings-nerd:us-west1:earningsnerd-db`; all run as the default compute service account. SEC therefore sees Google's dynamic egress addresses, not one fixed IP, so the 10 requests/s cap is not deterministically shared across instances and jobs; each process still carries its own limiter bucket (`lessons/arch-per-process-state-on-cloud-run.md`). Any fleet design that wants a single accountable SEC identity would need NAT, which is a founder capacity/cost decision.

Other SEC caller classes, as the E09 package requires them listed (`tasks/e09-proposal-next-2026-09-13.md`): (1) GitHub-hosted runners for `copilot-eval` (`evals.copilot_bootstrap` fetches filing metadata, documents and XBRL through the app's SEC transport), `eval-baseline` and `data-quality-weekly`, each a fresh process with its own limiter bucket on GitHub's dynamic Azure egress addresses, running only on PR events or dispatch; (2) manual and agent runs on the founder's Mac (for example this session's four 10-Q and fourteen 6-K acquisitions through the app transport), on the Mac's own address; (3) the eval harness's per-run SEC reads. None of these shares an address with Cloud Run, so the SEC cap is met per process per address rather than by one shared identity; no caller uses a fixed IP. The remaining unread item for E09 is the database's persisted job-outcome table.

## Stripe webhook evidence (E06)

Thirty days of service logs (from 2026-08-16) contain exactly one webhook delivery: `POST /api/subscriptions/webhook` at 2026-08-18T22:39:56Z from 54.187.174.169, answered 200 in 159 ms on revision `00246-vbt`, which means `stripe.Webhook.construct_event` accepted the signature (a bad signature returns 400). Three `GET /api/webhook` probes and 121 startup lines (`Stripe webhook secret configured`) are the only other Stripe-related lines; the application logs nothing about the event type or its effect at INFO, so which event it was and whether it applied to a subscription is not visible in logs. No delivery has occurred since the `invoice_payment.paid` configuration approved on September 13, so the natural delivery/signature/application evidence E06 asks for is still outstanding; the August 18 delivery proves the endpoint and signature path only.

## Production AI calls, for the record

The service and every job made no provider call on September 13, 14 or 15 (`ai_call` lines: 0 from the structured service logger and 0 from the jobs' plain-text logs; the September 7 pregenerate calls match the same text filter). Raw reads are retained under `outputs/e09-readonly/` and `outputs/stall-window/` in the agent workspace.
