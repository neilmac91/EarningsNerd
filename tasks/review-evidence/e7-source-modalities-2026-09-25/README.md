# Source modality inventory, 25 September 2026

This slice adds `backend/evals/acceptance_source_modalities.py`, the third offline-custody piece of the [hierarchy plan](../../readiness-2026-09-21/acceptance/source-review-hierarchy-implementation-plan.md). For one HTML source packet, every table, inline-XBRL fact (hidden facts included) and image reference gets exactly one disposition: assigned to review units whose byte coverage contains it, or unresolved, which holds completion. The [interface doc](../../readiness-2026-09-21/acceptance/source-review-modalities.md) defines the format and its limits. The module is non-admitting, with no readiness, protocol, executor, output or decision call site.

Branch `claude/dreamy-meitner-jywnhd` from main `0dfc291`: implementation `336269f`, then the review fixes in `b806e35`.

## Independent review

An adversarial review of `336269f` ran executed bypass scripts. It found no way to make the validator accept an omitted, extra, reordered, relabelled or forged item, a hidden fact recorded as visible, partial or cross-packet coverage, or a wrong accession, manifest or contract binding. It also compared the coverage walk against a brute-force byte check over 200,000 random span sets, with no mismatch. It confirmed seven findings, all addressed in `b806e35`:

| Finding | Resolution |
| --- | --- |
| Inline-XBRL under a prefix other than `ix:` was dropped silently | Any other prefix on `nonFraction`, `nonNumeric`, `fraction`, `hidden` or `header` now fails closed |
| A UTF-8 non-HTML packet (plain text, XML) inventoried as empty | A packet must contain an `html` or `body` element |
| The builder coerced tuples and `str` subclasses through JSON, and one input raised `TypeError` | Dispositions pass to the strict validator unchanged |
| The `start`, `end`, `sha256` and `item_id` tamper checks and `ix:fraction` were untested | Tests added; `ix:fraction` is in the fixture |
| The doc did not specify the `hidden_reasons` order | Specified as outermost first, and pinned with a fixture whose order is not alphabetical |
| One fail-closed guard is unreachable | Kept as defence in depth and documented as such |
| `<image>`, `<svg>`, `<object>` and similar left scope quietly | Rejected as unsupported image-bearing markup |

## Verification

[Full gate](full-gate.log) on committed `b806e35`: ruff and bandit pass, and pytest reports 3699 passed, 2 deselected (the performance marker), with zero failures, errors or skips. That is main's 3697 plus the two new gates. The four PostgreSQL lanes ran against a scratch local `postgres:15`, never production. An earlier attempt errored in those lanes because the local Docker daemon had stopped; it is superseded and not counted. The new tests pass under three hash seeds.

## Mutation proofs

One per new gate, both on committed `b806e35` ([receipt](mutation-proof.json), [runner](mutation-proof-runner.py.txt)), each with a fresh bytecode-cache prefix and a byte-identical restore on a clean tree:

| Gate | Mutation | Mutated | Restored |
| --- | --- | --- | --- |
| `test_every_table_fact_and_image_is_enumerated_and_dispositioned_once` | drop the recorded-item count check | 1 failed | 1 passed |
| `test_assigned_items_must_lie_inside_the_named_review_units` | disable the uncovered-bytes check | 1 failed | 1 passed |

## Boundaries

Only synthetic fixtures were used. No H01, H02 or H25 raw bytes are present, and nothing was fetched from SEC. No E7 generation, Fable or judge call, spend, flag or migration occurred. The two previously denied E7 guard proofs were not touched.
