# Backfill CLI read lease — local candidate

Base: `904ca43bb7079088e4de5d765e14396081c6fb04`. Only `_main`'s private session gains a fetch
closure through the existing `companyfacts_fetcher` seam. It completes a known read-only
transaction without detaching or expiring loaded inputs, restores the prior expiration policy,
refuses unexpected pending/nested state, and invokes the existing companyfacts transport.

The shared facts service, internal trigger, flag audit, dry-run semantics, remediation, summary
hook, writer and ledger remain unchanged. Per-filing facts and stamp still commit together.
The benefit is shorter checked-out lease and idle-transaction time during fetch. Physical
PostgreSQL pool slots, API pool capacity, SEC/provider capacity and fleet headroom are unproved.

The existing `test_job_reporting.py` home has one actual-CLI/service lease gate and a separate
pending-state guard gate. A single-slot QueuePool checks that transport can borrow a separate
read connection, while exact facts/stamps/order/idempotence/cache and durable ledger outcomes
remain correct. Both expiration policies, unavailable source, completion/transport errors and
no-active-transaction behavior are covered. Original tests and all locked contracts are intact.

The two required mutations run only after this candidate is committed: bypass read completion,
then omit the pending-state guard. Each must fail its own gate before byte-identical restoration.
The operator retains exact committed identities, fault patches, logs and pinned full-gate results
under `outputs/overnight-2026-09-28/capacity/backfill-read-lease-candidate/`. No live job, additional
capacity experiment, provider call, push or publication is authorized by this record.
