# Operations — health, metrics, caches, circuit breaker, admin & runbook

Production operations reference for the Cloud Run backend: monitoring surfaces, cache and
circuit-breaker management, performance tuning, alerting thresholds, admin endpoints, and
the verification-script catalog. Deploy/rollout mechanics live in docs/DEPLOYMENT.md;
local-dev issues in docs/TROUBLESHOOTING.md.

> Moved out of CLAUDE.md in the July 2026 refactor (Wave 3 / M3).

## Health Check & Monitoring Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /health` | Basic health check for load balancers | `{"status": "healthy"}` |
| `GET /health/detailed` | Detailed check with DB + Redis + circuit breaker | See example below |
| `GET /metrics` | Application metrics; authenticated admin required | See metrics response below |

### Detailed Health Check Response

```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "healthy": true,
      "latency_ms": 2.45
    },
    "redis": {
      "healthy": true,
      "latency_ms": 1.12
    },
    "sec_edgar_circuit": {
      "state": "closed",
      "healthy": true,
      "stats": {
        "total_requests": 1500,
        "success_rate": 98.5,
        "rejected_requests": 0
      }
    }
  },
  "timestamp": 1706454000.123
}
```

### Metrics Endpoint Response

```json
{
  "timestamp": "2024-01-29T12:34:56Z",
  "app": {"name": "EarningsNerd API", "version": "1.0.0", "environment": "production"},
  "circuit_breaker": {"sec_edgar": {"state": "closed", "stats": {...}}},
  "cache": {
    "redis": {"healthy": true, "hit_rate": 84.75, "hits": 1200, "misses": 215},
    "xbrl_l1": {
      "total_entries": 450,
      "valid_entries": 445,
      "max_size": 1000,
      "utilization_percent": 45.0,
      "hits": 3200,
      "misses": 800,
      "hit_rate": 80.0,
      "evictions": 50
    }
  },
  "thread_pool": {
    "edgar": {"max_workers": 4, "threads_created": 3},
    "anyio": {"scope": "event_loop", "total_tokens": 40, "borrowed_tokens": 4, "tasks_waiting": 0}
  },
  "database": {"pool_size": 10, "checked_in": 8, "checked_out": 2}
}
```

The values above are illustrative, not production measurements. `thread_pool.anyio` snapshots
the responding event loop's default worker limiter: `total_tokens` is its current capacity,
`borrowed_tokens` counts occupied tokens, and `tasks_waiting` counts tasks waiting for a token.
Health probes and summary database units share this limiter. Collection does not borrow a token
and exposes only aggregates, never borrower objects. Waiting tasks indicate contention at that
instant; the snapshot provides no duration, historical peak or alert threshold.

`GET /metrics` uses the existing authenticated admin check (normal session/bearer authentication);
it is not `/api/metrics`. Its database-backed authentication and synchronous dependency can
themselves wait under saturation, so this is not an outage-independent diagnostic. Counts are
local to that event loop, not fleet totals, CPU utilization or EDGAR/default-asyncio executor
state. Since E09b the snapshot also carries `provider_admission` (every provider stream in the
process: `in_flight`, `admitted`, `peak_in_flight`; and the chat-only slot gate
`AI_CHAT_MAX_INFLIGHT`: `limit`, `chat_in_flight`, `waiting`, `rejected`; the summary path is
counted but bounded by its own semaphores and never waits here) and
`sec_rate_limiter` (the process-local SEC token bucket: `total_requests`, `rate_limit_hits`,
`current_tokens`, `requests_per_second`). Both are per process: the load on the shared provider
key or on SEC is the sum over the API instances and every job that ran in the window (every
SEC-calling job carries its own buckets: pregenerate, the hourly filing-scan, backfill-facts and the
EFTS jobs notable-filings and earnings-calendar-refresh; pregenerate at Monday 06:00 UTC and
backfill-facts at Monday 07:30 UTC each overlap the hourly scan and the service in the 06:00–08:30
window). A rising `rejected` count means chat callers are timing out in the queue rather than at the
provider; `rate_limit_hits` climbing on the service while a job runs is the aggregate SEC budget
being exceeded; the per-process pins below bound the configured sum, not observed traffic. This addition
changes no capacity or startup/probe deadlines.

#### SEC budgets per process (deploy-pinned)

Each process holds two independent SEC limiters: the app's token bucket, `SEC_RATE_LIMIT_PER_SECOND`
(code default 10; it starts full, with capacity equal to rate), and edgartools' sliding window,
`EDGAR_RATE_LIMIT_PER_SEC` (library default 9, read once at import). The app wraps edgartools
traffic in its own bucket only in the SIC lookup (`app/services/edgar/company_sic.py`), which
therefore draws from both, so a process's configured SEC ceiling is at most the sum of the two. SEC
allows 10 requests per second per user regardless of machines, so the deploy pins both to `1` on the
API service, every Cloud Run job and the private task worker (`ci.yml`; gate
`tests/unit/test_sec_process_budgets.py`), and so does each Ops workflow step that runs a backend
script on its runner (gate `tests/unit/test_ops_workflow_wiring.py`; CODE RED decision records 16
and 17 staged it, the jobs and the worker first). Two request paths could not fit the service's 1 req/s and were removed with the
pin: the insider endpoint (`GET /api/companies/{ticker}/insiders`, a cold load of about two edgartools
requests per Form 4 for up to 60 Form 4s, so about 120) answers 404 unless `ENABLE_INSIDER_ACTIVITY` is
set (the deploy pins it `false`), and company search answers from the cached SEC ticker file only (its
edgartools fuzzy fallback never returned a company). Under load the pin shows as queueing. When several
generations run at once on one instance, a cold summary's XBRL enrichment (15 s budget) can fall back
to companyfacts (its section parse makes no SEC request: parses run one at a time on their own
worker, off the edgar pool, and the excerpt waits for it before the 18 s enrichment join; a parse past its 30 s bound, 40 s for a 20-F, leaves the regex excerpt); a
mega-filer's filing older than its recent submissions window needs about 43 history requests, past
every enrichment budget; and a
company's first filings list, coverage and full-text search each wait for their request. Breaker-wrapped
edgartools calls queued behind that work (a company's first filings list, 6-K text, and visit refreshes
run in-process when durable tasks are off) can time out after 15 s (30 s for 6-K text), and five
timeouts in a row open the shared SEC circuit breaker for 30 s, which fails summary document fetches on
that instance meanwhile (Circuit Breaker Management below). A synchronous precompute dry run on
`/internal` makes at least one request per job, so the route caps it at 20 jobs (tickers × forms),
which normally fits the 30 s request timeout; a job that needs a mega-filer's full submissions history
(about 43 requests) or other SEC traffic on the instance can still push it past. Split a larger
preview into batches.

The configured sustained sums are: 4 req/s sustained with no job running (two service instances), 6
in the hourly filing-scan window, and at most 8 req/s in any scheduled overlap — Monday 06:00 and
07:00 UTC (pregenerate, whose first attempt can run until 07:00, with a scan), Monday 07:30–08:30 UTC
(backfill-facts with a scan) and a daily EFTS job over a running scan — and 22 req/s if every job ran
at once (24 with the worker, 26 in a handover second), which configuration does not prevent. The
feedback-media cleanup job adds two to this conservative configured sum but performs no SEC calls.
A full bucket at rate R admits up to 2R−1 requests in
its first second (19 at the default 10), but at the pinned rate of 1 the bucket never holds more than
one token, so admissions are at least 1 s apart, and edgartools' window never exceeds its rate per
rolling second: under the pin a process's ceiling is 2 req/s in every second, the first included, so
these sums are also the per-second ceilings. The private task worker (`earningsnerd-task-worker`, one
instance running one isolated child per delivery) is deployed only with
`GCP_DURABLE_TASKS_ENABLED=true` (on in production since 2026-10-08); it adds 2 req/s to every window,
giving 6 req/s sustained with no job running and at most 10 req/s in any scheduled overlap, at the cap
with no headroom. Each task runs in a fresh child with fresh limiters, so a handover between two
children inside one second can briefly admit up to 4 req/s from the worker, 12 req/s in such a
second. A filing-scan run through the worker (`/internal/jobs/filing-scan`) is bounded by its 480 s
work timeout (`TASKS_WORK_TIMEOUT_SECONDS`), about 450 watched companies at 1 req/s; the scheduled
scan belongs on the Cloud Run job (1,800 s).

The Monday figures assume the Cloud Scheduler crons in `docs/DEPLOYMENT.md`: backfill-facts at
`30 7 * * 1`, so it starts after a first attempt of pregenerate (`0 6 * * 1`, 3,600 s timeout) has
ended. At the earlier `0 7 * * 1` the 07:00 overlap would carry pregenerate, the scan and
backfill-facts: 12 req/s with the worker, 14 in a handover second. The schedulers are created by hand,
so the repository cannot enforce them; the gate checks the documented crons, time zones and task
timeouts. Check the live schedule with `gcloud scheduler jobs describe backfill-facts-weekly
--location=us-west1 --format="value(schedule,timeZone)"`.

Not bounded by this pin: rollout-overlap instances, manual job executions and operator one-shots, a
job task retried after a failure or timeout (no documented create command sets `--max-retries`, so
Cloud Run's default of three retries applies, and each attempt restarts its task timeout: a retried
pregenerate can still be running at 07:30 and meet backfill-facts and a scan, 10 req/s or 12 with the
worker, and a retried scan can meet the next one), a scheduler cron moved by hand, the service, a job
or the worker created by hand without the pins (the commands in `docs/DEPLOYMENT.md` and the runbook
set them, and CI sets them on the next deployable merge), and any request outside both limiters. Neither
the jobs nor the worker (it serves only `/health` and its task endpoint) expose limiter state: the
pin shows as longer execution times and, when SEC pushes back, as app-bucket 429 backoff warnings in
their logs. Lowering the budget shows up as longer SEC waits inside a process (the limiter waits, it
does not reject, and waits are not counted): `rate_limit_hits` increments only when a backoff-path
request receives a recognised SEC 429, so a flat counter is not evidence of safe aggregate traffic,
while a rising one is SEC pushing back. SEC 403 responses are not counted there; they show in logs.

To change or undo the pins, set new values in the `ci.yml` maps, or add
`--remove-env-vars=SEC_RATE_LIMIT_PER_SECOND,EDGAR_RATE_LIMIT_PER_SEC` to each update, in a change
that also touches a deployable `backend/` path and updates the gate
(`tests/unit/test_sec_process_budgets.py`, and the backfill-facts map in
`tests/unit/test_data_completeness.py`); when adding `--remove-env-vars`, drop the keys from that
update's map. `--update-env-vars` only sets keys, so deleting them from `ci.yml`, or reverting the
change that added them, leaves the pins live; a change confined to `ci.yml` does not deploy at all. A revert of stage 2 also
restores the public insider endpoint and the edgartools search fallback while the service stays
pinned, so in the same change remove the service pins or keep the insider switch and local-only search.
After a deploy, Ops `describe-service` (`docs/DEPLOYMENT.md`) prints `SEC_RATE_LIMIT_PER_SECOND`,
`EDGAR_RATE_LIMIT_PER_SEC` and `ENABLE_INSIDER_ACTIVITY` for the serving revision, the pregenerate
job and the task worker's serving revision, and fails when either pin is not `1` on the service or
the worker; admin `/metrics` shows `sec_rate_limiter.requests_per_second` for the instance that
answers; Ops `describe-jobs` prints both pin values for each of the nine jobs and fails when either
is missing or not `1`. Ops `capacity-readout` carries the worker's request classes and latencies and
its error-level log counts, the only aggregate evidence of the pin's effect on the worker.

### AI call telemetry (`ai_call` / `ai_summary` log lines)

Every provider attempt logs one JSON line, `ai_call {...}`, from `app/services/ai_metrics.py`
(never prompts, keys or filing identities). Fields: `operation` (`summary_primary`,
`summary_fallback`, `section_recovery`, `copilot_chat`, `analysis_chat`), `provider`
(`primary`/`fallback`), `trigger` (`user` for request traffic, `job` for Cloud Run jobs, `eval`
for the eval harness), `requested_model` vs `actual_model` (what we asked for vs what the response
said it served), `system_fingerprint` (the provider's backend build id when present), `outcome`,
`latency_ms`, `first_token_ms` (streams), `usage` (`prompt_tokens`, `completion_tokens`,
`total_tokens`, `cache_hit_tokens`, `cache_miss_tokens`, `reasoning_tokens`; `null` = the provider
did not report it, never zero), `estimated_cost_usd` (per-model price table in
`app/services/llm_pricing.py`, times `AI_PEAK_PRICE_MULTIPLIER` when `peak` is true) and `peak`.
The estimate prices every prompt token once: a cache half the provider left out is the rest of
the prompt, at its own tariff, and with no split all input is priced at the miss rate. It is
`null`, never zero or a partial sum, when the input or the output count is unknown.
One `ai_summary` aggregate follows each summary generation. Admin `GET /metrics` exposes the
process-local counters per (operation, provider, model, outcome): `estimated_cost_usd` and its
explicit twin `estimated_cost_known_usd` sum the known estimates only, `estimated_cost_unknown_calls`
counts the calls left out of that sum, and `estimated_cost_complete` is true only when there are none.
The log-based cost metrics below likewise sum known estimates only, since a `null` estimate does not
match their extractor; their companion counter counts the calls left out, from the service and the
jobs, so a chart or alert on the sums can show when they are incomplete.

What to watch after a provider change (ADR-0008): `actual_model` or `system_fingerprint` moving
without a deploy is a silent routing change; `reasoning_tokens` above zero means thinking mode was
enabled upstream (every path sends it disabled); a step in `completion_tokens` or `latency_ms`
per `operation` is a behaviour change worth an eval run.

Log-based cost metrics (one-time setup, not applied by CI). The API service and its task worker log JSON
in production (`main.py` and `task_worker_main.py` turn on `StructuredLogFormatter`), so their `ai_call` text
is `jsonPayload.message`; Cloud Run jobs log plain text, `textPayload`. An extractor reads one field, so each
gets its own known-subtotal distribution, which `gcloud` takes only from a config file (its flags carry no
extractor, label or histogram-bucket options); one counter covers both. A cost under USD 0.0001 is written
in exponent form (`6.3e-05`), which the extractor keeps. Once a small-cost call and a null-estimate call have
been logged, check in Metrics Explorer that the small value lands at its size and the null line leaves the
subtotal alone, since Cloud Logging's handling of either is not exercised here:

```bash
cd "$(mktemp -d)"  # the two config files stay out of the checkout
for spec in "service cloud_run_revision jsonPayload.message" "jobs cloud_run_job textPayload"; do
  read -r scope resource field <<<"$spec"
  cat > "ai-call-cost-$scope.yaml" <<EOF
description: 'Known subtotal: sum of non-null estimated_cost_usd over the $scope ai_call lines'
filter: 'resource.type="$resource" AND $field:"ai_call {"'
valueExtractor: 'REGEXP_EXTRACT($field, "\"estimated_cost_usd\":([0-9.eE+-]+)")'
labelExtractors:
  trigger: 'REGEXP_EXTRACT($field, "\"trigger\":\"([a-z]+)\"")'
  operation: 'REGEXP_EXTRACT($field, "\"operation\":\"([a-z_]+)\"")'
metricDescriptor: {metricKind: DELTA, valueType: DISTRIBUTION, labels: [{key: trigger}, {key: operation}]}
bucketOptions: {exponentialBuckets: {numFiniteBuckets: 32, growthFactor: 2, scale: 0.000001}}
EOF
  gcloud logging metrics create "ai_call_estimated_cost_usd_$scope" --project=earnings-nerd \
    --config-from-file="ai-call-cost-$scope.yaml"
done
gcloud logging metrics create ai_call_cost_unknown --project=earnings-nerd \
  --description="ai_call lines whose estimated_cost_usd is null, outside the known subtotals" \
  --log-filter='(resource.type="cloud_run_revision" AND jsonPayload.message:"ai_call {" AND jsonPayload.message:"\"estimated_cost_usd\":null") OR (resource.type="cloud_run_job" AND textPayload:"ai_call {" AND textPayload:"\"estimated_cost_usd\":null")'
```

Then an alert on each subtotal's daily total, or one query-language condition adding the two (a $5/day
threshold is roughly 2× current product spend; neither form is exercised here), with `ai_call_cost_unknown`
beside it, and a dashboard split by the `trigger` and `operation` labels the configs extract.
Spend from CI eval runs bills to the same DeepSeek key until a CI-only key exists (plan item W6).

**Status codes:**
- `200` with `status: healthy` - All dependencies operational
- `200` with `status: degraded` - Non-critical dependency (Redis) unavailable
- `503` with `status: unhealthy` - Critical dependency (database) unavailable

## Operational Runbook

### Cache Management

**L1 (In-Memory) Cache:**
- Max 1000 entries with LRU eviction
- 24-hour TTL
- Check stats: `GET /metrics` → `cache.xbrl_l1`
- Clear via admin: `POST /api/admin/xbrl/clear-memory-cache`

**L2 (Redis) Cache:**
- Persistent across restarts
- Shared across instances
- Check stats: `GET /metrics` → `cache.redis`
- Clear pattern: Use Redis CLI `SCAN` + `DEL` for bulk deletion

**Cache Pressure Indicators:**
- `l1_utilization_percent > 90%` - Cache is near capacity, expect more evictions
- `l1_evictions` increasing rapidly - High churn, consider increasing `_cache_max_size`
- `l1_hit_rate < 50%` - Poor cache effectiveness, review access patterns
- Look for `cache_eviction` events in logs for structured eviction details

### Circuit Breaker Management

**States:**
- `closed` - Normal operation, all requests pass through
- `open` - Failing fast, rejecting requests (check SEC EDGAR status)
- `half_open` - Testing recovery, limited requests allowed

**Actions:**
- If stuck in `open`: Check SEC EDGAR status, network connectivity
- Manual reset (if needed): Restart application or use admin endpoint
- Check stats: `GET /metrics` → `circuit_breaker.sec_edgar`

### Performance Tuning

**L1 Cache Size:**
```python
# In app/services/edgar/xbrl_cache.py
_cache_max_size = 1000  # Increase for more memory, fewer evictions
```

**Redis Timeouts:**
```python
# In redis_service.py
CACHE_OPERATION_TIMEOUT = 2.0  # Increase if Redis is slow
```

**Thread Pool Size:**
```python
# In edgar/config.py
EDGAR_THREAD_POOL_SIZE = 4  # Increase for more concurrent SEC API calls
```

### Alert-to-return measurement (E11c)

Every delivered alert email is one `earningsnerd_delivery_batches` row (`status = 'accepted'`,
`provider_email_id` set). Resend's `email.clicked` webhook stamps `first_click_at` on that row
the first time the recipient follows any link in it (later clicks and webhook retries never move
it) and emits one PostHog event `alert_email_clicked` (`kind`, `batch_id`,
`hours_to_first_click`, `link_path`; never the address, the query string, the IP or the user
agent the provider also sends). The stamp uses the provider's click timestamp, so a delayed
webhook retry does not overstate the delay. Opens are not used: mail clients prefetch tracking
pixels. The return rate per kind and week:

```sql
SELECT date_trunc('week', first_dispatch_at) AS week, kind,
       count(*)                                   AS delivered,
       count(first_click_at)                      AS returned,
       round(100.0 * count(first_click_at) / count(*), 1) AS return_pct,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY first_click_at - first_dispatch_at) AS median_delay
FROM earningsnerd_delivery_batches
WHERE status = 'accepted' AND first_dispatch_at >= now() - interval '8 weeks'
GROUP BY 1, 2 ORDER BY 1 DESC, 2;
```

Only batches sent after this column existed carry a stamp; earlier sends count as delivered
with no return. A `provider_email_id` the webhook cannot resolve (transactional mail, older
sends) is a clean miss, logged at INFO with the masked recipient, the id and the link path only.

### Retention purge job

`earningsnerd-retention-purge` (weekly; `scripts/retention_purge.py`, ad hoc through
`POST /internal/jobs/retention-purge?dry_run=true|false`) applies the clocked rows of
`DATA_RETENTION_POLICY.md`: search history older than 365 days, failed-login state untouched for
7 days and not locked, expired OAuth states, refresh tokens expired or revoked more than 30 days
ago, contact-form submissions older than 365 days. Deletes run in batches of 5,000 committed
one at a time; the job ledger row (`earningsnerd_job_runs`, `job_name = 'retention-purge'`)
carries `<target>_purged` counts and `dry_run`. Nothing user-facing changes: every qualifying
row is already invisible or unusable. Account deletion for inactivity, waitlist and referral
rows, audit logs, usage counters and billing rows are outside this job by design.

### Monthly Cloud SQL export

The `Monthly Cloud SQL export` Actions workflow is the scheduled owner for one logical PostgreSQL
export each month. A green run means either that its one exact export operation reached `DONE`
without an error and the bound object passed metadata and gzip-prefix checks, or that the same
month already had both that successful bound operation and that verified object. Object shape
alone is never success. If the provider no longer returns the operation that created an existing
object, the workflow stops at `state-hold`; a privileged operator must inspect the retained cloud
history rather than overwrite it.

The workflow submits at most once, adopts one exact active operation, and performs only one
lookup after an uncertain submission result. It never redraws that request. A failed operation
is a state hold and never permits an implicit same-month retry. It may leave the deterministic
object name occupied; cleanup requires a separately authorized operator because the workflow
identities have no delete permission. Public database health is
checked before and after the export. This verifies an individual execution or same-month reuse
and custody of a compressed logical export; it does not read SQL contents or prove restoration
or a natural scheduled trigger. The separate [September 28 import rehearsal](../tasks/review-evidence/progress-2026-09-28/README.md)
restored the retained monthly object into local PostgreSQL 15 with one `NOLOGIN` owner-role
prerequisite, 33/33 application tables and 40/40 migration hashes. See
[deployment setup and import procedure](DEPLOYMENT.md#monthly-cloud-sql-logical-export) for the
dedicated identity, IAM, secret, bucket lifecycle and recovery limits.

### Feedback screenshot cleanup alerts

The hourly `feedback-media-cleanup` job is separately monitored by feature-owned Cloud Monitoring
policies provisioned through protected Ops. Failed completed executions notify the existing verified
channel; missing normal-cleanup success heartbeats alert after two hours. Probe and dry-run success
cannot refresh that heartbeat. Overdue objects fail the execution after their counters are recorded.
Inspect the counts-only job ledger and the private-storage manifests before concluding that media was
erased. See [private feedback screenshots](DEPLOYMENT.md#private-feedback-screenshots) for provisioning,
permission checks and the distinction between configured alert routing and verified delivery.

### Durable alert delivery: reconciling `ambiguous` batches (E11b-1)

New-filing alerts and daily digests are persisted in `earningsnerd_delivery_batches` (one row per
outbound email: frozen recipient/sender/subject/HTML and plain-text part, the provider
`Idempotency-Key`, status, lease and attempt bookkeeping) and `earningsnerd_delivery_items` (the
filings each batch owns). The plain-text part (`body_text`, E110) is covered by the batch's
`payload_sha256`; a batch frozen before the column holds NULL there and replays as it was frozen,
its page alone, under the digest it was frozen with.
Reply-To is also frozen in that envelope and covered by `payload_sha256`. Batches with a
frozen Reply-To use `reply_to:ready`, `reply_to:claimed`, `reply_to:sending` and
`reply_to:retryable`; all four remain outside older workers' due, claim and stale-lease
predicates. Compatible workers accept both state families and retain the family from the
persisted status on every claim, retry, re-key and lease recovery, even if `reply_to` changes or
becomes NULL. Legacy NULL Reply-To batches retain their legacy states, omitted header, payload
hash and provider key. No batch kinds, queues or job schedules change.

During a rollback to an older image, new-protocol batches wait until a compatible worker is
restored; the older image can continue processing legacy batches. Retain the nullable column,
status values, provider keys and item ownership. Do not use SQL to relabel states, re-key these
batches or release their filings to bypass the protocol boundary. Ready/retryable batches
resume with a compatible worker, and expired preparation leases recover normally. An expired
sending lease still becomes `ambiguous` and needs the human reconciliation below; rollback
preserves that uncertainty.

`accepted`, `suppressed` and `ambiguous` are terminal. `ambiguous` means the provider's answer
was lost after bytes may have left (timeout, dropped connection, unparsable or non-object 5xx
response, expired sending lease, exhausted attempts, payload drift): the job never dispatches it
again, because a resend could duplicate an accepted email, and its filings stay owned so they
are never re-selected. Every parked batch is counted once in the job's `delivery_ambiguous`
counter (`earningsnerd_job_runs`); a non-zero count needs a human decision.

When a pending envelope needs a new address, digest routing or a smaller wanted membership,
the old batch's suppression and the replacement batch's ownership commit together. A replacement
write failure rolls back both changes and fails the drain; after the original claim expires,
the next run can rebuild it even when its filings are outside the ordinary selection window.
This protects pending work only; it does not recover historical lost or ambiguous batches.

Triage (read-only):

```sql
SELECT id, kind, user_id, last_error_kind, attempts, first_dispatch_at, idempotency_key, provider_email_id
FROM earningsnerd_delivery_batches WHERE status = 'ambiguous' ORDER BY updated_at;
```

Confirm in the Resend dashboard whether an email with that `idempotency_key` (or the batch's
`to_email` and `subject` around `first_dispatch_at`) was accepted. Then, per batch, either:

- **It was accepted** → mark it delivered so the compatibility log and watermark match reality:
  `UPDATE earningsnerd_delivery_batches SET status = 'accepted', provider_email_id = '<resend id>' WHERE id = <id>`,
  then insert the `notification_log` rows (`status = 'sent'`) for its items and advance the
  watchlist watermarks the way `finalize_accepted` does. Do not delete the items.
- **It was not accepted** → give the filings back to selection:
  `DELETE FROM earningsnerd_delivery_items WHERE batch_id = <id>`; the next scan or digest
  builds a fresh batch under a fresh key if the filing is still inside the selection window and
  wanted. Leave the batch row as evidence.

Earnings-day alerts (`earnings_alert_log`) follow the same rule with a smaller ledger: the
`pending` claim is committed before the send, so a row still `pending` after its run finished is
a lost outcome (the process died after the claim, possibly after the provider accepted). The job
never retries it; confirm in Resend by recipient and subject around the run time, then set the
row to `sent` (accepted) or `failed` (not accepted), and for `failed` re-run the job the same
ET day (`POST /internal/jobs/earnings-day-alerts` or `gcloud run jobs execute
earningsnerd-earnings-day-alerts`): the job only takes over `failed` rows whose `event_date` is
today, so after that day the alert lapses.

Never re-send an `ambiguous` batch by hand under its old key, and never edit its frozen payload
(`payload_sha256` would then park it as `payload_drift`). Code from before E110 reads no
`body_text`, so a drain it runs fails the digest of every due batch frozen with a text part and
parks it as `payload_drift`, unsent: after a rollback past E110, and during the deploy that ships
it, in a job execution that started on the old image and reaches its drain after the new image
froze a batch. Such a batch was ready or retryable when that drain claimed it, so the provider
never accepted it: at `attempts = 0` it never reached the provider, and a retryable batch's attempts
each ended in a documented non-acceptance (the old drain re-keys one whose replay window closed
before it parks it). Give its filings back to selection as above. Otherwise a `retryable` batch
needs no action: the job retries it with backoff, re-keying it if the replay window closed.
Historical `notification_log` rows are never replayed.

### Account mail (F60)

Forgot-password and resend-verification queue their mail, the `account_mail` task, on the shared
`earningsnerd-background` queue whenever `DURABLE_TASKS_ENABLED` is on (production since
2026-10-08), so the private task worker sends it, not the API.

- **Where failures surface.** A failed send logs `Reset email NOT sent to user id=N: <class>` (or
  `Verification email ...`) at ERROR and is not retried. A send that sent nothing (a 429, a 5xx, no
  connection, no API key) logs `... email not sent to user id=N: <class> (nothing sent)`, and Cloud
  Tasks delivers it again, up to the queue's five attempts. These lines reach Cloud Logging only:
  filter `earningsnerd-task-worker` for `email NOT sent` and `(nothing sent)`. With `SENTRY_DSN` bound on
  the worker, a failed delivery also reaches Sentry by its exception's type and stack alone (the worker's
  `Durable task failed` and the child's `AccountMailNotSent`, F50); a send that failed after sending is no
  failed delivery, so it reaches Sentry not at all. Registration's own verification mail is still sent from the API, whose
  ERROR lines reach Sentry.
- **The cap.** `ACCOUNT_MAIL_LIMITER` (`routers/auth.py`) admits 60 account mails an hour per API
  instance across both routes, after each caller's per-IP (20 an hour per route) and per-address (3
  an hour) limits. Past it every address gets the same 429 until the window turns, so a flood costs
  that hour's reset and verification mail instead of backing the queue up.
- **Latency.** A mail waits behind the task the worker is running (up to the 480 s work timeout) and
  anything queued before it.
- **Rollback.** CI updates the worker before the API, so a forward deploy is safe. A revert deploys
  in the same order, so account mail queued until the API's revert lands meets a worker whose
  `TaskEnvelope` has no `account_mail` kind: it fails every attempt (422) and is lost, and its senders
  must ask again. To lose none, first roll the API's traffic back (the Ops workflow's
  `rollback-traffic`), which stops new account mail reaching the queue; let the queue drain; then
  revert. Never pause or delete the queue (`docs/DEPLOYMENT.md`).

### Monitoring Alerts (Suggested Thresholds)

| Metric | Warning | Critical |
|--------|---------|----------|
| `delivery_ambiguous` (job counter, per run) | > 0 | > 10 |
| `cache.xbrl_l1.utilization_percent` | > 80% | > 95% |
| `cache.redis.healthy` | - | `false` |
| `circuit_breaker.sec_edgar.state` | `half_open` | `open` |
| `database.checked_out` | ≥ pool_size − 1 (3 on the deployed service pool 4 / overflow 0) | = pool_size |

## Request Timeout Configuration

Per-endpoint timeouts configured in `backend/main.py`:

| Endpoint Pattern | Timeout |
|------------------|---------|
| `/api/summaries/` | 120s |
| `/api/filings/` | 60s |
| `/health` | 5s |
| Default | 30s |

Streaming endpoints (`*stream*`, `*/progress`) are excluded from timeout middleware.

## Admin Features

Admin endpoints require `is_admin=True` on the user account. Available at `/api/admin/`:

| Endpoint | Purpose |
|----------|---------|
| `POST /email/test` | Send a test email via Resend (diagnoses email config; defaults to admin's own address) |
| `POST /users/free` | Refuses with 409 and creates nothing: an account comes only from signup, where its holder accepts the account requirements, so the answer points to an invitation (`POST /invites`) |
| `DELETE /filing/{id}/summary` | Delete summary for a filing |
| `DELETE /filing/{id}/xbrl` | Clear XBRL cache for a filing |
| `DELETE /filing/{id}/reset` | Full reset (summary, XBRL, content cache, progress) |
| `POST /xbrl/clear-memory-cache` | Clear in-memory XBRL cache |
| `GET /xbrl/cache-stats` | View XBRL cache statistics |
| `GET /filings/audit-xbrl` | Audit filings for stale XBRL data |
| `POST /filings/bulk-reset-stale` | Bulk reset stale filings (supports dry_run) |
| `POST /summaries/reset-all` | Bulk delete summaries by form so they regenerate with current prompts; skips saved (bookmarked) rows unless `include_saved=true` (supports dry_run) |
| `POST /summaries/refresh-stale` | Bulk **in-place** refresh of version-stale summaries (below a `schema_version`, or stale vs the current schema+prompt version) via the one orchestrator with `force_regenerate=True`; preserves `summaries.id` so bookmarks survive, keep-better quality gate prevents downgrading a summary the filing page shows (a stored row the page cannot show is always replaced), `dry_run` reports the staleness count. Returns honest per-filing outcomes (`updated`/`kept_by_gate`/`failed`) when the run finishes inside the request-timeout middleware's 30 s default, which this path takes (`main.py`). A longer run, one generation can be, answers 504: its remaining generations and audit row run after the response, under the API's request-based CPU (the deploy's `--cpu-throttling` while durable tasks are on), where they can be slowed or cut short, and the audit row keeps only counts. A row the keep-better gate keeps stays **stale** and may be re-selected on a later call. Candidates are sampled at random per call, so a filing that consistently loses to the gate is a diminishing nuisance, not a permanent head-of-line wedge. If `stale_total` stops shrinking, the head of the queue keeps losing to the gate — narrow with `filing_type`/`schema_version_lt`. |

### Test accounts

`freeuser@earningsnerd.io` (user id 9) is the founder's free-plan test account, kept indefinitely for checking what a free user sees. It is Free, non-beta and non-admin, and its address is an alias of the founder's mailbox. While checkout is open, its checkouts reuse one live Stripe Customer created for verification and are never paid.

- Leave it out of funnel, revenue and user-count readouts by filtering on user id 9. That includes the `checkout_started` events its Upgrade clicks fire while checkout is open; while it is closed, as now, an Upgrade click fires none.
- Nothing deletes it: the retention purge never deletes accounts (`backend/app/services/retention_service.py`).

To create another test account, sign up through the site with an address whose inbox the tester
controls. Signup is where an account's holder accepts the account requirements, so no admin route
creates one: `POST /api/admin/users/free` answers 409 and creates nothing. While
`REGISTRATION_MODE` is `invite_only`, an admin first mints an invitation bound to that address
(`POST /api/admin/invites` with `email`) and hands over the response's `invite_link`, which is
shown once. Asking the mint to email it answers 503 while promotional mail stays closed
(`legal_readiness_service.is_marketing_available()`), and the mint and signup both answer 503
while new collection is closed (`is_collection_available()`).

New checkout is closed in code today: `legal_readiness_service.is_checkout_available()`
returns False, so `POST /api/subscriptions/create-checkout-session` answers 503. Once it
reopens, the monthly trial is available once per account. To test the first-subscription trial
again after an actual trial or subscription, create a fresh Free account. Opening an unpaid
Checkout preview and leaving it unsubmitted does not consume that eligibility, so those checks
can reuse the existing test account. Leave the retained user id 9 unchanged.

### Verification Scripts

Located in `backend/scripts/`:
- `apply_migrations.sh` - Apply `backend/migrations/*.sql` through the `migration_ledger` table (ADR-0007); the one script both `deploy-backend` and the `migrations-postgres` CI job run
- `deploy_check.py` - Pre-deployment validation (env vars, DB, dependencies)
- `validate_db_performance.py` - PostgreSQL performance benchmarking
- `verify_extraction_standalone.py` - Test XBRL extraction against live SEC data
- `verify_extraction_mock.py` - Tests XBRL extraction with mock data
- `verify_startup_config.py` - Detailed startup configuration verification
- `debug_extraction.py` - Debug regex patterns for extraction
- `fix_null_sec_urls.py` - Repair filings with NULL sec_url values (see docs/TROUBLESHOOTING.md)
- `backfill_facts.py` - Backfill the `financial_fact` table from cached/parsed XBRL. Its normal and
  `--only-new` modes write; `--dry-run` is valid only with `--remediate-financials` or
  `--backfill-company-sic` and otherwise exits before application initialization.
- `audit_reconciliation_flags.py` - Audit/repair stored `financial_fact.reconciled` flags on
  value-identical rows, flag columns only (unstored identities are counted, never inserted; dry
  run by default; `--apply` writes; `--tickers`, `--limit`)
- `list_facts_created.py` - Read-only: list `financial_fact` rows created in a time window
  (`--since`, `--until`, `--limit`), one JSON line per row; the review aid for a write pass
- `filing_scan.py` - Scan for new filings on watched companies (alerts pipeline)
- `pregenerate_examples.py` - Pre-generate example summaries (weekly refresh cron)
  - Weekly examples cover the latest domestic 10-K and 10-Q; BABA uses its annual 20-F.
    `--annual-only` keeps a manual run annual-only. The job's CI environment enables FPI.
    The token-gated precompute endpoint still defaults to annual forms unless requested otherwise.
- `seed_universe_companies.py` - Preview missing committed-universe Company identities; `--apply`
  writes them without invoking summary generation. Run the separate SIC backfill after seeding.
- `verify_insider_extraction.py` - Verify Form 4 insider extraction against live SEC data

### Review gate (rule 12 for the review-wait lesson)

`.github/workflows/review-gate.yml` publishes a `review-gate` status check on every pull request
head. On every pull-request event while the pull request is a draft the check fails (converting a ready
pull request back to a draft starts no run), and marking it ready starts the wait; `@codex review` on a
draft re-runs its newest gate run, which fails again, unless that run is a skip from before #1331, which
the re-run job refuses (E60 lists the drafts). The script reads the draft flag from the pull
request as it is now: a job skipped by its condition reports success, which a required check counts as
passing, and an event can still describe a draft after the pull request was marked ready, so the job
never skips on a pull-request event. Draft or not and override or not, it fails at once while the
pull request's title, body or any of its commit messages puts a closing keyword (close, fix or resolve,
in any form) right before an issue or pull request reference, since the merge into `main` would close
what it names, a pull request included: on 2026-10-09 the merge of #1136 left #1156 closed, unmerged,
that way (`lessons/ops-closing-keywords-close-what-they-name.md`). It reads the text as GitHub renders
it (Markdown escapes dropped, HTML entities decoded) and lists each reference; an edit to the title or
body re-runs the check, and a commit message is reworded on the branch. Until the edit's run reports, the
previous result stands on the head, as for drafts below, so merge only after it passes. It also fails a
pull request that lists 250 commits, the most GitHub's commits endpoint returns, because later commit
messages would go unread. A squash message typed at merge is outside every pull-request check. It passes
only when the trusted Codex summary's machine state names that full head, reports **Completed**,
and has `has_unresolved_findings` exactly false, with the required review-cycle evidence; or when
the pull request body carries a line `Review override: <reason>` (ten or more characters). The
ready transition's own review must have completed. A later manual review of a different head may
supersede that completed review's findings; a manual review of the same head requires the ready
review itself to be clean. A completed review of an earlier head is not enough, because a push does not
re-trigger Codex here: after fix commits, comment `@codex review` at once, or, while a review
still shows Running, once it completes or is an hour old. The gate waits up to
twenty minutes, then fails naming the remedy; an `@codex review` comment re-runs the newest gate run
on the pull request's current head automatically (the workflow's `issue_comment` job, the only one
holding a write scope, `actions: write`), so a re-requested review is observed without a manual
re-run. The job finds that run by the head commit and the pull request's head branch and repository,
however many runs other pull requests have had since. GitHub re-runs a run only within 30 days of its
first attempt, at most 50 times; past that the job fails, giving GitHub's reason and the remedy (push,
or edit the body). The job reports each outcome only in its own log, in the Actions tab: its run sits
on `main`'s latest commit, so the pull request's checks do not show it. Neither a ready mark nor an
`@codex review` goes in while a review shows Running: the summary carries no run id, so the gate replays
its history, pairs each completion with the open start of its head and trigger, never with one begun while
another of them was open (such a start holds the gate for its whole hour), and waits while any start is open,
until that review completes or is an hour old, when it counts as abandoned (F58 call 1, approved 2026-10-23). A ready review that hangs therefore stops
blocking an hour after it started, and one fresh draft-to-ready transition then passes; a ready mark or
request made inside that hour costs the hour again (`lessons/ops-merge-after-the-ready-marks-own-codex-review.md`
gives the recovery order). The gate prints each reason as it polls. Logic in
`backend/scripts/review_gate.py` (stdlib only), pinned by `tests/unit/test_review_gate.py`. The
workflow runs on `pull_request_target` and checks out the **base** branch, so a pull request can edit
neither its own gate script nor the workflow definition (the job never executes pull-request code and
holds read-only tokens); only the exact Codex GitHub App identity (login, `Bot` type, immutable id) is
trusted; and a reviewed short SHA counts only when the repository resolves it uniquely to the head and
no other commit of the pull request shares it, so a head minted to share a reviewed prefix stays
unreviewed while the reviewed object exists. F58 additionally reads GitHub's ready-transition
timeline and the bot's authenticated comment edit history, replaying it to pair each completion with
its start. GitHub's event/request timestamps have second precision, so a start in the same second
cannot establish ordering: the gate requires the next whole-second boundary. The PR's live head
and latest manual request must agree with that proof. Missing,
malformed or contradictory evidence waits instead of falling back to an older clean result.
GitHub retains at most 100 comment revisions and the bot exposes no unique review-run ID, so missing
required history waits, and so does a start still open, or an unreadable revision, younger than the hour; a
start or completion within the hour after an unreadable revision never pairs, and one fresh draft-to-ready
transition is the way out. Marking ready already requests a review;
let that cycle finish before sending another manual request for the same head. Thread disposition
remains a reviewer responsibility (`lessons/ops-merge-after-the-ready-marks-own-codex-review.md`).
Each run takes the workflow definition from `main` as it
stood at the run's event, and a re-run keeps that definition, so a change here reaches a pull request
at its next pull-request event. The re-run job never re-runs a skipped run: only a run from before
#1331 can skip, under its old draft condition, and a re-run would replay the skip. A ready pull
request whose newest gate run is such a skip needs a new pull-request event, an edit to its body for
instance. Never re-run such a run by hand ("Re-run all jobs"): it replays the skip, which a required
check counts as passing. Those runs pass GitHub's 30-day re-run limit around 2026-11-14. A draft whose
newest gate run is such a skip also shows it as its newest check from the moment it is marked ready
until its ready run's check appears, a few seconds, or for good when no run starts (an Actions outage,
or a transition made with a workflow's `GITHUB_TOKEN`): push or edit its body while it is still a
draft, so its newest check is a real run, then mark it ready.

The check binds merges through the ruleset on `main` (id 23561253, created 2026-09-16, `gh api
repos/neilmac91/EarningsNerd/rulesets/23561253` to read it): deletion and force-push of `main`
blocked; a pull request required with **zero** approvals and squash as the only merge method;
required status checks `backend-tests`, `frontend-tests`, `e2e-tests`, `migrations-postgres`,
`lighthouse`, `review-gate`, `secret-scan` and, since 2026-10-25, `e2e-charts-v2` (the trend charts' spec
renderer under `NEXT_PUBLIC_CHARTS_V2`; `tasks/todo.md` E195 takes it out again before that job is deleted),
each pinned to the GitHub Actions app; no bypass actors, so the rules
bind the administrator too. A required status check needs no approver, so this does not lock a
single-collaborator repository; requiring pull-request reviews would, because authors cannot approve
their own pull requests, and the GitHub default `require_extra_approval_for_unattributed_changes` is
switched off for the same reason (agent commits are authored as `noreply@anthropic.com`). When the
review service is unavailable, the pull request body's `Review override: <reason>` line is the only
way through the gate, by design.

Required checks bind a pull request only as far as its workflow files can be trusted. The ruleset pins
each check to the GitHub Actions app, and that app runs a pull request's `pull_request` workflows from
the pull request's own tree. So a pull request that edits `.github/workflows/` can make every required
check pass: it can rewrite the job behind `backend-tests`, or add jobs named `review-gate` and
`backend-tests` that do nothing. `test_no_job_in_any_other_workflow_publishes_a_check_named_review_gate`
catches only an accidental second `review-gate` job, since a pull request that adds one on purpose can
neuter `backend-tests` too. What binds such a pull request is that only the repository's writers can
merge, and that `AGENTS.md` §5 reviews every change to `.github/workflows/**` at the high tier, so the
merge rests on reading the workflow diff, not on the checks. A required check that a pull request cannot
forge needs a source outside its workflows: a dedicated GitHub App that the ruleset names as the check's
source, with its key held in an environment only `main` can use, or a ruleset-required workflow, which
GitHub configures in an organization's or an enterprise's rulesets (a personal account owns this
repository). Neither is in place, and the gap is accepted (the founder left this call to the agent on
2026-10-16); closing it starts with that App.

### Agent production readbacks (F51)

After a backend deploy has concluded, a Claude Code session may read production through two read-only
Ops operations. `.claude/settings.json` allows exactly these three commands, each as an exact-match rule:

```sh
gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main -f operation=describe-service
gh workflow run ops.yml -R neilmac91/EarningsNerd --ref main -f operation=logs-probe
gh run list -R neilmac91/EarningsNerd --workflow ops.yml --branch main --event workflow_dispatch -L 5 --json databaseId,status,conclusion,createdAt,headSha
```

**When the rules apply.** Only in a session that applies this checkout's project settings: a
single-repository session (a cloud thread in a project reads no project permission rules, nor does a
cloud session with several repositories in an Anthropic-hosted environment), in a workspace whose trust
is recorded (a `-p` or SDK run uses project allow rules only when `~/.claude.json` records
`hasTrustDialogAccepted` for the repository's main checkout root, where a worktree's trust is keyed),
with no managed `allowManagedPermissionRulesOnly` and no `autoMode.classifyAllShell` (which suspends
every Bash allow rule in Auto mode), and, under the Bash sandbox, with GitHub's API on the sandbox's
allowlist (a command that carries hosts of its own goes to the classifier). There, in Auto mode, a
matching command runs without a prompt and without the auto-mode classifier. Anywhere else it goes to the
prompt, the classifier or the session's own tool allowance, as before.

**No command proves the route on its own.** In Auto mode a silent run shows only that the command was
allowed, by these rules or by the classifier, which may approve a read of run metadata, or even a read
dispatch, by itself; in Accept edits, or under a harness that allows every Bash command, any command
that runs proves nothing about these rules
(`lessons/ops-prove-the-permission-route-before-a-gated-session.md`). The conclusive result is the
other one: a prompt or a classifier denial of one of the three exact commands means the rules did not
apply, so record it verbatim and stop, never reshape a command. `/permissions` lists each rule and the
file it comes from; the operator checks the conditions above beside it.

**What a rule admits.** A rule without `*` matches only its own text, so another operation, input, ref
or repository, a variable, or a wrapper or assignment the matcher does not strip falls outside it.
Two of the allowed commands chained together (`&&`, `;`, a newline) are each allowed; issue each alone
anyway. A read cannot replace a queued run: `ops.yml` runs `describe-service` and `logs-probe` each in
a concurrency group of its own run, so neither queues behind, nor replaces, a pending operation, an
approved apply's included. A read can overlap an Ops run that is in progress, though: a
`describe-service` that overlaps a `feedback-media` enable or disable apply can stop on a revision that
is not ready yet, as a describe during a deploy does, and one during or after `rollback-traffic` stops on
the traffic check until traffic is moved back to the latest revision. So dispatch a read when the list
shows no Ops run in progress, one read at a time, and wait until the list shows it `completed` before
the next. The list covers the newest five Ops dispatches.

**What the runs print** is the projection their steps already make ([Read-only release configuration
audit](DEPLOYMENT.md#read-only-release-configuration-audit)):
- `describe-service`: the traffic and revision names, `SENTRY_RELEASE`, the allow-listed values (the two
  AI base URLs among them) and SEC pins, each container's image reference, the sizing lines and the
  worker's invoker verdict; never the service, traffic or worker URLs, another environment value or
  gcloud's error text. A required read that fails stops the step, with no verdict line, on an
  `Unresolved production configuration: …` line that ends `cannot describe <kind> <name> (<class>).`
  after any defect found before it; the optional invoker-policy read prints `UNVERIFIED (<class>)`.
- `logs-probe`: whether `logging.read` is permitted, or `DENIED` with its failure class; the
  `company_upsert_conflict` count, which is absent when its read fails; and which revisions printed each
  Sentry start line, with counts, or `UNVERIFIED (<class>; gcloud's error text withheld)` for a kind it
  could not read; never a log line or gcloud's error text.

A record marks each of those failures Unverified (`lessons/ops-denied-reads-report-unverified.md`;
gates `test_prod_flag_visibility.py`, `test_ops_stderr_withheld.py`,
`test_capacity_projection_privacy.py`). The run log itself is read with `gh run view <run id> -R
neilmac91/EarningsNerd --log`, which stays outside the allow list: an exact rule cannot carry a run id,
and the whole job log also holds the authentication step's identity lines. A record keeps only the
operation step's verdict, revision, flag and Sentry lines.

**Nothing here allows an apply.** Every other operation, a dispatch through the REST API, a re-run, the
deployment-review and environment calls and any `gcloud` command stay outside the allow list; an
`-apply` still waits for the founder's approval of `ops-apply` and the workflow's owner-approval check,
and `.claude/hooks/ops_approval_guard.py` refuses a session the approval and rejection calls whatever
the allow list says ([DEPLOYMENT.md](DEPLOYMENT.md)). Gate:
`backend/tests/unit/test_ops_readback_allow_rules.py` (the three rules, the forbidden corpus, and the
jobs, steps, environment, runner and concurrency group a read dispatch runs, with the resolve script's
vocabulary); `ops/describe/service.py`, the Python every describe runs, is review-checked.

### Persisted audits and weekly judged readout (WS-6 measurement)

The data-quality report keeps two populations separate. Persisted audit counters describe the
currently retained Summary snapshots across the corpus; they are not a week's generation attempts.
The query projects only summary identity, SIC and audit/quality JSON, never the full generated
summary or excerpt. Each of the five families has its own recorded, missing and malformed counts:

| Family | Recorded outcome |
|---|---|
| Figure trace | Snapshots with flagged figures and total unique recorded figures per snapshot |
| Forward quotes | Checked, verified, unverified, near misses, other unverified and dropped quotes |
| Evidence snap | Checked, exact, would-snap candidates, performed snaps and unrepaired evidence |
| Machine sections only | Explicit true outcomes among snapshots with a recorded boolean |
| Quality tier | Partial snapshots and distinct reasons per snapshot, with SIC-prefix grouping |

Missing audits can mean legacy data, unavailable grounding or no eligible content. They never
contribute a measured zero. Malformed counters, lists or contradictory action counts remain
unavailable for that family. An empty recorded figure list does not establish that the tracer had
grounding; the eval's separately measured availability is the relevant denominator for that claim.
Rates use recorded snapshots only and are unavailable when that denominator is zero.

The weekly workflow supplies a bounded summary-only base64 value through the report script's
`--weekly-readout-b64` execution argument. The shared `app/services/ai_readout.py` validator owns
that external boundary. Both dry-run JSON and email preserve its complete/partial/unavailable
status, 24-attempt cohort counts, valid negative judgments, configured model identities,
provenance and artifact links. Missing or invalid handoffs still allow the ordinary operational
report to run, with the judged section explicitly unavailable. A complete measurement can contain
negative judgments; neither it nor this receiver automatically activates any guard.

No usable strong-judge credential was available when this change was implemented. Since
2026-09-15 (W3-7) the strong judge is the founder's Claude subscription (`claude-fable-5-1` over
the subscription CLI): the Monday workflow only generates and retains the 24 attempts, the founder
judges them locally with `python -m evals.judge_readout` (the `/judge-readout` skill), and a manual
dispatch of the same workflow with `readout_b64` delivers the judged readout through this receiver
without generating anything (`backend/evals/RUNBOOK.md`, "Weekly strong-judge measurement"). An
unavailable, partial, simulated or empty report does not meet D5's first-judged-readout
prerequisite. Existing scheduled delivery is preserved; development verification uses mocked email
transport and makes no live send or job dispatch.

### Version-stale summary drain (D4)

`backend/scripts/refresh_stale_summaries.py` is the job-side counterpart of the admin
`refresh-stale` endpoint for corpus-sized backlogs: the same shared staleness encoding
(`app/services/summary_refresh.py`), the same in-place regeneration through the one orchestrator
with `force_regenerate=True` (bookmarks survive; keep-better refuses to downgrade a summary the page shows), bounded by
`--limit` and `--max-seconds`, random candidate order, honest per-filing outcomes
(`updated` / `kept_by_gate` / `failed` / `deferred`), and a durable attempt in
`earningsnerd_job_runs` under `refresh-stale` (a run with any failed regeneration is recorded as
failed; it is not in the weekly job-health cadence table because it is not scheduled). It runs on
the pregenerate job image, which carries the generator credential and the database:

```bash
gcloud run jobs execute earningsnerd-pregenerate --region us-west1 --args=scripts/refresh_stale_summaries.py            # dry run: breakdown by stamp and form, no model call
gcloud run jobs execute earningsnerd-pregenerate --region us-west1 --args=scripts/refresh_stale_summaries.py,--execute,--limit,15,--max-seconds,1200
```

Every executed generation is paid provider spend; repeat bounded executions until `stale_total`
is zero. The script refuses `--limit` above 15 unless `--unbounded-batch` is passed, which is
reserved for after the job's memory has been raised: on 2026-09-16 a 48-row
execution was killed by the container's out-of-memory event after 22 sequential regenerations
(memory grows across generations in one process); Cloud Run's task retry then finished the rest,
and the killed attempt's ledger row stays `running` by design. Results land as a JSON line in the
job's logs (`jsonPayload` with `stale_total`) and as counters in `earningsnerd_job_runs`. A `SUMMARY_PROMPT_VERSION` bump (for example `summary-2026-09-n`, the armed evidence
auto-snap) makes every earlier row stale and is what schedules a drain; nothing regenerates on
read.

### Scheduled job outcomes and universe coverage (WS-7)

Every scheduled job script records an attempt in `earningsnerd_job_runs`, using a transaction
separate from its business work. The logical names are `pregenerate`, `filing-scan`,
`filing-digest`, `backfill-facts`, `earnings-calendar-refresh`, `earnings-day-alerts`, and
`notable-filings`. The weekly report records `data-quality-report` separately, even though it
runs on the filing-digest Cloud Run job, and the Item 1A extraction batch the real-time scan runs
behind `ENABLE_SECTION_CHANGES` records `section-extraction` on its own row (a failed batch fails
that row, not the scan's execution; it joins `JOB_CADENCES` when the flag flips). SIC backfill, financial remediation, the reconciliation-flag audit and the
operator's section backfill similarly use `backfill-company-sic`, `remediate-financials`,
`reconciliation-flag-audit` and `section-extraction-manual`; these ad hoc identities cannot satisfy a
scheduled heartbeat.

Each attempt records start, completion, status and numeric counters. Returned provider/send/
extraction failures and failed commits mark the attempt failed and make the CLI exit nonzero;
services retain their best-effort return behavior for HTTP callers. Dry runs are recorded as
`dry_run`, never success. An abruptly killed process can leave `running` without completion.
Heartbeat storage failures fail the execution; they cannot manufacture success. No provider
payload, exception text, email address or identifier list is stored in heartbeat counters.

The existing `.github/workflows/data-quality-weekly.yml` runs Mondays at 13:00 UTC and emails the
report through `scripts/data_quality_report.py`. Its new report sections mean:

| Field | Definition |
|---|---|
| Company coverage | Distinct normalized committed-universe tickers with a Company row / committed tickers |
| Summary coverage | Distinct committed-universe tickers with any stored Summary / committed tickers; does not assert latest-period or full-quality coverage |
| Stub ratio | Stored filings without any Summary / stored filings, restricted to universe companies; a partial Summary is not a stub |
| Universe age | UTC days since committed `index_membership.json.generated_on`; invalid/future date is unavailable |
| Per-job last success | Most recent completed `succeeded` attempt, unaffected by later failed or dry runs |
| Stale job | No successful completion, or last success older than twice the maximum schedule interval |

The maximum intervals are one hour for scan, one day for digest/calendar/alerts, seven days for
pregeneration/facts/report, and fourteen hours for Notable's longer overnight gap. All expected
jobs appear even if never observed. In particular, Notable remains never observed until the
founder creates and runs it. The current report attempt appears running in its own email; the
last-success field refers to the previous completed report. Empty universe/filing denominators
produce unavailable percentages, not a fabricated clean zero. Tick-count aliases normalize
hyphens to dots, using the same helper as the committed universe filter.

For a read-only report without sending email, the founder can execute the report script with
`--dry-run` through the existing jobs channel and retain its JSON output. A healthy deployment
alone does not prove scheduled scripts have executed: retain actual attempt/report output before
claiming live coverage or heartbeat success.
