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

Environment follow-up: local venv setup without pip completed successfully at `work/copilot-paired-venv`, with read-only dependency imports from the existing SDK environment. On committed `310a07ea5ea619ff9fe9148dde9c53b243be2b1d`, a final focused run in that isolated interpreter and fresh writable paths passed **77 passed, 2 warnings in 4.54s**. This repeat resolves the earlier environment-isolation limitation; no packages were installed or fetched. Independently compared every one of the eleven locked files' committed bytes against the base: all identical.


## Root integration review

Candidate `1a7bbc90820238408135561ba3c78fb70faa9b97` passed the root full PostgreSQL 15 gate with four isolated lanes and performance: **3,116 passed, 29 warnings in 97.78s**, exit 0, Ruff clean and Bandit zero medium/high findings. Independent correctness and tests/rules lenses found no blocker; all eleven locks are byte-identical. A stale single-claim wrapper/call-site comment is corrected in the final integration, along with the already noted duration-writer explanation.

Mutation evidence was retained in agent tool output, not filesystem logs: reproduction session98949/chunk73ee6c; mutation session15295/chunk211e96; restoration session95568/chunkb8c75f; final isolated focused session87442/chunk75d2de. The committed ledger contains their exact tails. Root independently verified feature/restoration tree equality and ran the full gate. No additional mutation was introduced.

Integrated Outlook main `d91dbdde45014021940162ae46c9fda26e071e0b` without conflicts. Its production verification remains pending; this citation branch stays unpublished. Combined final committed gate and actual assessment remain required.

### September 13 — final-visible citation eligibility correction

Actual PR #837 assessment retained three bare ASML paired answers with no chips. Workflow source identity was verified by root. Replaying the exact final answer through its real downloaded SQLite Filing snapshot, production tools and complete response boundary succeeds; the snapshot/data path is not the explanation. Raw model streams were not retained. An independently reproduced scenario yields precisely the observed final answer and zero misplaced-marker count: the model supplies unresolved F-markers, the initial repair correctly abstains, and the existing resolver strips those invented references without counting them as misplaced real facts. This is an observed-equivalent failure path, not proof of what those three model streams contained.

The correction keeps the existing first repair and resolver unchanged. Only when resolution changes the visible answer and leaves no surviving citation does certification inspect that final visible prose; it re-resolves only if certified markers were added. Rejected model references never become evidence. Both operands still certify before registration, valid surviving fact/text citations are preserved, and original misplacement telemetry is added to any later resolver telemetry. Already-bare failed claims incur no duplicate lookup.

The reproduction now traverses production `snapshot_filing` as well as normalization, isolated persisted fact rows, actual tools and streamed final resolution. Additional controls preserve valid text citations, valid fact citations and the original misplaced counter; a missing second duration still abstains atomically. No locked anchor, shared tool/extraction file or production flag changed.

Committed reproduction `77bea7c65bbb860cc1d6c901b09c154135882518`:

```text
1 failed, 19 passed, 2 warnings in 4.72s
```

Committed feature `417a3ac19a2a9c762180333ad2993348351cebc6`:

```text
82 passed, 2 warnings in 4.75s
```

Exactly one additional mutation proves the new final-visible-prose eligibility invariant. Mutation `f7b3bbf054b48e83fcc13a3e7cbb5fe3df1493b5` disables only the post-resolution certification:

```text
2 failed, 80 passed, 2 warnings in 4.63s
```

Restore `99346d726ebd17e97dd9cbbb0f205be412d62086` is backend-byte-identical to `417a3ac19a2a9c762180333ad2993348351cebc6`:

```text
82 passed, 2 warnings in 4.53s
```

Ruff passes on both changed Python files. Logs are retained outside the repository in `outputs/paired-final-{repro,green2,mutation,restored}.log`. Existing paired-atomicity mutation proof remains unchanged. These are focused committed-state results, not a full PostgreSQL gate or new paid assessment. Root retains publication, full gates and serial deployment ownership. No source fetch, model call, push or live database write was performed.
