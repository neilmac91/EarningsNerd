# Source review units: byte custody, 23 September 2026

This slice adds `backend/evals/acceptance_source_units.py`, a pure, non-admitting library that builds and independently validates a deterministic unit manifest over explicitly declared source packets. It establishes byte custody and declaration consistency only. It is not an E7 evidence schema, has no readiness/protocol/executor/decision call site, and cannot set `coverage_status: complete` or admit evidence. The [interface and limitations](../../readiness-2026-09-21/acceptance/source-review-units.md) define the format, canonical encoding, golden vectors and explicit non-claims.

Implementation branch `codex/wave3-source-custody-units`, stacked on #951 at `523b26fe6a86e2c0f92f98e2f27bfde0f51a160d`. Measured implementation: `f6a0fb981469b8ed06e34d8a51a5e6da193e64b2` (initial implementation `6a96a1c`, then the independent-review fixes). Evidence-only commits after it change no backend byte.

## What it proves and does not prove

A manifest that validates proves exact length/SHA-256 custody of each declared packet, declared-accession and role binding into every packet/unit identity, exact disjoint coverage of `[0, byte_length)` for each declared packet (the union is walked; equal totals are insufficient), separately hashed repeated context that never counts as coverage, length-framed unit payload hashes and recomputable unit IDs. The validator recomputes everything from the caller's expected accession and bytes and never repairs, coerces or reorders input.

It does not prove that the declared accession, roles or labels are true, that the declared packets are the whole filing, that any byte split is semantically safe, or that tables, hidden inline-XBRL facts, images, encoded archives or decoded members were accounted for. Every attestation flag is `false`, and five fixed limitation strings travel with the manifest and summary.

## Synthetic example

[`synthetic-example-manifest.json`](synthetic-example-manifest.json) is the documented six-byte example stored in its required canonical form (no indentation, no trailing newline). Its file SHA-256 equals the validator's `manifest_sha256`, `ea73eff3b57db48cd9f3c127e719ca389d60d5afd93f4861ea496464fc521e7b`. [`synthetic-example-summary.json`](synthetic-example-summary.json) is the validation summary for it.

## Verification

The repository-standard gate ran from `backend/` on committed `f6a0fb98` under Python 3.11.15, with pinned ruff 0.16.8 and bandit 1.9.4. The [gate receipt](full-gate-receipt.json) and [log](full-gate.log) record the result:

- `ruff check .` passed, and `bandit -r app -ll` passed.
- `python -m pytest`: **3694 passed, 2 deselected, 40 warnings in 222.50s**, with zero failures, errors or skips.
- The four PostgreSQL concurrency lanes ran against a scratch local `postgres:15` container (PostgreSQL 15.19), never production: 24, 29, 6 and 5 cases.
- The 2 deselected cases are the performance marker in `pytest.ini`. No repository rule or dependency change selects that lane for this pure offline module, so it was not run locally; hosted CI runs it separately.
- The totals reconcile with the base: `523b26fe` collects 3656 tests, 3654 in the default lane plus 2 performance cases. The new default lane is 3654 + 40 regression cases.
- An earlier pre-run on `6a96a1c`, before the scratch database existed, reported 39 environment skips in those lanes. It is superseded by this run and is not claimed as a pass.

The regression home, `backend/tests/unit/test_acceptance_source_units.py`, holds one central invariant gate, one encoding and golden-vector test, and one table of malformed declarations: 40 cases in total. Every identity is compared with an independent reimplementation of the documented encoding. The whole-manifest vector freezes the limitation text, flags, key sets and encoding. The documented API example runs verbatim and reproduces it.

## Single mutation proof

Exactly one proof was run on committed `f6a0fb98` ([receipt](mutation-proof.json), [executed runner](mutation-proof-runner.py.txt), [failed log](mutation-failed.log), [restored log](mutation-restored.log)). It replaced only the exact-union walk in `_require_exact_partition` with a total-length comparison, which is the bug class the requirement names:

- mutated `1a9edfe6…`: `1 failed, 2 warnings in 1.78s`. The equal-length shift case, whose byte total is unchanged but which has an overlap and a gap, failed with `DID NOT RAISE ValueError`.
- restored `b85c2a88…`: byte-identical to the committed source, clean tree, `1 passed, 2 warnings in 1.28s`.

Each run used a fresh bytecode-cache prefix. No other mutation experiment was run. No E7 spend or required-source-brief guard was touched.

## Design and review record

The [review record](review-record.md) covers two independent multi-agent reviews:

- A pre-implementation design critique in three lenses.
- An adversarial review of committed `6a96a1c` in four lenses, with two refutation attempts for each blocker or should-fix finding.

Three findings survived refutation and are fixed in `f6a0fb98`:

- `str`-subclass dict keys could pass the exact key-set check;
- partition edges were not exercised;
- a reordered `declared_packets` manifest was not tested at the validator.

Two lenses independently recomputed the golden vectors from the specification alone. These reviews are not Agent B's independent verification.

The provider-balance read for paid PR CI was **denied** (`403 Resource not accessible by integration`) and was not retried by another route; see [provider-balance.json](provider-balance.json). The latest existing reading is run 35839909018 from 08:55 UTC, which is not current.

## Real-source availability

No raw H29, H01, H02 or H25 source bytes are present in this environment or tracked in Git, and nothing was refetched from SEC. Real-source custody validation was **not performed**. The repository-visible H29 declarations (accession `0001193125-25-183155`; roles `complete_submission`, `earnings_exhibit`, `index`, `primary`; positive integer byte counts and lowercase SHA-256 values) satisfy the format's declaration grammar. That is a format-compatibility observation only; the revised source snapshot is held outside Git.

## Boundaries preserved

All existing files are byte-identical to the base, including the protocol, readiness, executor, output and decision modules and every locked test. No schema number or validator changed. No provider, model, Fable or judge call, E7 generation, spend, flag, migration, deployment or merge occurred. The two previously denied E7 admission and required-source-brief guard proofs were not touched, retried or routed around; their holds remain.
