# Backfill read lease and capacity inspection — combined candidate

## Combined verification on released tax main

Tested integration: `09485b8cffb650e9273d370affcf18729e092f7a`; backend tree
`bc32eac54c121977bd80b20340eecbbe5979b627`. It merges combined Ops candidate
`fdfbd490` with verified tax main `b3ca84b266e75ddcedba922f464268e90bdca743`.
The earlier combination normally merged #1020 `77408135` and #1015 `7ce7960c`.
Published histories remain intact. Only additive lesson entries required resolution in that
first merge; the tax-main merge had no conflicts. All component runtime and test bytes remain
identical to their reviewed parents, and all five locked contracts remain unchanged.

The final diff against released main contains the CLI-owned lease closure plus the
[bounded Ops capacity projection and confidentiality gate](../review-evidence/capacity-runtime-inputs-2026-09-28/README.md).
All application and frontend bytes equal that main. No pool, worker, production flag, model,
prompt, source acceptance or fleet-capacity claim changes are included.

One full pinned gate on the integration passed: Ruff 0.16.9; Bandit 1.9.4; pytest 9.1.1,
**4,070 passed, 39 skipped, 2 deselected, 40 warnings in 177.54s**, exit 0. The full suite
includes the required backend workflow readers. All **10 workflow YAML files parsed**, and
Node 22.23.2 / Vitest 5.0.1 passed **three Node lockstep tests**. Fresh bytecode caches and
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` were used. Full logs retain the known
post-summary shutdown logging diagnostic; the process exited successfully. No tests or
fault proofs were duplicated. The final documentation commit preserves the tested backend.

The unchanged component proofs remain: privacy child-output omission, **20 failed → 20 passed**;
backfill read-completion omission, **4 failed → 4 passed**; pending-state guard omission,
**8 failed → 8 passed**. Root and a fresh independent reviewer cleared the exact integration
for these gates. Hosted exact-head review and readiness remain separate publication steps.

Two earlier readiness failures remain distinct and retained. #1015 Copilot run `36500418287`
completed 18, scored and passed 17, and had one provider-timeout error; its 34 physical calls
include one unknown-cost call. The unrelated #1021 run `36516634768` completed and scored 18,
passed 17 with zero execution errors, and correctly rejected a stitched ASML text citation.
#1021 stays held at `55e89142`; none of its candidate changes were imported. Root therefore
re-sequenced this independently reviewed Ops work onto already verified tax main. Neither
failure is erased, redrawn, reclassified or claimed fixed by the consolidation.

The integration and one final gate were necessary for the changed released base and genuine
combined behavior. No push, readiness transition, provider call or production action is
recorded here. #1015 remains unchanged until a combined #1020 release is independently
verified; any eventual closure must retain its failed-ready history. Operator receipts are
under `outputs/overnight-2026-09-28/capacity/combined-1015-1020-final-handoff/`.

## Historical backfill implementation and first draft

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
