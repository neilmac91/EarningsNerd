# Separate durable summaries from account-mail delivery

Durable summary generation has its own Cloud Tasks route and private worker role. A summary
handoff cannot fall back to the background queue. Existing account mail, filings, history,
companyfacts and internal-job envelopes continue using their existing background route.
The summary worker accepts only summary envelopes and empty probes; the background worker
refuses summary envelopes. Refusals return 503 so a misrouted delivery is not acknowledged as
completed. They log the closed task kind, never the payload.

This protects background queue and worker slots from **durable-summary tasks**. It does not
establish a mail-latency service level: other background jobs can still be long, and both
services can contend on shared database/provider infrastructure. Legacy direct precompute is
not a durable-summary task; pause or migrate those producers during the ownership transition
described in [durable summary generation](durable-summary-generation.md).

## Configuration contract

| Setting | Default | Intended placement |
| --- | --- | --- |
| `TASKS_QUEUE`, `TASKS_WORKER_URL`, `TASKS_INVOKER_EMAIL` | Existing background values | Preserve on all current producers and the background worker; also present on the summary worker so the isolated route can be compared with the background route |
| `TASKS_PROJECT_ID`, `TASKS_LOCATION` | Existing project/region | Shared placement; isolation is within that project/region |
| `SUMMARY_TASKS_QUEUE` | Empty | Explicit summary queue on every summary producer and the summary worker |
| `SUMMARY_TASKS_WORKER_URL` | Empty | Explicit summary worker's canonical HTTPS Cloud Run origin, on every summary producer and the summary worker |
| `SUMMARY_TASKS_INVOKER_EMAIL` | Empty | Explicit service-account identity for summary deliveries; no fallback to the background identity |
| `TASKS_WORKER_ROLE` | `background` | `summary` only on the separate summary worker and its inherited child environment; the existing worker stays `background` |
| `TASKS_WORKER_PROCESS` | Existing value | True on each private worker; API and scheduled producers retain their existing roles |

The summary route requires a complete valid background route and a complete valid summary
route. Queue names and normalized worker origins must differ. Invalid or incomplete routing
fails before the metadata credential read or Cloud Tasks request. Optional trailing slash,
host case and HTTPS port 443 cannot disguise an identical worker origin. Existing background
delivery does not require any summary configuration. Normalization is used only for that
comparison: the HTTP target and OIDC audience retain the configured URL spelling with its
trailing slash removed, as older queued tasks were minted. A new image must not invalidate
those tasks merely by lowercasing the host or removing an explicit port from the audience.

Task naming preserves the existing hash of server-owned dedupe key and envelope. The full task
name additionally belongs to its queue namespace. Moving a queue does not deduplicate against
the old queue, so changing routes while work is outstanding still requires the existing
pause/drain and receipt reconciliation procedure. A 409 from the selected queue confirms only
that selected queue's same-name task.

The worker selects OIDC audience and expected service-account email from its configured role,
never from the incoming body or queue headers. The HTTP receiver checks the kind before
calling the process supervisor; the supervisor repeats the check before spawning a child,
and the business runner repeats it in the fresh child before executing work. A probe remains
an ingress/authentication check: it bypasses business execution and the supervisor's busy
lock, so it is not evidence of spare worker capacity or successful summary delivery.

## Proposed production resources and transition

The following is a configuration proposal, not an applied change:

- A dedicated queue `earningsnerd-summaries`, separate from `earningsnerd-background`.
- A private service `earningsnerd-summary-worker` using the exact reviewed backend image and
  `task_worker_main:app`, role `summary`, with its own service-level concurrency/instance
  limits and a separate summary invoker service account.
- Preserve the existing background worker, queue, account-mail identity and broader
  `DURABLE_TASKS_ENABLED` value. Do not copy the summary role into the shared scheduled-job
  deployment map.

The application rejects identical origins, but different Cloud Run tag or service URL forms
can still address one service. Before activation, read back **distinct service resource
identities**, images, traffic revisions, roles, private IAM policy, OIDC audiences/identities,
queue targets and capacity. A URL inequality or a successful probe is not that proof. Separate
identities are the operational proposal; code permits an explicitly configured common invoker
with different audiences, and does not claim IAM isolation from the route fields alone.

Provision the isolated resources and deploy the compatible image before enabling durable
summary admission. Keep both prewarm caps zero. Apply routing to the API, filing-scan/recovery
producers, worker retry path and any other producer inventory entry, then verify it in each
actual role. Keep ordinary image updates additive and preserve all four new controls; the
rollout-preservation gate covers them. The optional CI step `Update configured summary task
worker image` runs before the API deployment. With repository variable `GCP_SUMMARY_WORKER_URL`
unset, it performs no cloud operation. Once that non-secret variable names the provisioned
service's canonical URL, it requires the fixed `earningsnerd-summary-worker` service to exist
and match that URL, to run a single container, and to pin `SEC_RATE_LIMIT_PER_SECOND` and
`EDGAR_RATE_LIMIT_PER_SEC` each to the plain value `1` (no `valueFrom`). It then updates only its
image and additive `SENTRY_RELEASE` marker. It moves
traffic to the new revision and clears old revision tags. It does not create a service or change
its role, feature controls, secrets or capacity. Lookup, identity mismatch, an unpinned SEC budget or image-update
failure stops the step before subsequent mutations; the API deployment follows only success.

Run the bounded isolated actual-delivery rehearsal before directing user work to this queue.
It must demonstrate private OIDC delivery, real child completion, ambiguous create/redelivery,
worker interruption and database fencing, as well as mail progress during a held summary.
No cloud infrastructure, IAM, production flag, queue capacity or scheduler change is performed
by the code implementation. The separate acceptance tooling owns the exact resource budget
and approval packet.

Rollback pauses new summary admissions and drains accepted jobs on the summary queue/worker.
Do not redirect an outstanding summary to the background queue, or disable broader task
delivery to roll back summaries. Stop incompatible direct generation producers and reconcile
old queue deliveries before changing ownership modes.

## Verification scope

`test_summary_task_isolation.py` exercises the real task naming and routing with Cloud Tasks
HTTP mocked, incomplete/shared routes before metadata access, every pre-existing task kind,
role-specific signed identity checks, and parent/child kind restrictions.
`test_summary_worker_http_isolation.py` uses two actual loopback HTTP worker processes and the
real subprocess supervisor. It holds a synthetic summary child while a synthetic account-mail
child completes on the other worker. It replaces only the Google public-key source and business
child command, and makes no live SEC, model, database or mail call. It proves the code/process
boundary offline, not Cloud Tasks persistence, deployed Cloud Run isolation or production latency.
`test_summary_worker_deploy.py` executes the actual CI shell step against a fake `gcloud`
boundary: unset configuration makes no calls, failed lookup/mismatch changes nothing, failed
image update does not move traffic, and success changes exactly the reviewed image/release
marker before traffic. The ordinary-deployment preservation inventory covers all six maps.
