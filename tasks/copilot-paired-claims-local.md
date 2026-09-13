# Paired annual claims — local candidate

Base `03cbf966c550537b67b32ebc9aa052dea193674f`. Reproduce retained ASML two-claim answer through production normalization, isolated SQLite persistence, actual fact tools and streamed final resolution before implementation. Only the model transport is replaced offline. No source tags are invented; net-income accounting-basis provenance remains incomplete.

One new invariant: both operands must independently certify the shared annual scope before either marker is registered. Preserve the existing single-claim behavior. No shared extraction, tools, locked tests, historical backfill, network, spend or publication changes. Root owns full PostgreSQL 15 gate and serial release.

## Implemented and focused verification

The exact finite shape is an annual revenue/net-sales clause followed by `, and net income was <currency><amount><scale>.` Each operand passes the existing identity, signed-value, currency and annual-duration certifier; actual starts/ends, units and accession must agree. Both registrations occur only after every check passes. Separate adjacent markers preserve all other answer bytes. Unsupported prose and already-cited answers remain outside the paired path. Existing single-claim behavior is unchanged.

Code contradicted the old `_fact_certifies_claim` explanation: duration writers now retain starts, although fallback selection can still retain a quarterly point. Corrected that docstring in this change; it does not change certification behavior. Historical NULL starts still abstain. The retained net-income raw_tag stays NULL; this slice makes no US-GAAP accounting-basis claim and does not repair existing text-table overclaims.

Committed reproduction `42088287cab05a2a8241f125f22b56199f36badd` failed through actual normalization/persistence/tools/stream resolution: grounded 0 instead of 2, two uncited figures.

```text
1 failed, 2 warnings in 4.93s
```

Feature `f30d20b7c6cf01abe267a6efd3b53fbecff92a0a` passed Ruff for both changed Python files and the new paired plus existing single-claim suite:

```text
All checks passed!
77 passed, 2 warnings in 4.83s
```

Exactly one committed mutation for the new all-operands-first invariant, `c96869d077c31b5bc724cb3a5c9d298d9aafdd2d`, registers each fact before the next operand certifies. The real resolver boundary exposes premature registration in the missing-duration, quarterly-duration, mismatched-start/end, wrong-unit/value/sign/accession/concept/fiscal-period controls:

```text
11 failed, 66 passed, 2 warnings in 5.26s
```

Restore `d328c0ed973b68db2aba749f14de222ac6a246d2` has exactly the feature tree `b849f05486504e780f8eb7dc284a0b79f079a6cf`. Restored focused run:

```text
77 passed, 2 warnings in 4.87s
```

All tests used fresh external bytecode/application SQLite paths and per-test fact databases; no live database. Dependency interpreter was the existing read-only `work/minor-sdk-venv`; creating a separate dependency environment stalled during local venv setup, so no dependency files were changed. Root must run the full committed PostgreSQL 15 gate before publication. No full-gate, assessment or deployment pass is claimed here.

Read-only self-review found no surviving blocker. Refuted cross-period attribution by the individual annual certifiers plus actual start/end equality; refuted one-chip-for-two-claims by exact distinct rendered citation assertions and separate insertion offsets. The signed/unit/accession controls traverse production persistence and run_tool rather than fabricated successful lookup dictionaries. The only code diff is Copilot service; all eleven locked anchors and shared extraction/tools are untouched. Independent three-lens release review remains root-owned.
