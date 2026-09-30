# Source review graph custody, 26 September 2026

This slice adds `backend/evals/acceptance_source_review_graph.py`, the fourth offline-custody piece of the [hierarchy plan](../../readiness-2026-09-21/acceptance/source-review-hierarchy-implementation-plan.md). For one role it validates the context and receipt custody of the multi-context review graph:

- every unit of a validated unit manifest bound to exactly one leaf;
- a hash-linked, acyclic, single-rooted tree of leaves, reducers and one role synthesis;
- every node run in its own registered context, which must be eligible and its latest attempt, with no reuse or cross-role overlap;
- receipts matched to a frozen role contract and to the exact supplied template, prompt and artifact bytes.

The [interface doc](../../readiness-2026-09-21/acceptance/source-review-graph.md) defines the format and its limits. The module is non-admitting, with no readiness, protocol, executor, output or decision call site. Issue propagation and reconciliation are the next stage.

Branch `claude/dreamy-meitner-jywnhd` from main `16cdc1a`: implementation `301cbd1`, then the review fixes in `fe03cd0`.

## Independent review

An adversarial review of `301cbd1` ran executed bypass scripts and 34 runtime mutations. It found no way to make the validator accept any of these:

- an ineligible, non-latest, reused or cross-role context;
- a registry trick;
- a missing or duplicate leaf, a cycle, a mismatched child, two roots or an orphan;
- a receipt that disagrees with the contract;
- a type-confused value;
- an artifact trick.

No non-`ValueError` exception escaped. Its confirmed findings are all addressed in `fe03cd0`:

| Finding | Resolution |
| --- | --- |
| A leaf receipt bound only the unit's content hash, so units with identical bytes were interchangeable | A leaf's `input_sha256` is now the unit's `unit_id`, which also binds packet, spans, context and labels |
| The kind-not-allowed test was shadowed by an earlier contract-hash rejection | The test now builds the graph under the restricted contract and matches the specific message |
| 26 enforced rules were not pinned by any test | Added: full summary equality, an independent `children_sha256` reimplementation, node-shape and loader cases, and an 11-case malformed-contract table |
| A node artifact could alias another node's artifact, a template or a prompt | Rejected |
| The context-reuse check is unreachable | Kept as defence in depth and commented |

## Verification

[Full gate](full-gate.log) on committed `fe03cd0`: ruff and bandit pass, and pytest reports 3714 passed, 2 deselected (the performance marker), with zero failures, errors or skips. Main at `16cdc1a` collects 3701 default-lane tests, 2 more than the previous slice's 3699 because neilmac91/EarningsNerd#958 merged in between. This slice adds 13 cases. The four PostgreSQL lanes ran against a scratch local `postgres:15`, never production. The new tests pass under three hash seeds.

## Mutation proofs

One per new gate, all on committed `fe03cd0` ([receipt](mutation-proof.json), [runner](mutation-proof-runner.py.txt)), each with a fresh bytecode-cache prefix and a byte-identical restore on a clean tree:

| Gate | Mutation | Mutated | Restored |
| --- | --- | --- | --- |
| `test_every_node_runs_in_its_own_latest_eligible_context` | disable the eligible-status check | 1 failed | 1 passed |
| `test_graph_structure_and_receipts_are_bound_to_frozen_bytes` | disable the child artifact-hash check | 1 failed | 1 passed |
| `test_malformed_role_contracts_are_rejected` | disable the required leaf/synthesis kinds check | 2 failed, 9 passed | 11 passed |

## Boundaries

Only synthetic fixtures were used. No provider, model, Fable or judge call occurred, and no E7 generation, spend, flag or migration. The two previously denied E7 guard proofs were not touched.
