# Source-unit quote context local verification

Clean gated head: `e119e4c1fefc3154bff96968af2d35f2d13f9684`, branch `codex/wave3-source-unit-quote-context`, based on verified `f0a81fff216c318a40979b7dfcd55500c8b43a03`. Local implementation only; no remote publication, model call or paid assessment. Scope remains source-owned context beside qualifying unchanged primary quotes, not correction of authored guidance. Root/independent source review is retained separately.

Full committed backend gate completed with **exit 0**. Ruff passed; Bandit returned success at the required `-ll` threshold. PostgreSQL 15.15 on localhost port 55433 used its own `earningsnerd_source_unit_quote_context` database, with all four exact CI lane variables configured. `pytest -m ""` includes performance. No parallel test or edit occurred in this worktree.

```text
All checks passed!
================ 2888 passed, 29 warnings in 102.73s (0:01:42) =================
```

Full log: `work/source-unit-full-gate.log`; script: `work/run-source-unit-gate.sh`. After the successful pytest summary, the existing Yahoo-client shutdown callback logged `ValueError: I/O operation on closed file` while asyncio logged its selector. The process still exited 0. The same shutdown diagnostic occurs in earlier unrelated full-gate logs (including `work/derived-basis-full-gate.log` and `work/chat-cleanup-full-gate.log`); no silent retry or extra test run was used to conceal it.

Exactly one mutation proof was run, on committed state. At `39a5389c`, only the v2 consumer's source-unit declaration delivery was removed. The source annotation still existed internally; the actual visible-consumer assertion failed, demonstrating that a metadata-only implementation would not pass.

```text
FAILED tests/unit/test_source_unit_quote_context.py::test_source_units_belong_to_entire_quote_in_actual_consumer[primary]
1 failed, 9 passed, 2 warnings in 2.12s
```

Restored commit `bd8a35f6` restored the declaration and the same control gate passed:

```text
10 passed, 2 warnings in 1.87s
```

Logs: `work/source-unit-mutation-red.log`, `work/source-unit-mutation-green.log`. Before the proof, two focused fixture runs failed because the test directly rendered the service's intentionally unstamped outer raw payload; the real pipeline stamps that at `summary_pipeline.py:875`. The corrected fixture renders the actual service-stamped nested structured summary through the common v2 projection and compares it to actual returned markdown. It does not alter production stamping. Corrected focused run at `f795474f`: 10 passed, 2 warnings in 1.80s. Earlier logs are retained (`source-unit-focused.log`, `source-unit-focused-corrected.log`, `source-unit-focused-final.log`). These were fixture preparation, not additional mutation proofs.

All existing test files, including locked anchors, are byte-identical to base: the entire tests diff contains only addition of `backend/tests/unit/test_source_unit_quote_context.py`. Historical todo bytes are retained with appended plan/proof records. `git status --short` is empty after the gate.

Retained-data application separately examined 56 attempts/90 quotes and annotated four COST capital-plan quotes without changing their bytes; no other issuer received context. Recovered forward sections, previews, absent supplied excerpts, duplicates, conflicting units and unrecognized boundaries abstain. No live browser/PDF layout, database reload, fresh model selection behavior or universal false-positive claim was verified. Universe-wide pregeneration remains held.

## Historical trust correction — superseding publication head

The additional read-time trust review found that historical unknown quote keys could persist without Pydantic filtering. The local code now gates the shared quote projection on a code-created **outer** envelope marker, assigned only after new final association; model/nested markers cannot grant it. The unused Pydantic annotation field was removed. This corrects the earlier publication limitation without changing rollout stamps or replaying old summaries.

Final clean gated head: `aff17c2d5ae810382855351e9408c33695f87c66`. Full corrected gate `work/source-unit-trust-full-gate.log` completed exit 0, Ruff/Bandit successful, own PostgreSQL database with all four lanes and performance:

```text
================= 2892 passed, 29 warnings in 98.03s (0:01:38) =================
```

A **distinct persisted-trust invariant** received exactly one new committed proof, preserving the original association/delivery proof. Mutation `3023c479` bypassed only the envelope eligibility condition; forged historical quote/nested/boolean controls failed:

```text
3 failed, 1 passed, 10 deselected, 2 warnings in 2.63s
```

Restoration `690de5c7`:

```text
4 passed, 10 deselected, 2 warnings in 1.98s
```

Logs: `work/source-unit-trust-red.log`, `work/source-unit-trust-green.log`. Pre-proof focused suite: 14 passed, 2 warnings in 3.01s. New controls use actual final generation and shared web enrichment/PDF/CSV/Markdown consumers; they do not rely on a model-provided eligibility value. No old locked test was changed. Final git status is empty. No network/model/remote action, content-stamp change or live browser assertion is included in this verification.
