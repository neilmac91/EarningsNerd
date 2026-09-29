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

The two required mutations ran on committed `19f867386c8a38f7d4c0d3aba9bcf8f58c37ad25`:
the focused preservation gate first passed 129 cases. Bypassing read completion failed all four
lease cases at the real transport boundary (`4 failed, 55 deselected`); byte-identical restoration
passed all four. Omitting the pending-state guard failed all eight refusal cases
(`8 failed, 51 deselected`); restoration passed all eight. The script SHA-256 before and after
both faults is `ed5eaa6024de977452c8b5d82a39f5e22ec5a90765d664442e659882ebfe8faf`.
Each run used a fresh bytecode cache and no concurrent pytest. The checkout was clean after each
restoration. The operator retains exact committed identities, fault patches, logs and pinned full-gate results
under `outputs/overnight-2026-09-28/capacity/backfill-read-lease-candidate/`. No live job, additional
capacity experiment, provider call, push or publication is authorized by this record.


## Root review and draft publication

Pinned Ruff0.16.9 and Bandit1.9.4 passed at `066c023f`. Full pytest9.1.1 passed
3,946 tests, with39 skipped,2 deselected and40 warnings in167.79 seconds, exit0.
Root verified all19 retained evidence files and completed correctness, repository-rule
and gate reviews with no remaining actionable finding. The final documentation commit
keeps the tested backend bytes.

Root authorized draft publication to obtain independent hosted review while main
remains `904ca43b`. This supersedes the earlier local-candidate publication boundary
only. Any intervening main changes require integration and appropriate verification
before readiness. Ready-stage fidelity and serial deployment verification remain
required. This change establishes job-local lease behavior, not fleet capacity.
