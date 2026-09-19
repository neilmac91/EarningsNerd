# E9 decision package — prepared 2026-09-19

**Protection decision executed after this proposal was prepared:** the founder approved daily backups/seven retained copies and seven-day PITR, then selected “now, after active deployments finish.” Backup-settings operation completed2026-09-19T19:07:14.781Z; PITR restart completed19:16:01.014Z with no operation error. Effective settings are enabled=true, pointInTimeRecoveryEnabled=true,16:00 UTC window, retainedBackups7, transactionLogRetentionDays7, CloudStorage transaction-log storage. Initial on-demand backup1789845398872 is SUCCESSFUL at19:18:10.104Z. Post-restart detailed health is healthy and the same backend revision serves100%. See [retained receipts](review-evidence/fleet-2026-09-19/README.md). This verifies configured protection and a completed backup, not a restore drill. The fleet-coordination designs below remain proposals; no capacity, ownership or SEC limiter change was made.

The disabled-backup statements below describe the observation before that authorized change; this dated decision supersedes them.

Proposal only. The source design is unchanged from the September 19 dependency release. Current runtime configuration was read on 2026-09-19 at 18:58:48 UTC after the founder renewed gcloud. One bounded read-only IAM database transaction connected at 18:53:24 UTC, confirmed max_connections=25, then stopped because SELECT on earningsnerd_job_runs was denied. No production configuration, grants, jobs or application data were changed.

**Current decision:** retain the separated ownership and SEC-admission designs below. To complete job-outcome evidence, an existing identity with SELECT access must execute the attached [read-only SQL](review-evidence/fleet-2026-09-19/founder-readonly.sql). The current IAM identity cannot do so; logging in again or opening Studio under the same identity does not resolve the missing privilege. No privilege change is requested implicitly.

**Operational decision:** automated backups are disabled on the live earningsnerd-db instance and PITR is not enabled. Recommend enabling daily automated backups and seven-day PITR, followed by a separately scoped restore verification. This production setting requires founder approval. Enabling PITR on this existing instance restarts it, so approval must include a maintenance window; see [Google Cloud documentation](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/configure-pitr). Retain the existing16:00 UTC backup window and seven-backup retention unless the founder selects another window. No backup setting has been changed.

## Recommendation

Retain the two separate proposals: PostgreSQL generation ownership first; fleet SEC admission only after transport coverage and policy are specified. Do not increase capacity or activate either feature to collect evidence. The existing proposal can be completed offline to this decision-ready design and bounded read plan; the missing production outcomes and unresolved policy budgets must remain explicit before implementation approval.

Slice A uses one filing-keyed lease with database time, an opaque owner and monotonic fence. Claim, renewal and final ownership validation use short transactions; no connection is held over SEC/model work, semaphore waits or follower waits. Final insert/refresh and generation-owned cache publication validate ownership atomically, preserving Summary IDs, keep-better behavior and quota accounting. Audit earlier facts/cache writes individually. Fail closed for new generation if ownership is unavailable; serve an existing permitted result or the existing bounded error. This guarantees the accepted publisher, not exactly-once model execution after a paused owner/takeover. Do not set a lease duration before checking cleanup timing and provider limits.

Slice B uses one conservative shared admission domain through existing transport owners, retaining local pacing. Every actual HTTP attempt, including retries and SDK pagination, requires admission. Short database transactions return an eligible time; callers release connections before waiting. Expiring grants avoid sending stale permits after process pauses. Coordinator failure uses existing stale/valid fallbacks or honest job failure, not an uncoordinated burst. This is an admission guarantee; strict packet-departure timing would require a separately approved centralized dispatcher. No NAT, proxy, Redis, queue or database sizing change is bundled.

## Evidence and limits

- Current source still has process-local leaders and semaphores. `summary_pipeline.py` specifies a 120-second pipeline timeout and 110-second follower cap. `database.py` creates one sync SQLAlchemy engine per importing process. Docker launches uvicorn without an explicit multiworker argument. Effective deployed process/environment overrides still require confirmation; source is not live process evidence.
- September 19 live service configuration: min/max 1/2, concurrency 40, 1 vCPU, 1 GiB, pool/overflow 12/8, request timeout600s. No container command/argument override was returned. Revision earningsnerd-backend-00368-8jt serves100%; verify/gate remainfalse and evidence-snaptrue. At two instances and one process/engine each, configured pool demand is40, excluding rollout overlap and jobs. The earlier service-level max20 observation is historical and is not multiplied by revision max2.
- September 19 live inventory: eight jobs, taskCount1 each, retries3, timeouts900–3600s, pool/overflow3/2 each. Parallelism is omitted in the list representation; this does not mean zero. Seven schedulers are enabled. Filing-scan runs hourly, and pregenerate starts Monday06:00 UTC, so their schedules overlap; backfill-facts remains unscheduled in this inventory.
- September 19 IAM database transaction directly measured max_connections25. It was read-only with short transaction-local timeouts; these are read safeguards, not server defaults. The50-connection scenario (40 service + two jobs×5) exceeds the measured limit, but is configured demand rather than an observed incident. Retained September15 hourly-aggregated peak13 is historical and cannot establish instantaneous headroom. Automated backups remain disabled; no PITR-enabled value is returned. No capacity or backup setting was changed.
- September 15 egress configuration showed no fixed egress arrangement. Dynamic egress does not prove callers have independent IPs or that a per-process limiter meets the aggregate per-IP cap. The retained statement that none of these callers shares an address is stronger than the evidence supports; do not carry it into this proposal. No live public-IP collision/ownership measurement is available.
- A stopped Cloud SQL instance named `earningsnerd` in us-central1 is a database resource. It does not settle the separate Cloud Run service of the same name that the September 12/14 records leave unresolved.
- Healthy HTTP deployment proves serving health only. Historical Cloud Run `Succeeded`/exit 0 is not sufficient proof of meaningful generation/ingestion work. Pregenerate can successfully serve cached results; feature-disabled jobs can succeed with zero work. The ledger counters are required to distinguish these outcomes.

## The missing database evidence

Read only `public.earningsnerd_job_runs`: `job_name`, `started_at`, `finished_at`, `status`, `error_type`, numeric/boolean `counters` and optionally the operational attempt UUID to distinguish ties. No user, auth, billing, filing content or provider payload tables are needed. Capture database timestamp and actual max_connections in the same bounded snapshot.

For the eight job identities (pregenerate, filing-scan, filing-digest, backfill-facts, earnings-calendar-refresh, earnings-day-alerts, notable-filings, retention-purge), plus `data-quality-report`, obtain latest attempt, latest completed success, latest 20 attempts per identity, counts by status over the previous 14 days, and any still-running rows from that interval. Separately identify maintenance names (`refresh-stale`, `universe-company-seed`, `reconciliation-flag-audit`, `remediate-financials`, `backfill-company-sic`) so their outcomes cannot be mistaken for a scheduled job's success. Missing rows remain `never_observed`, not zero failures.

Interpret `succeeded` only with non-null completion; failed/dry_run/running rows never refresh last success. A running row with no finish may be a killed process, not a currently active execution. Compare timestamps and counters with retained Cloud Run executions, allowing wrapper startup differences. This schema contains no Cloud Run execution ID or deployed revision, so correlation by time is not exact attribution. A 20-row sample cannot prove all overlap; the 14-day aggregate and narrowly requested anomaly rows supplement it.

The application's `job_health` marks stale after twice the configured cadence. Its backfill-facts seven-day cadence is a reporting expectation; retained Scheduler evidence says that job is manual, so a stale result must not be presented as proof that a scheduler failed. `sync_companyfacts.py` does not call track_job: this table cannot certify the pending Analysis warm-up.

## Access route, without secrets or live jobs

Preferred: an already authorized Cloud SQL Studio session on project `earnings-nerd`, instance `earningsnerd-db`, database `earningsnerd`, using an existing IAM database identity with SELECT access. Google documents passwordless IAM login and separate required database permissions in [Cloud SQL Studio](https://docs.cloud.google.com/sql/docs/postgres/manage-data-using-studio?hl=en). Studio creates a new session on each execution: run the complete guarded SQL batch together. Do not grant roles, create users or retrieve a database password to make this work.

Alternative: reuse the existing Cloud SQL Auth Proxy route with automatic IAM database authentication and an existing IAM database user already authorized to SELECT the ledger. The founder has renewed the login; the completed connection proves authentication works, while the missing SELECT privilege remains the blocker. [Automatic IAM authentication](https://docs.cloud.google.com/sql/docs/postgres/iam-authentication) avoids retrieving the application's DATABASE_URL or database password. The successful read supplied short-lived gcloud access/login tokens only in the proxy child environment; no tokens were printed, placed on command lines or retained in artifacts. The proxy uses the known instance connection name `earnings-nerd:us-west1:earningsnerd-db`. Do not assume gcloud login and Application Default Credentials are interchangeable; verify the actual existing proxy credential mechanism without displaying credential contents. If no existing IAM DB principal/SELECT grant exists, authentication renewal alone will not unblock this route; return the exact access error for founder action.

Do not execute `data_quality_report.py --dry-run`: despite older OPERATIONS wording, it writes a dry-run ledger attempt through track_job. Do not dispatch the Ops data-quality-report action: it runs a live job and sends email. Existing Ops detection-sql reads Secret Manager DATABASE_URL and is restricted to its committed detection queries; it is not a secret-free generic database console. No public/admin read endpoint exposes the job ledger in the inspected router source.

The following batch was attempted through existing IAM. Its metadata query succeeded; the first job-table query failed for missing SELECT, so no job outcomes were returned. It is also supplied as a standalone Studio-ready file. Statement timeout is deliberately bounded; timeout is a missing observation, not justification to increase it automatically. If the table is absent or permissions fail, retain the error and stop. Querying this table creates normal database read/audit activity but does not mutate application rows.

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
SET LOCAL idle_in_transaction_session_timeout = '30s';
SET LOCAL TIME ZONE 'UTC';
SELECT transaction_timestamp() AS observed_at_utc,
       current_database() AS database_name,
       current_setting('max_connections') AS max_connections;

-- Latest and last successful attempt, preserving missing expected jobs.
WITH expected(job_name) AS (VALUES
 ('pregenerate'), ('filing-scan'), ('filing-digest'), ('backfill-facts'),
 ('earnings-calendar-refresh'), ('earnings-day-alerts'), ('notable-filings'),
 ('retention-purge'), ('data-quality-report'))
SELECT e.job_name, l.started_at AS latest_started_at,
       l.finished_at AS latest_finished_at,
       coalesce(l.status, 'never_observed') AS latest_status,
       l.error_type, s.finished_at AS last_success
FROM expected e
LEFT JOIN LATERAL (
 SELECT started_at, finished_at, status, error_type
 FROM public.earningsnerd_job_runs j WHERE j.job_name=e.job_name
 ORDER BY started_at DESC, id DESC LIMIT 1
) l ON true
LEFT JOIN LATERAL (
 SELECT finished_at FROM public.earningsnerd_job_runs j
 WHERE j.job_name=e.job_name AND status='succeeded' AND finished_at IS NOT NULL
 ORDER BY finished_at DESC LIMIT 1
) s ON true
ORDER BY e.job_name;

-- Latest twenty attempts per known identity; counters remain counts only.
WITH expected(job_name) AS (VALUES
 ('pregenerate'), ('filing-scan'), ('filing-digest'), ('backfill-facts'),
 ('earnings-calendar-refresh'), ('earnings-day-alerts'), ('notable-filings'),
 ('retention-purge'), ('data-quality-report'), ('refresh-stale'),
 ('universe-company-seed'), ('reconciliation-flag-audit'),
 ('remediate-financials'), ('backfill-company-sic'))
SELECT e.job_name, a.id, a.started_at, a.finished_at, a.status, a.error_type,
       (SELECT jsonb_object_agg(k, v)
        FROM jsonb_each(CASE WHEN jsonb_typeof(a.counters::jsonb)='object'
                       THEN a.counters::jsonb ELSE '{}'::jsonb END) AS c(k,v)
        WHERE jsonb_typeof(v) IN ('number','boolean')) AS numeric_counters
FROM expected e CROSS JOIN LATERAL (
 SELECT id, started_at, finished_at, status, error_type, counters
 FROM public.earningsnerd_job_runs j WHERE j.job_name=e.job_name
 ORDER BY started_at DESC, id DESC LIMIT 20
) a
ORDER BY e.job_name, a.started_at DESC, a.id DESC;

-- Aggregate actual identities, retaining maintenance names as separate rows.
SELECT job_name, status, count(*) AS attempts,
       min(started_at) AS first_started_at, max(started_at) AS last_started_at,
       max(finished_at) AS last_finished_at,
       count(*) FILTER (WHERE finished_at IS NULL) AS incomplete_attempts
FROM public.earningsnerd_job_runs
WHERE started_at >= transaction_timestamp() - interval '14 days'
GROUP BY job_name, status ORDER BY job_name, status;

SELECT job_name, id, started_at, status
FROM public.earningsnerd_job_runs
WHERE started_at >= transaction_timestamp() - interval '14 days'
  AND finished_at IS NULL
ORDER BY started_at LIMIT 200;
ROLLBACK;
```

## Founder decisions and completion status

Immediate access action: return the attached SQL results through an existing identity already authorized to SELECT public.earningsnerd_job_runs. The renewed gcloud/IAM path connected but returned exactly `permission denied for table earningsnerd_job_runs` and stopped (psql exit3). No new credentials, user grants, secret access, live jobs or security configuration changes are part of this request.

After outcomes and remaining capacity/latency/provider evidence are attached, decide Slice A: authorize PostgreSQL filing ownership with fail-closed new generation and an explicitly recorded bounded wait/renewal policy, or retain current process-only protection. This is a separate schema/runtime decision; the draft does not silently authorize activation. Establish an administration/migration connection reserve from actual limits and peaks before adding coordination load.

Decide Slice B separately: approved aggregate rate, burst/headroom and maximum wait/error tolerance; accept conservative admission semantics or request a separately priced hard-dispatch design. Dynamic egress is not a basis for assuming independent higher-rate domains. There is no supported numeric recommendation yet for provider quotas, lease TTL, reserve or SEC headroom.

Backups/PITR are the concrete operational decision stated above. The stopped database resource, unresolved extra service, Notable retain/kill, Analysis warm-up and production flag activation remain separate founder matters; no destructive cleanup is proposed.

Offline complete: source review, outcome semantics, exact bounded read specification, safe access alternatives, separated architecture/acceptance criteria and decision wording. Current runtime and the database connection limit are now verified. Live blocked: ledger outcomes, because the existing IAM database identity lacks SELECT. Provider quotas and wait/failure/rate budgets remain unspecified, and SDK actual outbound-attempt coverage remains an engineering proof requirement. Successful table access closes the retained September 15 inventory item; it does not itself authorize either implementation or prove fleet safety.

For each future implementation slice: full backend gate including PostgreSQL/performance lanes, independent review lenses, one mutation proof per new invariant, unchanged locked contracts, additive ledger-applied migrations and serial deploy verification. Test takeover, stale-owner publication, force-refresh IDs, quota release, provider cancellation, mixed revisions and no connections held over waits. SEC tests need multiple processes and actual mocked wire attempts, retries, pauses, expiry and coordinator failure. Deployment and activation remain distinct decisions.
