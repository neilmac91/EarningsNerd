# Durable exact-filing summary generation

This is an additive, disabled-by-default generation path using the existing PostgreSQL database and `stream_filing_summary` orchestrator, with a dedicated Cloud Tasks queue and private summary worker. Enablement requires both `SUMMARY_DURABLE_GENERATION_ENABLED` and `DURABLE_TASKS_ENABLED`, plus the explicit isolated route below. Production activation remains held pending the ownership transition and operational acceptance; an ordinary image release does not enable it.

## Ownership and billing

`ensure_job` takes the filing lock, serves a ready source-safe summary or joins its existing job, then admits new work. The job table has one unique filing ID across all prompt versions. Task payloads contain only the server-generated job ID and generation number, never client-supplied source URLs, user snapshots or force flags. The private worker loads these from the persisted job and revalidates the account.

An account lock serializes new jobs for different filings. Creation checks current allowance and a bounded pending backlog (default three). It does not consume a quota unit while waiting in the queue. The worker obtains the existing short usage reservation immediately before generation; an entitlement change or exhausted quota can therefore refuse a previously queued job before provider work. Ready reads and shared joins do not consume generation admission or usage.

The job row journals reservation, charged month and charge state. Conversion of a reservation, the monthly counter increment and the receipt commit in one transaction. Recovery of a charged job reuses its receipt. Refunds are idempotent and use the original charged month. The final Summary write holds the same job lock while validating the generation and lease token, and commits its terminal job receipt and usage settlement together. An expired worker cannot charge, refund or publish another owner's result. Short transactions never span SEC, provider or queue network calls.

A browser is only an observer. Closing its SSE stream neither cancels the private worker nor consumes another generation. Explicit authenticated retry can reopen a failed job after a persisted 60-second cooldown, subject to the same quotas/backlog/admission; it does not request a paid refresh of an already ready result. Automatic retries have their own finite attempt and age limits.

The authenticated generation POST accepts `retry_failed=true` for the reader's explicit Retry or Regenerate action; page-load and transport reconnects omit it and observe a failed job without reopening work. An explicit forced refresh is never automatically replayed after an ambiguous transport failure; a 401 refresh may repeat the original intent because authentication denied admission first. `force=true` retains the separate Pro refresh policy. A pending dispatch that cannot be acknowledged returns HTTP 503 with `Retry-After: 5`, retaining the same job for repair. Each SSE observer has at most 240 seconds before an actionable reconnect response; the worker remains independent. Request evidence names observer disconnection rather than generation cancellation. The public progress GET reports persisted job identity/status and accepts a terminal result only when its matching Summary is ready; a retained older Summary cannot complete an active refresh.

## Delivery and bounded recovery

`SUMMARY_TASKS_QUEUE`, `SUMMARY_TASKS_WORKER_URL` and `SUMMARY_TASKS_INVOKER_EMAIL` must be explicitly configured alongside the complete background route. The summary queue and normalized worker origin must both differ from their background counterparts. Invalid, missing or shared routes fail before credentials or queue network access; summaries never fall back to the background queue. `TASKS_WORKER_ROLE=summary` selects the summary worker's OIDC audience/identity and permits only summary envelopes and empty probes. The default `background` role rejects summaries. Kind checks run at the HTTP receiver, process supervisor and child runner; a mismatch returns 503 rather than acknowledging completion.

Origin comparison normalizes host case, HTTPS port 443 and trailing slash, while the task target and OIDC audience retain configured spelling with the trailing slash removed. This preserves tokens on already queued deliveries. Different Cloud Run aliases may still address one service: verify distinct service resources, private IAM and actual routing before activation. An empty probe proves authenticated ingress, not spare capacity or business completion. See [summary task isolation](./summary-task-isolation.md).

A queued database row is the dispatch intent. Cloud Tasks creation uses a stable job/generation/dispatch identity, so an ambiguous response can be retried with the same task name. An acknowledged delivery is recorded only after task creation confirms success or the same-name task exists. A failed task creation leaves the intent for recovery and must not be presented as an acknowledged running worker.

The worker holds a renewable 90-second lease, heartbeats every 30 seconds, and can be replaced only after expiry. Transient typed failures schedule a new task after the greater of the source cooldown and exponential backoff, with bounded jitter. Default limits are four attempts and one hour from admission. Typed 404/publication delay, 429, transient 5xx and network failures can retry; source403 and parse defects stop automatic attempts. A source cooldown longer than the automatic horizon remains on the terminal receipt, so manual retry cannot evade it. An unrepresentably distant cooldown becomes a terminal hold at the maximum supported UTC timestamp, with no scheduled retry; clearing that hold requires operator review and evidence that the source refusal no longer applies. Exhaustion becomes a terminal failure; reconnecting does not silently start a fresh paid job.

`recover_due_jobs(limit=20)` repairs unacknowledged intents, sufficiently stale acknowledged intents, and expired worker leases. Its batch is capped at 50; acknowledged future retries do not crowd out due work. The stale dispatch threshold defaults to 300 seconds. This function requires a caller: the existing scheduled filing scan and authenticated internal recovery endpoint are the integration seams. There is no independent recovery scheduler created by this module. The actual failure-to-recovery latency includes the configured scan/recovery cadence, queue delay and lease expiry. Verify that cadence before enabling; a five-minute threshold does not itself guarantee a five-minute recovery time.

## Activation requirements

1. Apply the additive migration with the normal migration runner. Leave the feature flag and all paid prewarm caps disabled.
2. Deploy compatible API, background worker and separate summary worker revisions with their intended roles. Drain old browser-owned generation and legacy direct precompute writers before activation: old binaries cannot honor a new fencing row. Route all paid production generation producers through the coordinator when the flag is enabled. The central orchestrator refuses calls without a valid durable lease before SEC/provider work, including legacy background/precompute entry points in the new revision; pause and drain or migrate those producers before activation. Inventory schedules, in-flight executions, command overrides and manual/admin entry points; zero optional prewarm caps do not disable legacy pregenerate/precompute. An explicit ready-result refresh records fresh-XBRL intent separately from an unready-result repair.
3. Confirm the scheduled recovery caller, private worker authentication, queue acknowledgment, redelivery, and staged worker restart behavior. Prove distinct summary/background queue and service resources, not just URL inequality. Account mail retains its background queue; measure its latency during summary work because other background jobs and shared database resources can still delay it.
4. Establish shared SEC request admission and cooldown across every API/worker/library path. A shared job deduplicates popular filings; it does not enforce an aggregate SEC request limit for distinct filings or enrichment siblings. The optional fleet gate spaces admissions, not socket writes after a paused process or connection-pool wait. Verify actual outbound request rate and pool behavior under the canary workload before activation; do not claim a strict physical rate from admission timestamps alone.
5. Validate source readiness, exact-accession 8-K exhibit coverage, failure visibility, charge/refund receipts, and fleet concurrency in a controlled canary before expanding. Size queue/worker capacity from observed latency and burst demand, not solely from per-instance concurrency.
6. System preparation requires an explicit bounded watched-filings cohort and a configured spend budget. `SUMMARY_PREWARM_MAX_PER_SCAN` and `SUMMARY_PREWARM_MAX_PER_DAY` both default to zero. The global UTC-day budget row serializes admissions across the fleet in the same transaction as job creation. Joins and ready reads consume no admission; failed attempts and jobs never replenish it. With a daily cap D and attempt cap A, at most D×A generation attempts can originate from that day’s admitted jobs. Attempts can run after UTC midnight and provider-internal requests/retries can exceed one per generation attempt, so this is an admissions/attempt ceiling, not a same-day dollar ceiling. Review the configured worst-case provider retries, token limits and per-attempt cost before setting either preparation cap above zero. User usage counters are never charged for system jobs.

`SUMMARY_NEW_JOBS_PAUSED` defaults to false and provides an admission-only drain control. When true, ready reads, active joins, existing durable workers, dispatch repair and scheduled retries continue; new jobs, forced refreshes and explicit failed-job restarts are refused before admission/quota/budget consumption. System preparation selects no new cohort. Legacy generation also refuses new work while paused, after its ready/join checks.

For rollback, first set `SUMMARY_NEW_JOBS_PAUSED=true` on every admission-serving revision and set both prewarm caps to zero, keeping durable mode and task workers enabled. Verify all admitting revisions received the pause and drain any older revision that does not understand it. Drain or deliberately fail/reconcile every queued, retry-wait and running summary job, including reservation/charge receipts. Verify no old provider runs, active leases or outstanding summary task deliveries remain before switching both API and worker revisions to `SUMMARY_DURABLE_GENERATION_ENABLED=false`. Only then unpause new legacy generation. Disabling the durable flag alone immediately selects legacy generation; it is not a safe admission pause and must not overlap live durable writers.

## Deployment ownership and preserved controls

An ordinary release must preserve the deployed summary/SEC controls. The five existing image-update
commands and optional sixth summary-worker command in `ci.yml` use additive `--update-env-vars`
maps and omit the held controls, including summary routing and worker role. That
preserves an existing override; it does not establish its value. Adding `false` or `0` to a map
would reset a live value, just as adding `true` would enable it. The preservation gate in
`tests/unit/test_summary_rollout_preservation.py` holds all six commands to additive
maps and rejects changes/removal of the held controls or replacement environment/secret maps.
It also finds literal mentions outside those maps in workflow source. Console edits, scripts
invoked indirectly, image ENV, constructed command/key names and old executions remain outside
that source gate. Read back the actual resources and exact image defaults separately.

The optional `Update configured summary task worker image` step runs before API deployment.
With repository variable `GCP_SUMMARY_WORKER_URL` unset it performs no cloud operation. Once
configured, it requires the fixed `earningsnerd-summary-worker` service's canonical URL to match,
then updates its image and additive `SENTRY_RELEASE` only, moves traffic to latest and clears
revision tags. It does not provision the service or change routing, role, feature flags, secrets
or capacity. Resource preparation and activation remain separate operations.

The later activation change revises this gate and the complete matrix below together, with
the approved values, caller cadence and operational acceptance. It must not copy one value
blindly onto heterogeneous roles. In particular, the broader `DURABLE_TASKS_ENABLED` controls
existing mail and other jobs; its current API/worker value must survive a summary rollback.

| Process and deployment map | Summary ownership and work | Activation dependency |
| --- | --- | --- |
| API; `Deploy Cloud Run service` | Browser admission/observation, internal recovery endpoint, admin refresh, legacy internal precompute fallback | Durable summary admission needs both durable flags and complete background/summary routes. Pause and drain direct/admin generation before enabling ownership. |
| Background worker and its task subprocesses; `Update configured private task worker` | Internal scan/precompute, account mail and other background envelopes; rejects summary envelopes | Keep role `background` and preserve broad task delivery/mail. Any recovery/preparation handoff needs the isolated summary route. Direct precompute does not acquire a summary lease and must be paused/drained or migrated. |
| Separate summary worker and its task subprocesses; `Update configured summary task worker image` | Summary task lease owner, retry handoffs and empty probes; rejects background envelopes | Role `summary`, both durable flags and complete background/summary routes must reach the child. Provision/read back the distinct service before setting `GCP_SUMMARY_WORKER_URL`; the optional image map does not configure it. |
| Pregenerate; `Update pregenerate job image` | `pregenerate_examples.py` → precompute → headless pipeline; operator refresh-stale and other command overrides | This is a direct generation producer, not a durable summary producer. Pause its schedule, drain executions and prevent manual direct generation during transition. Do not enable its broad task switch merely to make maps match. |
| Filing scan; shared scheduled-job update map | Discovery/delivery, bounded preparation and end-of-scan recovery | Preparation/recovery need both durable flags and a working queue capability; zero prewarm caps are retained. Discovery does not establish summary readiness. |
| Filing digest, calendar refresh, earnings-day alerts, notable filings, retention and feedback cleanup; shared scheduled-job update map | Other scheduled work; the map is shared even by jobs with no summary producer | Preserve existing delivery controls. SEC coordination must cover every actual SEC caller; a shared map alone does not prove transport coverage or runtime process count. |
| Backfill facts; its own job update map | SEC/companyfacts work; also the operator maintenance channel | Include it in shared SEC placement and drain old/overridden executions. The scheduled entrypoint is restored by deployment, but an in-flight override is not replaced. |
| Local/operator scripts and old revisions/executions | May invoke the same transports or headless generator outside the declared deployment maps | Inventory and stop incompatible writers explicitly; neither source checks nor a new service image fence an old binary. |

The precompute producer chain is `precompute_service.precompute_one` →
`generate_summary_background` → `stream_filing_summary`; pregenerate and internal precompute
use it. Admin stale refresh and `refresh_stale_summaries.py` enter at
`generate_summary_background`. When durable mode is enabled,
the orchestrator refuses a call without a valid durable lease before source/model work.
That is a safety barrier, not a migration of these producers. Leaving an old or flag-off
producer running would defeat the ownership transition.

## Proposed independent recovery caller

This is a reviewable configuration proposal, not a provisioned schedule. Approval and the
remaining delivery/latency evidence are required before applying it. Inspect the fixed name
and any existing recovery callers first; do not silently replace an existing resource.

| Field | Proposed value or prerequisite |
| --- | --- |
| Resource | Cloud Scheduler `summary-recovery-minute`, project `earnings-nerd`, location `us-west1` |
| Schedule | `* * * * *`, timezone `Etc/UTC`; initially paused until the approved ownership transition |
| Target | HTTPS POST to the verified serving API's `/internal/jobs/summary-recovery`, no query/body, not the private task-worker endpoint |
| Authentication | `X-Internal-Token` matching the API's existing `INTERNAL_JOB_TOKEN`; the endpoint returns 401 for a wrong/missing value and 503 when unconfigured |
| Secret handling | Resolve the API's existing approved secret binding inside the reviewed provisioning process, send its value to Scheduler without shell tracing, command-line values, logs or retained payload artifacts; store only header presence in evidence. A presence-only unresolved secret reference does not mean the token is absent. Scheduler stores a header value, not a Secret Manager reference, so rotation must update the API and caller together. |
| Deadline and retries | Proposed attempt deadline 180 seconds, retry count 0, maximum retry duration 0; the next minute is the next scheduled opportunity, not a guaranteed new attempt if prior work has overrun. Validate the resulting readback rather than relying on omitted-field defaults. |
| Work bound | Existing endpoint batch 20, store cap 50 and one 20-second work budget with the drain caveats below; no model/source work in the recovery request. It only repairs task handoffs. |
| Enablement | Both durable flags must be consistently enabled for the intended API/worker/producer roles; the endpoint returns 409 while disabled. Keep both preparation caps zero. |

The existing hourly scan uses OAuth to invoke the Cloud Run Jobs API. That authentication
does **not** satisfy the recovery endpoint's shared-secret header check. OIDC presence alone
also does not authenticate this handler. The private worker separately verifies the Cloud
Tasks OIDC identity; proving one path does not prove the other.

All scan, scheduled and manual recovery calls now enter one bounded recovery scope. A
nonblocking process lock prevents local queueing; a fixed database-wide PostgreSQL session
advisory lock excludes other recovery passes. A contender returns zero dispatched without
reading candidates. The guard uses its own one-slot connection pool, zero overflow and a
250ms pool wait, with two-second connect/TCP timeouts and three-second guard statement
limits. It never borrows the last ordinary application-pool slot. Budget **one additional
transient database connection and one lazy guard thread per participating process** before activation. SQLite development
uses only local exclusion and does not establish fleet ownership.
Guard operations use one lazy thread of their own, so physical disconnect does not queue
behind unrelated request-pool waiters; the local permit bounds its submissions.

The pass has one 20-second async budget covering ownership acquisition, candidate selection
and every sequential handoff. Recovery's job transactions receive local statement limits of
at most three seconds and row-lock limits of at most one second, clipped to the remaining
budget; normal dispatch keeps its existing behavior. There is no open PostgreSQL transaction
or row lock across queue HTTP. Immediately before each queue handoff the caller checks the
deadline and its live guard session. On timeout, queue/storage failure or cancellation, it
drains actual synchronous workers before physically closing the owning guard connection and
releasing the local permit. Session advisory ownership is not returned to a reusable pooled
connection, and PostgreSQL releases it after a process crash/disconnection. Timeout/storage
refusal uses the existing internal endpoint's safe 503 path; successful calls keep the integer
count of confirmed handoffs. No new generation occurs in the recovery caller.

The 20-second budget is below the internal route's 30-second middleware timeout, but it is
**not a hard process/remote-work kill guarantee**. Cancellation cannot terminate a running
Python SQL thread, so cleanup waits for it; ordinary pool/connect waits, driver transport
behavior and an OS pause can extend cleanup. The guard remains held while that work drains.
A queue create already accepted remotely can complete after the HTTP await is canceled.
A disconnected PostgreSQL lock session can also release ownership before its old process
notices; the next checkpoint refuses further local handoffs, while an already in-flight one
may still finish. Per-job fencing and deterministic task names remain the authority for
those ambiguous deliveries. Do not infer physical request non-overlap or an end-to-end
recovery SLO from the advisory lock alone.

Candidate selection applies the acknowledgment cooldown before the batch limit, so recently
redispatched expired owners do not crowd out new unacknowledged work; each dispatch transaction
rechecks eligibility under its short row lock. Expired or canceled batches leave undispatched
intents for the next caller. Worker claims and result/usage writes remain independently fenced.

The intended time budget is the 300-second stale-handoff threshold, up to one minute until
the next eligible scan, bounded recovery execution, and measured queue wait, all within the
3,600-second job horizon. Use 600 seconds as a proposed maximum overdue-handoff target and
1,800 seconds as an early nonterminal-job stop threshold; these are acceptance targets, not
observed service levels. Recovery does not terminalize every overdue waiting row itself:
claim/finish enforce the attempt/age ceiling, so a queue outage can leave an old job queued
until delivery resumes. Count overdue pending jobs explicitly; their existence does not
prove another provider call after the horizon. A terminal row can retain expired lease
fields, so an active-owner read requires running status and a live lease, not field presence.

Provisioning rollback pauses this one Scheduler resource and verifies that no new invocations
start; it does not disable the broad task switch, delete accepted jobs, erase source cooldowns
or cancel active worker ownership. Summary-mode rollback follows the pause/drain procedure
above. Recovery retries must remain available until accepted work is reconciled; pausing its
only dependable caller during a drain requires an explicitly verified alternate caller.

## Isolated delivery acceptance before activation

Use a separately approved, isolated queue/worker/database configured from the exact reviewed
image and deployment role map. Existing HTTP/PostgreSQL ownership tests simulate the Cloud
Tasks boundary. The loopback worker isolation test exercises signed identity validation and the
real subprocess supervisor with synthetic children; it proves that offline process boundary,
not real queue persistence, private Cloud Run ingress or deployed resource isolation.
The runnable [isolated delivery rehearsal](../ops/summary_delivery/README.md) uses synthetic
source/provider fixtures labelled with the two REGN identities and synthetic mail transport,
with no live SEC, model or mail call. It exercises the existing orchestrator and actual queue,
receiver, subprocess and persistence boundaries. It does not reproduce the original filing's
content or establish summary quality. An unmocked source/provider fallback is a failed
rehearsal, not permission to reach that provider.

The fixed manifest admits two summary jobs, four generation POSTs, six result GETs and bounded
separate control polling. It also bounds queue attempts, task creation, admitted child
deliveries and run lifetime; HTTP counts alone do not bound those operations. Acceptance
checks held-summary mail progress, child timeout/reap and recovery, observer disconnect,
persisted result visibility and logical usage settlement. The runbook owns exact limits and
the approval/cleanup procedure. No actual cloud rehearsal has been accepted merely because
these tools or local tests pass.

Ambiguous queue acknowledgment, source cooldown and stale-owner writes have separate offline
and PostgreSQL checks below; the first cloud rehearsal does not inject every one of those
faults. Captured-source correctness, release-time source availability, actual scheduler cadence
and production burst/mail latency need their own retained evidence before those claims can be
made. Keep that broader acceptance matrix distinct from this synthetic transport result.

The code now refuses a durable summary on the background queue/worker route. That protection
requires correctly provisioned distinct services and queues; aliases alone do not establish it.
Other background jobs, legacy direct precompute and shared database contention can still delay
mail. Measure both queues' age/completion and mail-start delay during a held summary under the
approved workload, and reject activation if agreed limits fail. A dispatch rate with a burst
allowance is not a strict spacing promise. Queue/worker provisioning, capacity and IAM changes
require their own reviewed operational approval; an offline test authorizes none of them.

## Verification

`tests/unit/test_summary_jobs.py` exercises the real database receipt and existing orchestrator offline, including duplicate task delivery, observer disconnect, cooldown, outbox repair and billing rollback. `tests/integration/test_summary_job_transactions.py` uses independent PostgreSQL sessions in disposable schemas to establish create/claim exclusivity, cross-filing account limits, idempotent concurrent charge/refund, stale-owner fencing and result-commit versus reclaim behavior. Its required CI step sets `SUMMARY_JOB_TEST_DATABASE_URL`, and the PostgreSQL gate fails if configured cases skip or use sessions unlike production.

`tests/unit/test_summary_durable_route.py` exercises the authenticated route through real persisted jobs, queue acknowledgment failures and repair, ready recovery, explicit failed-job retry, stale progress, observer disconnect/deadline and both disabled-flag fallbacks. The frontend recovery flow and queued-state tests keep Retry separate from refresh and prevent a queued job from claiming that SEC retrieval has begun.

`tests/unit/test_summary_task_isolation.py` covers distinct routing, existing background envelopes, role-selected signed identities and kind restrictions. `tests/unit/test_summary_worker_http_isolation.py` holds a synthetic summary child while synthetic mail completes through another loopback worker's real supervisor. `tests/unit/test_summary_worker_deploy.py` executes the optional CI step against a fake `gcloud` boundary. These prove offline behavior, not production delivery or mail latency. `tests/unit/test_summary_recovery_bound.py` covers the recovery budget and drain behavior; the PostgreSQL transaction suite exercises recovery ownership across independent sessions and crash/disconnection.

## Optional verified source reuse

[Verified filing source artifacts](filing-source-artifacts.md) describes the separate default-off primary/exhibit store and pre-provider commit barrier. It uses this same orchestrator and does not enable jobs, prewarming, ready notifications or new resources.
