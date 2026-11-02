# Isolated summary delivery acceptance

This is a bounded **synthetic** rehearsal of the real Cloud Tasks adapter, private
OIDC receiver, process supervisor, existing summary orchestrator, job leases,
usage settlement and persisted result reads. It does not establish SEC
availability, model quality, real email delivery, production throughput or a
production recovery schedule. The fixed REGN identifiers label synthetic records
in a separate database; no production business record is read or changed.

## Review and execution

Planning reads stable production revision/image metadata and secret **references**
and the production PostgreSQL major version. It neither reads secret values nor creates resources. The manifest binds
the immutable image, current reviewed source fingerprints, runtime fingerprint,
fixed resource identities, numeric run ID, nonce, limits and two-hour approval expiry. Schema2 adds a run-bound temporary SQL instance; schema1 plans cannot authorize this larger resource set, including through cleanup.

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

Planning also runs the current Ops identity's project `testIamPermissions` with
exactly `cloudsql.instances.connect/create/delete/get/list`. The manifest retains
only these required/granted/missing names, not an IAM policy or principal dump.
Missing permissions leave a reviewable resource plan; apply requires a fresh,
matching all-granted result before any mutation. Grant changes require a new plan.
No permission or broad Cloud SQL Admin role is granted automatically. `list` is a
conservative compatibility prerequisite because Google's current permission matrix
and audit reference disagree on whether operations-list needs `get` or `list`.
Standalone cleanup does not require unrelated create/connect permissions.

The controller obtains a private token and its actual expiry through the SDK's
`config config-helper --force-auth-refresh` credential projection. It refreshes
120seconds before expiry, caps a cache interval at one hour, and invalidates the
cache once on cleanup entry. The bounded refresh subprocess consumes the same
remaining request/phase deadline as HTTP. An HTTP401 invalidates the cache but
does not replay the current operation; later independent/reconciliation requests
may refresh. Credential output never enters plans, receipts, argv or logs. This
uses the same SDK refresh interface as Google's
[container registry helper](https://github.com/google/go-containerregistry/blob/main/pkg/v1/google/auth.go),
without extending token lifetime or changing the shared feedback controller.

## Fixed resource contract

All resources are in `earnings-nerd/us-west1`:

| Resource | Count and bound |
| --- | --- |
| Cloud Run | Three private services: `earningsnerd-summary-verify-api`, `-background`, `-summary`; one vCPU each; API/background 1 GiB, summary 2 GiB; minimum zero, maximum one instance, concurrency one, request timeout 600 seconds |
| Cloud Tasks | Two queues named `earningsnerd-summary-verify-{background,summary}-RUN_ID`; concurrency one each, 0.2 dispatches/second, three attempts, 30-second retry interval, one-second retry duration |
| Service accounts | `en-summary-verify` runtime and `en-summary-verify-invoker`; no keys; runtime gets scoped queue enqueuer, isolated secret access and Cloud SQL client |
| Secret Manager | `EARNINGSNERD_SUMMARY_VERIFY_DATABASE_URL` and `EARNINGSNERD_SUMMARY_VERIFY_SECRET_KEY`; one new version each, numeric bindings |
| Cloud SQL | One temporary instance `earningsnerd-summary-verify-db-RUN_ID`, PostgreSQL15, Enterprise, zonal, `db-custom-1-3840`,10GBSSD; one restricted database/login role `earningsnerd_summary_verify`, connection limit12 |

Cloud Tasks stops when both attempt and duration conditions are met. The
one-second duration is below the 30-second retry interval, so it cannot extend the
three-attempt ceiling. Queue names include the originating run ID to avoid queue
deletion tombstones colliding with a later rehearsal. Workers are verified by
actual distinct Cloud Run resource identities, not different URL aliases.

Before fixtures run, each service must deny an anonymous request and a valid
Google identity token for another service's audience and a correct-audience token
for the runtime identity, which has no intended invocation grant. It must then
accept its invoker identity's own audience. Twelve health requests check effective
ingress and reject unexpected effective invocation grants. Real
task delivery still passes the existing receiver's signed Google-token verifier.

The runtime identity checks its own metadata identity and effective access to
every production secret reference discovered by the plan; any production-secret
access refuses startup. Only the two temporary secrets are mounted. All model,
mail and telemetry credentials are absent/disabled. A Python socket guard allows
only fixed Google control endpoints; uvicorn uses Python's asyncio loop for those
Python socket boundaries. The SQL connection is the fixed Unix socket
and restricted role. This guard is not an OS firewall or native-code sandbox.

## Database admission and credential boundaries

The approved controller creates a separate run-named instance. Its reviewed
manifest fixes PostgreSQL15, one vCPU/3840MB, zonal availability and10GBSSD.
Storage growth, backups, PITR, final/retained backups and deletion protection are
disabled. Public IPv4 uses no authorized networks and requires Cloud SQL
connectors, encrypted transport and the per-instance Google CA. This is connector
access over public-IP transport, not private-IP networking. Creation must finish
and its complete configuration must read back before SQL provisioning starts.
Production engine metadata must confirm PostgreSQL15; another major refuses.

A new administrator password is generated only in runner memory and the instance
insert request. No production credential or admin secret version is read or
created. The proxy's target and runtime socket derive from the approved run ID;
changing both the runtime URL and its environment cannot redirect them to another
instance. The runtime receives only the newly restricted database password.
`psql` receives credentials through its environment and SQL over stdin; SQL uses
a SCRAM verifier rather than the reusable password. The proxy binary is pinned.

Before database/role provisioning, admission on the temporary instance requires:

```
active_connections + 12 + 5 <= 70% * usable_max_connections
usable_max_connections = max_connections - reserved_connections
```

Three parent instrumentation pools, at most two worker-child pools and one API
recovery lock connection normally use six connections, with pool size one and
no overflow. Twelve is the hard role ceiling, including startup overlap. The five
additional connections and30% margin are unchanged. The administrative observer
is included in the active count. This is a point-in-time admission check, not a
fleet reservation. Failure retains safe measured capacity fields and tears down
the temporary instance; production capacity and pool settings are untouched.

The new role has no superuser, role/database creation, replication, bypass-RLS or
inherited privileges. Provisioning audits effective access in the temporary admin
database and verifies authentication/schema permissions using the restricted
credential. Runtime Cloud SQL client IAM remains project-scoped; no instance IAM
condition is claimed. Its missing production credentials and effective denial of
the discovered production API secret references are separate boundaries.

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

The controller has a400-call/40-minute cloud API budget and an independent
500-call/25-minute cleanup budget. Google requests use at most30seconds, reduced
to the remaining deadline. On the Linux main thread a shared real-time signal
timer bounds the entire synchronous HTTP exchange, including trickled response
headers, JSON bodies and SSE lines; a socket inactivity timeout alone is not a
total deadline. Existing active timers, nested use and unsupported threads refuse
before sending a request. The prior handler is restored and the timer disarmed on
success/error. SQL create/delete each use at most600seconds; Cloud
Run operations240seconds each. The fixture client has a shared540-second window.
SQL provisioning has a shared120-second query budget, with30seconds proxy
readiness and10seconds termination. The Ops apply step allows80minutes:
40minutes control work +9minutes fixture +25minutes cleanup +6minutes local
bootstrap/shutdown allowance. Standalone cleanup allows30minutes. These bounded
waits do not claim an OS-hard deadline. Startup permission checks and bounded runtime task/JWKS/metadata
requests are separate. Resource/work limits are not a billing-account invoice
cap; failure to complete cleanup can leave resources requiring follow-up.

## Cleanup and failure handling

Apply always attempts cleanup after the instance creation attempt, including a
lost acknowledgement or failed admin/proxy startup. Create is issued once;
reconciliation requires exact purpose/run/nonce labels and matching asynchronous
operation identity. Acknowledgement alone is not completion. The same orchestration
handles standalone cleanup: independently pause queues, then remove owned cloud
resources despite individual failures. All workers must read absent before any
SQL instance deletion. SQL Admin teardown needs no database credential, proxy,
`psql` or SQL-tools installation. It deletes only the exact run-owned instance,
requests no final backup, waits for its operation and verifies actual absence.
An early404 after an ambiguous create is insufficient: unresolved creation stays
`UNVERIFIED`. Foreign ownership or retention/dependency drift is never adopted.

The project Cloud SQL grant is removed before deleting its service account,
preserving unrelated policy entries and etag. Failure leaves closed failed-stage
and residual-instance fields with explicit cleanup required. SQL uncertainty
retains identities; it does not prevent earlier independent cloud deletions.
Cleanup may use the original approved plan after expiry/source changes. The
two-hour approval expiry does not delete resources. Runner interruption can leave
continuing charges, requiring supervised execution and the exact cleanup command;
there is no recurring janitor or invoice cap in this tool.

The SQL Admin field contract was checked against Google's public
[v1beta4 discovery](https://sqladmin.googleapis.com/$discovery/rest?version=v1beta4)
and [instance-delete API](https://docs.cloud.google.com/sql/docs/postgres/admin-api/rest/v1beta4/instances/delete).
`rootPassword` belongs on DatabaseInstance, connector enforcement on Settings,
CA/SSL on IP configuration, and final-backup controls on Settings/DELETE.

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
public-ingress refusal, temporary-instance capacity refusal before database writes, paused-before-credential
ordering, SQL boundaries, and the actual summary pipeline with synthetic network
seams. Local PostgreSQL tests provide separate database privilege/cleanup
evidence. Fake Cloud API tests and local persistence tests must not be reported as
actual Cloud Tasks delivery acceptance; only a successful approved cloud run can
close that gap.
