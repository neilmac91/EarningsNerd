# Finish only the job-owned read transaction before external work

Date: 2026-09-29 · Area: ops / database leases

The real backfill CLI held its private business connection through a two-second local fixture
fetch. The shared service also serves caller-owned transactions and flag audits, so a global
close or rollback would change their contract. Closing detaches the filing's stamp target;
rollback expires inputs already used for extraction.

Keep the release in the CLI's existing companyfacts callback. Complete only its known read-only
transaction, preserve loaded state with temporary `expire_on_commit=False`, and restore the
prior policy even on error. Refuse pending ORM writes or nested state before completion or
transport. No active transaction means no logical commit. Continue through the existing SEC
transport and writer; do not change service/audit/remediation transaction ownership.

`test_job_reporting.py` gates the real CLI/service with a one-slot pool and separate pending-state
controls. Bypassing read completion must fail at transport-entry checkout; omitting the pending
guard must fail the refusal controls. Returning a pooled lease does not close its physical
PostgreSQL connection, establish write contention, or prove fleet capacity.
