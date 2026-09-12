# Cash-basis assessment archive — September 12, 2026

This archive preserves the first #821 assessment and the second Copilot assessment, and corrected second-summary source/mechanical acceptance. **The bounded assessment is accepted and #821 is merged and production-verified.** The first summary identified missing selected-capex concept provenance and triggered a confirmed-finding correction; its findings must not be presented as acceptance of the corrected candidate. The second Copilot result evaluates that corrected candidate within its existing six-question gate.

## Retained evidence

| Assessment | Report | Supporting evidence | Bounded result |
|---|---|---|---|
| First summary | [Cash and preview review](pr821-first-summary-cash-review.md) | [Cash review evidence](pr821-first-summary-cash-review-evidence.json), [source and projection integrity](pr821-first-summary-integrity.json) | 52 outcomes; targeted cash review of final output and 509 retained preview frames. Missing capex provenance required correction; material narrative findings remain open. |
| First Copilot | [Acceptance](pr821-first-copilot-acceptance.md) | [Integrity](pr821-first-copilot-integrity.json) | Run 34693652630: 18/18 under the existing gate, with retained citation-scope and redundancy advisories. |
| Second Copilot | [Acceptance](pr821-second-copilot-acceptance.md) | [Integrity](pr821-second-copilot-integrity.json) | Run 34698883776, job 103567021024: 18/18, after the confirmed capex correction; inherited advisories remain. |
| Second summary | [Source/mechanical acceptance](pr821-second-summary-acceptance.md) | [Integrity](pr821-second-summary-integrity.json), [usage conservation](pr821-second-summary-usage.json) | CI 34698866950, eval job 103566979337: 52 outcomes, zero comparison issues, 38 intended capex concept additions and 523 retained preview frames. [Independent cash-prose review](pr821-second-summary-cash-review.md) and [its evidence](pr821-second-summary-cash-review-evidence.json) accept the bounded scope while retaining broader findings. |

The first assessment executed synthetic commit `f2200353f590f2d7a75e96bb188966077b0777de`, with the same complete tree `2066c3b1ff910f4ff7ba3c0ea6c8d51788a8a747` as candidate `d183241a2384348f19e8bfa01e346f0bb6501992`. The second Copilot executed `ac9a02c96b9e54351aa0ade75d57a1d9ea249691`; its complete tree `eef75a8a4eefb2ffd6d0e001b7f885b6e3ff0141` matches gated candidate `f989c657339449ece84f95a1143f6d2e187b4370`. These are execution identities, not merge or production revisions.

## Integrity and reproduction limits

The twelve reports and evidence files above are byte-identical copies of the original private review files. [Archive integrity](archive-integrity.json) records their SHA-256 hashes, sizes and original private paths. The original reports retain their original `work/` references rather than being rewritten. A `work/<report basename>` reference to one of these twelve files resolves to the same basename beside this README. References to provider artifacts, checkout logs and checker utilities denote private retained evidence, not additional files in this repository archive.

The underlying provider reports are deliberately not copied here. Their recorded SHA-256 values are:

| Artifact | SHA-256 |
|---|---|
| First summary `eval_20260912T123350Z.json` | `d92eb5508c80eca8074c7ce36b7b6a6b54020b299aad6005949f4b71bd8d5ab6` |
| First Copilot `copilot-eval.json` | `f7d2451eb83d18ca6bfc7a18c12b63ff62fd326a471bed8cac296011d7bc1290` |
| Corrected second summary `eval_20260912T142553Z.json` | `cd078f4371c17c8dfb342996364ef368e7065579411079cacbe29e54959a6a90` |
| Second Copilot `copilot-eval.json` | `20db9caffae449a85b19db6c6e16934f0d2a236e44f78b3c5dba5dbc8ca49d86` |

These checksums identify retained artifacts but do not make the archive independently reproducible without those artifacts and logs. No secrets or large provider/source payloads are included. The first summary contains one failed provider call without usage telemetry: its known token totals are incomplete billing evidence. Copilot cost amounts are logged estimates, not independently reconciled account debits.

The cash qualifier is not a general financial-quality certificate. Retained Ford/PDD arithmetic or comparison errors, WMT/ASML/MELI debt-scope findings, issuer-versus-derived cash-flow interpretation, COST authored-guidance units, and Copilot citation-scope advisories remain bounded findings in the linked reports. Neither this archive nor a passing deterministic gate authorizes universe-wide pregeneration, historical replay or a production flag change.

The balance records are distinct: the founder reported USD89.17; a live read returned USD88.49 at 14:13 UTC. Their difference is not attributed to this PR or any individual evaluation; it is not a reconciled bill. Hosted CI passed and automated review recorded +1 at 14:21:43 UTC, but neither substitutes for the independent semantic review or deployment verification.

## Release verification

- [x] Retain corrected second-summary source/concept, deterministic cash-field and usage-conservation acceptance.
- [x] Complete the separate second-summary cash-prose/preview review: bounded cash-basis and capex identity scope accepted; broader narrative findings remain open.
- [x] Record the actual merge, main CI, migration tail, serving revision at 100%, and CI plus independent detailed health.
- [x] Integrate the verified main release into this documentation branch, append dated ledger records and complete the documentation link/anchor check before publication.

[PR #821](https://github.com/neilmac91/EarningsNerd/pull/821) merged as `929995d4b9190785e732e4d889cd193e9ce271f7` at 2026-09-12T14:31:29Z. Main CI `34699536585` succeeded. Deploy job `103569199353` reported `apply_migrations: applied=0 skipped=39` at 2026-09-12T14:36:52.0425759Z. Revision `earningsnerd-backend-00332-p9k` serves 100% of traffic, explicitly confirmed at 14:37:34.8124744Z. CI detailed health was healthy at 14:38:13.2213219Z (database 7.24 ms). Independent detailed health was healthy (database 9.11 ms, server timestamp `1789223987.8105648`; Redis disabled and SEC circuit closed). Private evidence: `work/pr821-main-deploy.log` and `work/pr821-independent-health.json`. This branch has integrated that exact main commit while preserving the archive. Earlier ledger entries are unchanged.

The final semantic review retains newly sampled AAPL distributions-versus-OCF and MELI direction errors, repeated WMT/MELI debt scope, and expanded COST unit loss. These are open quality findings; unchanged financial operands and machine-owned strings do not establish that the capex correction caused them. Prior sampled failures remain open even where the second draws do not repeat them.

The separate source-unit quote-context PR #823 is now merged with bounded assessments accepted; its [production verification is complete](../source-unit-2026-09-12/README.md). The combined release record is committed and reviewable, with both verified main releases integrated, dated ledgers preserved and documentation checks complete.
