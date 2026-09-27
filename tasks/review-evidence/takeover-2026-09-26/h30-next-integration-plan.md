# H30 next integration plan — bounded cross-role history custody

## Purpose and current boundary

This handoff scopes the smallest remaining H30 engineering step under the founder’s existing implementation authority. It requires no new provider call, candidate/comparator evaluation or financial re-judgment. The implementation passed independent review, its actual-artifact smoke, one failing/restored fault proof and the full local gate (3,732 tests); hosted checks and release verification remain pending. This document retains its original bounded requirements; the [AI-assisted protocol guide](../../readiness-2026-09-21/acceptance/ai-assisted/README.md) and the final release receipt govern the implemented schema. This plan is not programme admission.

H30’s frozen current record is complete within its existing source-only scope:

- accession `0001104659-25-086034`;
- source A has 9 dispositions and source B has 10;
- the revised reconciliation has 10 material issues, all 19 current dispositions and 12 resolved current disagreements;
- the separate history ledger has 52 identities: 12 old-A, 11 old-B, 23 old-reconciliation and 6 same-context partial-A identities;
- 51 historical identities are source-supported;
- `old-reconciliation:disagreement:0` is an unresolved operator-runtime custody claim.

The current schema-2 reconciled reference can carry the 19 current dispositions and 12 current disagreements. It has no field for the separate 52-row cross-role history. H29’s retired-B-only adverse-evidence shape cannot represent old A, old B, old reconciliation and same-context partial-A origins together.

## Frozen inputs

Do not rewrite, normalize or regenerate any existing artifact. Bind them by reference and SHA-256:

- revised reconciliation: `8ce13076933ceb392f909d9661449e9374d8a2874a8318f24191550939ef7c70`;
- reconciliation context evidence: `96519bf96b9327edf24e6e98a3285ac2eb5f45892e508007d5a64291dc539d6d`;
- current A brief: `932deaca7cf64be22ca6ab463e05a48a817c1b9fce749358b9ab4108fc461240`;
- current B brief: `99fc6975901a3ab5919cea9fa45265e8afd1588a24365524da89e1ab34268c7f`;
- clarified 52-row history ledger: `80a1daee5ebfbd6119f4349ecd2b6d7d9cea556a2c696ac42686ac3977a09872`;
- external-history manifest: `63a03048de3269ca3bfc3c21b4489fe0ef03355432826e32cd6190a172c089e6`;
- clarified raw reconciliation draft: `c6433a134858fd3cc6f27d8f3e54f65fbb355c3d309e5d953a1e04d715f078ad`.

The current compact receipts are `tasks/review-evidence/takeover-2026-09-26/h30-freeze-receipt.json` and `h30-custody-audit.json`. The frozen workspace sources are under `outputs/takeover-2026-09-26/h30-source-bundle/`.

## Optional history boundary

Add one optional `reconciliation_history` entry per accession to the AI prerequisite wrapper. Keep the existing top-level schema-2 prerequisite, current A/B brief records and current reconciliation record unchanged. A no-history accession must produce the same inventory bytes it produces today.

The implemented wrapper additionally binds the raw reconciliation draft, a stable history prefix and actual byte-bound artifact for each origin, both technical attempt custody chains, declared runtime holds, and the complete source-context closure. Use the protocol guide for the exact field shape; the earlier abbreviated proposal is intentionally removed to prevent it being mistaken for an executable example.

`identity_set_sha256` hashes a canonical JSON array of the exact `history_id` values, sorted lexically using `ensure_ascii=True`, compact comma/colon separators and `allow_nan=False`. Completeness must also be derived from the bound origins’ actual issue IDs and disagreement indices, then paired with each row’s exact origin context/hash; a self-recomputed count and set hash are insufficient. Do not adopt an ad hoc newline hash. `source_context_closure_sha256` must cover the complete sorted exclusion set, including all old A/B/reconciliation contexts and `/root/h30_source_a_retry3`.

The four H30 origin context/artifact pairs already retained are:

| Context | Origin | Artifact SHA-256 |
| --- | --- | --- |
| `/root/e7_h30_source_a` | old A | `6e47757b5eef8edecc085ae4c621c068865e2b09ffdb66e176a31fd90d53a285` |
| `/root/e7_h30_source_b` | old B | `9af8e2dd4a826f10cbf03c3b91ecafbbf9cfe2d2afad8dfc5d3034b7352cc9d3` |
| `/root/e7_h30_reconciliation` | old reconciliation | `f3d0a75b17121120e705066b2a13c5140cf9bb002493e618a497e8ded99cff21` |
| `/root/h30_source_a_retry3` | same-context partial A | `9350718ae851132ce8e12a42f97d2c705eaf5f1a829c0ecc659a034949c578ed` |

## Complete known context closure

The exact eight excluded contexts are:

- `/root/e7_h30_reconciliation`
- `/root/e7_h30_source_a`
- `/root/e7_h30_source_b`
- `/root/h30_reconciliation_retry2`
- `/root/h30_source_a_retry2`
- `/root/h30_source_a_retry3`
- `/root/h30_source_b_retry2`
- `/root/h30_source_b_retry3`

Closure SHA-256: `4143e5140879fa5dfea41b517abe652f8ef05f2c9d983ba4b31b43236a2d9113`. Both issue-free technical attempts are required; issue absence is not evidence of no source exposure. Their retained custody chains are:

- `/root/h30_source_a_retry2`: reservation `9ad6d898c01cca180dfe3453a6ea80566ab9fcf24968646336ad117a872b503e`; dispatch `08b1f7261d13e25c633e1840e5ff8d02d71efb15dfea5eae872f9422f1630b3b`; settlement `13f11e5a0fb722077b3b234f1ac75af47e483d810fe844af3a9f0476f61a5d2c`.
- `/root/h30_source_b_retry2`: reservation `b33e22c1c5b176c18ab929bb5dea414e8e31e666c4901e0ee129fd141119b0c5`; dispatch `b5ec64d8b8b3f401395e88193dedc8a06ed7f6c4a09f4d3923f5d9079c6100d4`; settlement `1a76e2ffceadae1af68a2fb5030224daad0c7cebf7f31d06770bd586e5b58992`.

The settlement children must be resolved and hash-checked; declaring a manifest or settlement hash alone does not bind its child bytes.

## Row treatment

Keep the frozen 52-row ledger unchanged. Validate a typed projection beside it:

- Each of the 51 financial rows has `evidence_class: "filing_source"`, retains its exact history ID, origin context and original artifact hash, and requires the ledger’s valid source role, source hash, filing locator and current `reconciled_issue_id`. The target must exist in the unchanged current reconciliation.
- `old-reconciliation:disagreement:0` has `evidence_class: "operator_runtime"`, `status: "unresolved"`, `reconciled_issue_id: null` and `hold: "custodian_classification"`. It cannot satisfy a financial-source completeness check.
- The frozen runtime row currently carries explanatory text in its existing `source_locator` field: “No filing locator: historical execution claim retained for custodian classification.” Preserve that byte-for-byte. The typed projection should expose `filing_source_locator: null`; do not rewrite the frozen row merely to turn its legacy explanatory field into JSON null.
- The historical artifacts remain retired and ineligible. Their contexts enter the shared source-context exclusion closure and cannot be reused for blind quality or source-challenge review. The partial-A artifact shares `/root/h30_source_a_retry3` with the later current source-A brief; retiring that partial artifact does not retire the later current source-only reference. The two additional technical attempts A2/B2 must also enter the closure even though neither produced a financial issue, giving eight known excluded contexts for H30.

The implemented hold set is bound to the exact originally unresolved disagreement identities. Structural validation does not itself classify a dispute as financial or operational; H30’s runtime classification comes from its retained source reconciliation/custody audit. An unresolved financial dispute requires a separate supported reconciliation path.

Filing bytes can support the 51 financial dispositions. They cannot prove what an old runtime retained. The runtime row therefore remains a custody hold even though the surrounding historical financial rows are source-backed.

## Implemented surface

The bounded change uses `backend/evals/acceptance_ai_protocol.py`, its existing unit-test module, and the existing protocol guide. Shared inventory/context helpers already connect to readiness and blind-decision validation; those consumers need no parallel implementation. Existing no-history and retired-B-only adverse-evidence routes remain supported. Legacy source contexts are retained as historical evidence; no journal dispatch records are fabricated for them.

## Reused gates

Extend the existing protocol, readiness and decision tests. Required cases:

- no-history compatibility retains byte-identical current inventory behavior;
- H30 accepts exactly the bound 52 IDs with origin counts 12/11/23/6;
- omission, duplication, unknown identity, origin change, artifact/hash change and current-target change fail;
- a financial row without a valid filing locator or current target fails;
- the runtime row fails if marked source-supported, given a financial target, or allowed to clear the custody hold;
- any old or partial context reused as a blind quality or source-challenge context fails;
- changed current A/B/reconciliation bytes fail their existing bindings.

Reuse the existing one-accession actual-artifact smoke, deterministic protocol/readiness/decision tests, full backend gate and one focused failing/restored mutation proof for the new invariant. No dedicated source-review provider run, candidate/comparator generation, strong judge or new financial-source opinion is needed for this custody-only change. Repository-required ordinary hosted regression measurements remain separately metered.

## Exit condition

The step is complete only when the unchanged current H30 reconciliation is wrapped under the existing schema-2 boundary, the optional history record binds all 52 identities and all eight known source contexts (including the two issue-free technical attempts), the one runtime claim remains explicitly unresolved, and downstream review rejects every history context. Passing this step establishes bounded custody and exclusion only. It does not establish H30 semantic correctness beyond the frozen source dispositions, E7 admission, full-corpus readiness or candidate quality.
