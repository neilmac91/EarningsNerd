# Isolated summary delivery acceptance

This is a bounded **synthetic** rehearsal of the real Cloud Tasks adapter, private
OIDC receiver, process supervisor, existing summary orchestrator, job leases,
usage settlement and persisted result reads. It does not establish SEC
availability, model quality, real email delivery, production throughput or a
production recovery schedule. The fixed REGN identifiers label synthetic records
in a separate database; no production business record is read or changed.

## Review and execution

Planning reads stable production revision/image metadata and secret **references**
only. It neither reads secret values nor creates resources. The manifest binds
the immutable image, current reviewed source fingerprints, runtime fingerprint,
fixed resource identities, numeric run ID, nonce, limits and two-hour expiry.

```sh
python ops/summary_delivery/manage.py plan --output summary-delivery-plan.json
python ops/summary_delivery/manage.py apply --plan summary-approved-plan.json \
  --expected-plan-sha256 REVIEWED_SHA256 --approval-nonce REVIEWED_NONCE \
  --output summary-delivery-receipt.json
python ops/summary_delivery/manage.py cleanup --plan summary-approved-plan.json \
  --expected-plan-sha256 REVIEWED_SHA256 --approval-nonce REVIEWED_NONCE \
  --output summary-delivery-cleanup.json
```

Apply and cleanup require the protected Ops job, `GITHUB_ACTIONS=true`, first run
attempt, `SUMMARY_DELIVERY_APPROVED=true`, exact hash and nonce. Apply also checks
current production revision stability, image, secret inventory and reviewed local
source. The image must contain that source: each service hashes its application
files before starting. A plan made against an older image cannot prove the new
code; runtime startup refuses the mismatch. Cleanup deliberately permits an
expired plan and changed application source while enforcing its original fixed
resource set and exact approval. The workflow separately verifies artifact
provenance. Plans and receipts are mode 0600, exclusive-create bounded JSON;
stdout contains closed status only.

Prerequisites are the existing project APIs and approved deployer permissions,
`gcloud` authentication, `psql`, and the pinned Cloud SQL proxy binary at repository
root. `SUMMARY_DELIVERY_DEPLOYER` identifies the existing project deployer service
account. The tool grants that identity act-as on the temporary runtime identity
and OpenID-token creation on both temporary identities for positive/negative
ingress checks. It never creates a service
account key. Existing resources with these names are not adopted by apply.

## Fixed resource contract

All resources are in `earnings-nerd/us-west1`:

| Resource | Count and bound |
| --- | --- |
| Cloud Run | Three private services: `earningsnerd-summary-verify-api`, `-background`, `-summary`; one vCPU each; API/background 1 GiB, summary 2 GiB; minimum zero, maximum one instance, concurrency one, request timeout 600 seconds |
| Cloud Tasks | Two queues named `earningsnerd-summary-verify-{background,summary}-RUN_ID`; concurrency one each, 0.2 dispatches/second, three attempts, 30-second retry interval, one-second retry duration |
| Service accounts | `en-summary-verify` runtime and `en-summary-verify-invoker`; no keys; runtime gets scoped queue enqueuer, isolated secret access and Cloud SQL client |
| Secret Manager | `EARNINGSNERD_SUMMARY_VERIFY_DATABASE_URL` and `EARNINGSNERD_SUMMARY_VERIFY_SECRET_KEY`; one new version each, numeric bindings |
| PostgreSQL | One database and restricted login role named `earningsnerd_summary_verify`, on existing `earningsnerd-db`; connection limit 12; no production object grants |

Cloud Tasks stops when both attempt and duration conditions are met. The
one-second duration is below the 30-second retry interval, so it cannot extend the
three-attempt ceiling. Queue names include the originating run ID to avoid queue
deletion tombstones colliding with a later rehearsal. Workers are verified by
actual distinct Cloud Run resource identities, not different URL aliases.

Before fixtures run, each service must deny an anonymous request and a valid
Google identity token for another service's audience and a correct-audience token
for the runtime identity, which has no intended invocation grant. It must then
accept its invoker identity's own audience. Twelve health requests check effective
ingress, including inherited public or all-authenticated IAM. Real
task delivery still passes the existing receiver's signed Google-token verifier.

The runtime identity checks its own metadata identity and effective access to
every production secret reference discovered by the plan; any production-secret
access refuses startup. Only the two temporary secrets are mounted. All model,
mail and telemetry credentials are absent/disabled. A Python socket guard allows
only fixed Google control endpoints; uvicorn uses Python's asyncio loop for those
Python socket boundaries. The SQL connection is the fixed Unix socket
and restricted role. This guard is not an OS firewall or native-code sandbox.

## Database admission and credential boundaries

The approved controller resolves the stable API's existing `DATABASE_URL` secret
binding, requires an enabled pinned numeric version, reads it privately and
rechecks revision/binding stability. It never assumes a secret name or creates a
production secret version. The administrative credential stays in the runner;
it is not mounted in a rehearsal service. `psql` receives credentials through its
environment and SQL over stdin, with bounded output and execution. SQL contains
a SCRAM verifier for the new random password rather than the reusable password.

Before any resource creation, admission requires:

```
active_connections + 12 + 5 <= 70% * usable_max_connections
usable_max_connections = max_connections - reserved_connections
```

The normal runtime accounting is three parent instrumentation pools, at most two
worker-child pools and one API recovery advisory-lock connection: six connections,
each ordinary pool configured size one and overflow zero. Twelve is the hard
rehearsal-role ceiling, retaining startup/overlap allowance; the additional five
connections and 30% margin protect unrelated operations. This is a point-in-time
admission check, not a global fleet reservation. The administrative observer is
included in the measured active count. Failure writes safe measured capacity
fields and creates nothing. The tool never resizes Cloud SQL or changes production
pool configuration.

Provisioning audits effective table/view/sequence, SECURITY DEFINER function and
schema CREATE privileges in the production application database. Existing PUBLIC
privileges that would grant access cause refusal; the tool does not revoke them
in production. The role has no superuser, role/database creation, replication,
bypass-RLS or inherited role privileges. Own-database schema permissions are
verified with the new credential. Database and role ownership markers must match
before cleanup. A crash between CREATE DATABASE and its ownership comment leaves
an unmarked resource requiring explicit manual review; it is never silently
adopted or dropped.

## Observable acceptance and work bounds

The API seeds exactly two synthetic filings, two generation users and one
unverified mail user, all isolated. Source acquisition, optional XBRL/section
boundaries, provider output and the mail provider are fixed offline fixtures.
The ordinary account lookup/token issuance and summary state/persistence owners
still run. A 70-second summary and a 200-second cancellation-resistant fixture
exercise mail separation and the real 80-second child deadline. The supervisor's
actual child process is observed to have a return code after its real kill/wait
path; a replacement delivery must finish the stalled filing. Fixture-child stdout
and stderr are discarded so document/provider exceptions cannot enter cloud logs;
this changes neither the supervisor deadline nor its kill/wait ownership.

Successful acceptance requires two complete persisted summaries, attempts one
and two respectively, two settled logical charges, zero remaining reservations,
mail starting during the long summary within 60 seconds of its enqueue, observed
failed child plus reap, and successful reconnect/result reads after observer
disconnect. The receipt includes source/image fingerprints and explicitly marks
source/model/mail quality unverified.

Persisted counters limit four generation POSTs, six result GETs, 100 receipt
polls, one mail job, two summary jobs, eight generation attempts, eight recovery
calls, 32 real task-create attempts and 12 admitted worker deliveries. The
database run expires after 600 seconds; the controller polls for at most 540
seconds. Queue retries and the subprocess deadline further bound each admitted
child. No live SEC, model or mail call is part of this rehearsal. The recovery
control invokes the real shared recovery owner, but it is **not evidence of an
actual Cloud Scheduler invocation or cadence**.

The controller has a 400-call cloud API budget and an independent 500-call
cleanup budget. Startup permission checks and bounded runtime task/JWKS/metadata
requests are separate. Resource/work limits are not a billing-account invoice
cap; failure to complete cleanup can leave resources requiring follow-up.

## Cleanup and failure handling

Apply always attempts cleanup after creation begins. Apply and standalone cleanup
share one orchestration: check ownership, independently attempt each queue pause,
then remove independently owned cloud resources even if one pause or deletion
fails. SQL and identities remain until every worker is confirmed absent.
The SQL role is disabled, only its own database sessions are terminated, and
unrelated sessions prevent deletion. The project Cloud SQL grant is removed
before deleting its service account, preserving unrelated policy entries and
etag. Final resource absence is read back. Failure is `UNVERIFIED`, never a
successful acceptance; the receipt lists closed cleanup stages and requires the
explicit cleanup operation. Standalone cleanup resolves SQL credentials and starts
the proxy only after cloud teardown and verified worker absence; SQL unavailability
retains the database, identities and associated project grant without preventing
the preceding cloud deletions. Unknown ownership or
unmarked SQL residue needs manual review rather than broader deletion rights.

## Paused recovery caller

```sh
python ops/summary_delivery/recovery_caller.py plan > summary-recovery-plan.json
python ops/summary_delivery/recovery_caller.py apply-paused \
  --plan summary-approved-plan.json --expected-plan-sha256 REVIEWED_SHA256 \
  --approval-nonce REVIEWED_NONCE > summary-recovery-receipt.json
```

The fixed `summary-recovery-minute` Scheduler job targets the stable API's existing
recovery endpoint. Its plan requires the API's actual pinned numeric
`INTERNAL_JOB_TOKEN` Secret Manager binding; missing, literal or `latest` bindings
refuse without inventing a replacement. The endpoint uses the existing internal
header contract. The controller creates a credential-free future-dated shell,
verifies/persists PAUSED state, then privately resolves the existing token and
sets the minute cadence/header while preserving PAUSED state. An existing
unowned, enabled or conflicting caller is refused. No endpoint invocation,
run/resume operation, feature activation or token rotation is provided.

Rotation requires a separately reviewed coordinated API binding/caller-header
change while paused, followed by matching verification. This tool creates no new
production credential. Its receipt proves paused configuration only; independent
authenticated delivery and actual cadence must be established before relying on
it for recovery. The ordinary hourly scan remains a distinct existing caller.

## Local verification

Focused unit tests cover manifest tampering, expired-plan cleanup, protected-job
guards, isolated credentials, independent cleanup budgets/failures, inherited
public-ingress refusal, capacity refusal before writes, paused-before-credential
ordering, SQL boundaries, and the actual summary pipeline with synthetic network
seams. Local PostgreSQL tests provide separate database privilege/cleanup
evidence. Fake Cloud API tests and local persistence tests must not be reported as
actual Cloud Tasks delivery acceptance; only a successful approved cloud run can
close that gap.
