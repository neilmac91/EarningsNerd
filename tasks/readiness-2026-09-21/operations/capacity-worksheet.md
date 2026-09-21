# E09 capacity worksheet — 2026-09-21

Inputs are the retained [2026-09-19 live runtime](../../review-evidence/fleet-2026-09-19/e9-live-runtime.json), [read-only DB receipt](../../review-evidence/fleet-2026-09-19/iam-read-evidence.md), and [E09 decision package](../../fleet-coordination-proposal-2026-09-19.md). This is a configured-demand envelope, **not** measured concurrent connections or an invitation capacity claim. Backups/PITR subsequently changed; no capacity setting changed. The copied 2026-09-20 [observation](observations-2026-09-20.json) still shows the same protection state and no fleet evidence.

| Input | Retained value | What it means |
| --- | ---: | --- |
| Cloud SQL `max_connections` | 25 | Observed directly in the bounded IAM transaction. |
| Service min/max instances | 1 / 2 | `earningsnerd-backend`, concurrency 40 requests per instance. Effective workers assumed one until read back from deployed container. |
| Service SQLAlchemy pool/overflow | 12 / 8 | Up to 20 configured DB connections **per engine/process**. Pool slots are a cap, not all currently open. |
| Eight Cloud Run jobs | taskCount 1 each | Each has pool/overflow 3 / 2, up to 5 connections per process. `parallelism` missing in inventory is unknown, not zero. Retries up to 3, so overlapping executions must be observed. |
| Historical hourly aggregate peak | 13 | September 15 receipt; aggregation hides instantaneous peaks and predates the protection operation. |

Let `I` = simultaneous service instances, `P` = engine processes per instance, `J` = simultaneous job task processes, `R` = connections reserved for admin/migrations/other clients, and `O` = overlapping rollout/old-revision engines not counted in `I`. Configured possible demand is `20 × (I × P + O) + 5 × J + R`, against a 25-connection server cap. `R` must be positive and chosen from actual operational needs; no value has been approved. The ratio below deliberately leaves `R=0` and `O=0` to show how even an optimistic bound behaves.

| Scenario (`P=1`, `O=R=0`) | Configured possible demand | Gap to 25 |
| --- | ---: | ---: |
| 1 service instance, 0 jobs | 20 | +5 |
| 1 service instance, 1 job | 25 | 0 |
| 2 service instances, 0 jobs | 40 | -15 |
| 2 service instances, 2 jobs | 50 | -25 |
| 2 service instances, all 8 job tasks | 80 | -55 |

The 40 and 50 examples are already in the E09 proposal. The eight-job row is only a worst configured sum, not evidence that all run together. A rollout can temporarily add engines; multiple workers multiply pools. Pool timeout is 10 seconds by default (`backend/app/database.py`), so exhaustion can surface as errors before any fleet coordinator is built. Do not turn the historic peak 13 into 12 connections of safe headroom or infer that no exhaustion occurred.

## Evidence required to close the worksheet

1. Read deployed service/revision container command, worker count and concurrent old/new revisions; read each job's effective taskCount, parallelism and execution overlap. Capture representative instantaneous Cloud SQL connection counts/peaks, pool wait/timeout errors and request/job latency during the Monday 06:00 UTC pregenerate + hourly filing-scan overlap. Use a bounded observation window and record timestamp/resolution.
2. Obtain the already prepared [ledger query](../../review-evidence/fleet-2026-09-19/founder-readonly.sql) through an **existing principal with SELECT** on `public.earningsnerd_job_runs`. The previously used IAM identity received `permission denied`; do not retry it, grant privileges, read secrets or substitute Cloud Run exit 0 for useful-work counters. Reconcile succeeded/failed/dry-run/running with Cloud Run executions and flag never-observed jobs.
3. Choose an explicit admin/migration reserve `R`, then compare measured high-water connections plus credible service/job overlap and rollout allowance to 25. If the bound remains above 25, keep traffic at the current small beta envelope until an authorized capacity or workload change. A fleet lease would itself add short DB transactions and needs reserve.
4. For SEC, obtain actual egress identity and per-wire aggregate requests/bursts across service and jobs. The default local token bucket is 10 requests/s **per process**, not a fleet cap. No numeric fleet rate, burst or wait budget is supported by current evidence; see [outbound map](sec-outbound-attempts.md).

Record the final decision separately for Slice A ownership and Slice B SEC admission as [E09](../../fleet-coordination-proposal-2026-09-19.md) specifies. This worksheet authorizes neither implementation nor production tuning.
