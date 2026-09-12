# E09 remainder — proposal for founder decision

Proposal only, prepared 2026-09-08 from the repository at `1fe1f156`. No application, schema, configuration, scheduler or production change is included. E09a provides per-process generation deduplication; E09b adds per-process chat admission and metrics. The remaining engineering should ship as separate, serially verified slices: generation ownership first, then SEC admission after the egress inventory is known.

## What the code establishes

`backend/app/services/summary_pipeline.py` keeps leaders in `_inflight_generations`, uses a process-local generation semaphore, and has a 120-second pipeline deadline. Both request and background generation consume this same orchestrator. A database uniqueness constraint on `Summary.filing_id` resolves competing inserts after their work has already occurred; force refresh updates the existing row in place with its keep-better quality check. Neither prevents two processes from spending provider work on the same filing. Usage reservations in `subscription_service.py` protect account quota, not filing ownership; they must remain a separate mechanism.

`backend/app/services/sec_rate_limiter.py` holds tokens, elapsed-time accounting and its lock in memory. Raw HTTP transport owners in `integrations/sec_api.py`, `services/facts_service.py`, and the EDGAR compatibility/companyfacts paths call its existing execution helpers. The EDGAR layer also invokes SDK operations through threadpool/timeout/breaker wrappers; an SDK operation is not necessarily one HTTP request. Before claiming complete fleet coverage, instrument actual mocked outbound requests from those SDK paths and identify the supported transport hook. Counting only calls to the async limiter or importing allowlist is insufficient. Local parsing stays breaker-exempt.

The checked-in deploy command pins service maximum instances and request concurrency; Settings supplies process limits. Those are source configuration, not a new observation of effective production capacity, job overlap, rollout overlap or egress. `/metrics` explicitly reports process snapshots. The proposal does not adopt the older ledger's numerical fleet estimate as measured capacity.

## Slice A: cross-instance generation ownership

Use a small PostgreSQL lease table keyed by filing ID, shared by every caller of `stream_filing_summary`. Proposed fields are filing ID, opaque owner token, increasing fencing generation, lease expiry and completion identity/state. Use database time for expiry. Claim/reclaim and renew with conditional ORM updates in short transactions; never retain a connection, transaction or row lock while waiting for the model, SEC, another owner or a local semaphore. Keep the in-memory event map as a local optimization.

A follower waits within the existing request deadline, periodically checking the durable owner/result through fresh sessions and yielding the existing progress/error event shapes. A timeout does not grant ownership. Only the active owner can renew, release or publish. The final summary insert or force-update, content-cache publication and ownership completion must validate the fence in the same transaction; retain the unique constraint, in-place summary ID and keep-better check. Trace every earlier shared write in the orchestrator—facts, cache and progress—and either fence generation-owned writes or document why their existing independent idempotent transaction remains safe. Do not silently call every existing side effect “fenced” because final summary persistence is fenced.

Preserve the current follower/force-refresh semantics and account charging policy. A follower must release any quota reservation it did not consume; the owner must preserve the existing quality exemption and month allocation. Prove accounting behavior explicitly, including death between summary persistence and metering; do not turn this ownership slice into an unapproved billing-policy change. Locked contracts remain byte-identical; any unavoidable contract change returns to the founder before implementation.

On failed renewal or lost ownership, cancel provider work and refuse publication. With uncertain coordinator availability, fail closed for new generation: return an existing permitted persisted result when available, otherwise the existing bounded error path. This prevents a database outage from triggering a duplicate-generation stampede. Fail-open would retain availability at the cost of duplicate provider spend within the existing process/quota limits and loss of the cross-instance ownership guarantee, and is not recommended. Lease fencing can guarantee the accepted publisher, not exactly-once external provider execution: a paused old worker may overlap briefly with takeover before cancellation reaches it. The lease/renewal values must cover measured queue and cancellation behavior; this proposal sets no production duration.

An advisory lock held across generation is simpler but occupies a database connection for the whole provider wait, reversing E03's purpose. Redis or a queue introduces infrastructure, operating cost and additional delivery semantics. Retain PostgreSQL leases as the initial design unless measured database overhead makes that choice unsuitable.

## Slice B: fleet-wide SEC admission

Start with one conservative global admission domain for all identified EarningsNerd SEC callers. Do not infer separate quota domains merely because jobs are separate or observed egress addresses differ. A PostgreSQL coordinator is the lowest-infrastructure candidate: an approved rate/burst policy and shared next-eligible/token state, updated under a short bounded transaction with database time. If a permit is unavailable, return a bounded delay and close the transaction before sleeping; respect each caller's existing deadline and retry policy. Each actual outbound attempt, including SDK retries and pagination, must acquire a permit through its current transport owner. Never count CPU parsing as an SEC request or add a second raw SEC transport.

The coordinator limits admitted attempts. It does not by itself prove a strict bound on packet departure times: delayed processes can transmit previously granted permits together. Use expiring permits, discard delayed/cancelled grants without a compensating burst, and verify conservative admission behavior under pauses; if the founder requires a hard bound at a shared egress address, evaluate a central outbound dispatcher/proxy instead. That alternative introduces deployment, availability, networking and cost decisions and needs separate approval. Distinguish these guarantees in the implementation's acceptance criteria.

Fail closed when shared admission cannot be established: user paths may serve their existing valid/stale fallback and report a bounded unavailable outcome; scheduled ingestion records an error and cannot refresh last-success. Fail-open restores per-process buckets and removes the fleet guarantee exactly when coordination is unhealthy, so it is not recommended. Keep current local pacing and Retry-After behavior as additional conservative protection. Do not let retries bypass the shared gate or hold a permit through a backoff sleep.

Static per-process budget division is an alternative only if a hard upper bound on all simultaneous processes, retries and rollout overlap is established and maintained. Without that inventory it is not fleet-safe. A central coordinator's database contention and connection cost must be measured before selecting its implementation; no Cloud SQL sizing change is bundled here.

## Founder evidence and bounded decision

The founder supplies read-only configuration/output showing service revisions and traffic, min/max instances, concurrency, worker processes and pool settings; each SEC/provider-calling job's task count, parallelism, schedule, retries, timeout and overlapping execution history; and network/egress configuration plus which callers share addresses. Include relevant CI/eval/manual callers and any unrelated workload sharing the same egress domain. Retain timestamps and source revision with the evidence, and omit secret values.

Also needed: the approved aggregate SEC admission rate and burst/headroom policy for that domain, provider-key concurrency/token/request constraints and acceptable duplicate-work exposure, acceptable user wait/error behavior, and the database connection/latency budget available for coordination. Configuration, observed peaks and chosen limits must be recorded separately. Provider constraints do not imply permission to change the DeepSeek provider, capacity or pricing.

**Decision requested after that evidence is attached:** approve implementing PostgreSQL filing leases with fail-closed new generation, and a separate conservative global SEC admission slice at the recorded rate/burst and waiting budgets; or retain the current process-scoped behavior. This authorizes the described engineering only. Any proxy/NAT/Redis provision, capacity adjustment, production enablement or changed locked contract still needs its own concrete approval. Until the evidence and decision are recorded, E09 remains blocked; no speculative implementation is needed.

## Acceptance and rollout

For ownership, use independent PostgreSQL connections/processes to prove one claimant, expiry/takeover, stale-owner publication rejection, force-refresh ID preservation, follower timeout and quota release. Inject death before/after claim, renewal, publication and metering; include slow cleanup, unavailable database and old/new revision overlap. Verify no connection remains checked out during provider or follower waits. Specify the admitted external-work overlap bound separately from fenced publication correctness.

For SEC admission, test aggregate mock wire traffic across multiple API/job processes, cold start, retries, cancellation, clock skew, process pause and coordinator outage. Trace every actual network attempt through the supported SDK and raw-HTTP paths; assert deadline/fallback/job-failure behavior and bounded database overhead. Before activation, reconcile the caller inventory against the founder's effective configuration. No live SEC, email, account or job run is an engineering test under this proposal.

Each code slice gets the full backend gate including performance and the four PostgreSQL lanes, three review lenses, exactly one mutation proof for each new invariant, and byte-identical locked tests. Migrations are new, project-specific, additive and idempotent files applied through the existing ledger; fresh-model schema must agree and the triple-pass migration CI must pass. Do not edit applied migrations, perform historical cleanup or add startup DDL. Expand with enforcement inactive, verify deployment and every configured job image, then obtain the founder's activation decision once mixed-version writers are understood. Rollback disables new enforcement under founder authorization and leaves additive tables intact; no destructive rollback is required. Serialize backend releases with CI, migration tail, revision/traffic and independent health verification.

## Optional founder appendix: read-only E09 inventory

The proposal requests console evidence, so the following makes that prerequisite concrete. Run in the founder's existing Cloud Shell and paste the printed JSON. These are `describe`/`list` operations only: no job execution, deployment, configuration change or secret access. Project `earnings-nerd`, region `us-west1`, service and all eight job names are taken from the checked-in CI deploy steps and the handover. The Python wrapper prints only allowlisted metadata; it does not print environment values, commands/arguments, secret references, full annotations or raw resource documents. No agent has executed these commands.

```bash
python3 - <<'PY'
import datetime
import json
import subprocess

PROJECT, REGION = "earnings-nerd", "us-west1"
JOBS = (
    "earningsnerd-pregenerate", "earningsnerd-filing-scan",
    "earningsnerd-filing-digest", "earningsnerd-backfill-facts",
    "earningsnerd-earnings-calendar-refresh", "earningsnerd-earnings-day-alerts",
    "earningsnerd-notable-filings", "earningsnerd-retention-purge",
)
ANNOTATIONS = (
    "autoscaling.knative.dev/minScale", "autoscaling.knative.dev/maxScale",
    "run.googleapis.com/minScale", "run.googleapis.com/maxScale",
    "run.googleapis.com/scalingMode", "run.googleapis.com/manualInstanceCount",
    "run.googleapis.com/vpc-access-connector", "run.googleapis.com/vpc-access-egress",
    "run.googleapis.com/network-interfaces", "run.googleapis.com/execution-environment",
)

def read(*args):
    return json.loads(subprocess.check_output(
        ["gcloud", *args, "--project=" + PROJECT, "--format=json"], text=True))

def emit(kind, name, value):
    print(json.dumps({"kind": kind, "name": name, "metadata": value}, sort_keys=True))

def metadata(resource):
    annotations = resource.get("metadata", {}).get("annotations", {})
    return {key: annotations[key] for key in ANNOTATIONS if key in annotations}

def capacity(template):
    spec = template.get("spec", {})
    return {"annotations": metadata(template),
            "concurrency": spec.get("containerConcurrency"),
            "timeoutSeconds": spec.get("timeoutSeconds"),
            "maxRetries": spec.get("maxRetries"),
            "containers": [{"name": c.get("name"),
                            "resources": c.get("resources", {})}
                           for c in spec.get("containers", [])]}

emit("observed_at", PROJECT, datetime.datetime.now(datetime.timezone.utc).isoformat())
service = read("run", "services", "describe", "earningsnerd-backend", "--region=" + REGION)
traffic = [{k: t[k] for k in ("revisionName", "percent", "tag", "latestRevision") if k in t}
           for t in service.get("status", {}).get("traffic", [])]
emit("service", "earningsnerd-backend", {
    "annotations": metadata(service), "traffic": traffic,
    "latest_template": capacity(service.get("spec", {}).get("template", {}))})
for revision in sorted({t["revisionName"] for t in traffic if t.get("revisionName")}):
    emit("traffic_revision", revision, capacity(read(
        "run", "revisions", "describe", revision, "--region=" + REGION)))

for job in JOBS:
    data = read("run", "jobs", "describe", job, "--region=" + REGION)
    execution = data.get("spec", {}).get("template", {}).get("spec", {})
    emit("job", job, {"taskCount": execution.get("taskCount"),
                      "parallelism": execution.get("parallelism"),
                      "task": capacity(execution.get("template", {}))})
    history = read("run", "jobs", "executions", "list", "--job=" + job,
                   "--region=" + REGION, "--limit=20", "--sort-by=~metadata.creationTimestamp")
    emit("recent_executions", job, [
        {"name": e.get("metadata", {}).get("name"),
         "createdAt": e.get("metadata", {}).get("creationTimestamp"),
         **{k: e.get("status", {}).get(k) for k in
            ("startTime", "completionTime", "runningCount", "succeededCount", "failedCount", "cancelledCount")}}
        for e in history])

schedulers = read("scheduler", "jobs", "list", "--location=" + REGION)
emit("schedulers", REGION, [
    {k: s.get(k) for k in ("name", "schedule", "timeZone", "state", "retryConfig", "attemptDeadline")}
    for s in schedulers])
PY
```

A missing field is unknown/unset, not zero or the source default. A missing resource or permission stops the script with its error; retain the completed output and the error, and do not provision anything to make it pass. The twenty-execution history per job is a bounded sample, not proof of worst-case fleet overlap. Job configuration describes the current template, which can differ from older executions. The scheduler listing deliberately omits targets and request bodies; match its safe job names against the schedules in the repository and identify any custom scheduler by name for a narrower follow-up.

These metadata cannot establish actual public egress addresses, unrelated workloads sharing an address, Cloud SQL headroom or provider-key limits. If connector/direct-VPC metadata appears, return its exact names first; engineering can then supply the narrowly scoped connector/router/NAT read commands without inventing resource names. If no network metadata appears, do not infer a dedicated or stable egress IP.

For the remaining inputs, the founder should separately record effective **numeric** `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, process/worker count and Cloud SQL connection headroom from the serving revisions/jobs and existing monitoring. Do not paste the whole environment page or connection string. The checked-in service pool pins are 12+8 and job pins 3+2; they are comparison values, not observed runtime evidence. Record only the provider account's documented request/token/concurrency quotas and the approved spending/duplicate-work tolerance, never a key. The SEC rate/burst headroom and acceptable wait/error budget remain founder decisions; no console command can determine the approved policy.

Command syntax was checked against Google's [Cloud Run job describe](https://docs.cloud.google.com/sdk/gcloud/reference/run/jobs/describe) and [execution list](https://docs.cloud.google.com/sdk/gcloud/reference/run/jobs/executions/list) references. Cloud Run [VPC connector](https://docs.cloud.google.com/run/docs/configuring/vpc-connectors) and [Direct VPC](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc) references identify the metadata being collected; the commands do not perform those configuration procedures.


## September 12 — read-only production capacity observation

The [retained console observation](review-evidence/cloud-run-capacity-2026-09-12/observation.md) supersedes the earlier inability to inspect the production account: authenticated read-only access succeeded without changing settings. Service `earningsnerd-backend` in project `earnings-nerd`, region `us-west1`, showed revision `earningsnerd-backend-00333-56s` at 100%. Revision overrides are minimum 1 / maximum 2; service scaling is separately minimum 0 / maximum 20. Observed container settings are 1 vCPU, 1 GiB, concurrency 40, timeout 600 seconds, instance-based billing, startup CPU boost enabled and database pool 12 plus overflow 8. The outbound VPC option was unchecked and ingress was All. These are observations, not proposed edits.

Assuming one process per instance, the simple serving-revision estimate is 40 potential database connections (2 × (12 + 8)); worker/process count was not observed. This excludes jobs, other services and old revisions and is not measured database headroom. Another `earningsnerd` service in `us-central1` was listed but not reconciled. Job task/parallelism limits, scheduler overlap, full fleet ownership, database headroom, outbound IP identity and budget remain unresolved. Prior-day CPU/memory charts are not a load test. An unchecked VPC option does not establish stable shared egress. E09 remains proposal-only; no capacity, scheduler, cost or generation activation is authorized. Universe-wide pregeneration and historical replay remain held.
