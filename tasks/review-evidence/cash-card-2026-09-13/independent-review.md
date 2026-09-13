# Cash-card applicability independent review — 2026-09-13

Reviewed committed c0928f721930c883ca19f815d57532deb4a80d90 against de74f94e0422e72ceff0b20a943ae5ef59069749 in work/cash-card-applicability. No surviving blocker was found across correctness, rules and tests lenses. Root's content stamp/RUNBOOK changes, full committed PostgreSQL 15 gate and actual assessment remain separate prerequisites; this report does not claim them complete.

## Correctness and scope

cash_claims.py:106 introduces conventional_cash_applicable: classification is explicitly False and bank components are absent. Both lead qualification and markdown_render.py:463's old derived card use this helper. The model card is removed before the guard; there is no model-written fallback. Classification True, absent/unknown or contradictory bank components therefore abstain. Existing ordinary bank-revenue predicate semantics, ratio math/bands, selected values, source acquisition and prompts are unchanged.

The financial-exposure candidate was refuted twice against the correction: the shared helper consults the actual propagated classification rather than missing bank rows; the committed mutation removes only affirmative classification and re-exposes COIN and unknown cases through the real final/preview/export controls. The controlled false classification does not reopen a bank-component case. The unknown-coverage loss is intentional and documented for future generation; no stored summary is rewritten or replayed.

The source/prompt-change candidate was refuted twice: the runtime diff touches only the two cash owners, with no extraction/classifier/transport/facts/cache/provider changes; the existing integrated source tests still compare full generator/recovery request sequences plus eval/Copilot projections with/without metadata. The helper performs no lazy SDK or network operation.

## Tests and preservation evidence

Independently compared RETAINED_FINANCIAL's selected current rows and classification to actual PR842 JPM/COIN artifacts: all included source values/metadata are exact. The control labels its nonfinancial/unknown/bank-veto variants as controlled changes, rather than relabelling actual COIN. It uses summarize_filing with a mocked provider response, then final raw sections, partial preview, common web sections, Markdown, PDF HTML and CSV. It verifies the stray model card never survives, basic signed operating/investing/financing values remain, and an unrelated qualitative disclosure remains. The nonfinancial variant retains the old positive-OCF/despite-loss card; JPM, COIN, unknown and bank-veto variants suppress it.

Existing arithmetic/currency/boundary tests retain their assertions and add the explicit nonfinancial premise. The earlier ordinary preview fixture needed the same premise; its failure and correction are documented rather than waived. Changes to the previous PR's old-card-parity assertions are explicit scope corrections, not weakening locked contracts.

The five new surface cases do not carry the complete financing_comparison_source or complete statement-context sidecars. They prove preservation of basic cash-flow facts and unrelated prose, not by themselves preservation of every rich financing/statement paragraph. No changed runtime line edits those owners; the full gate and actual assessment should nevertheless check those established cohort fields. Native PDF layout is not exercised by the PDF HTML control.

## Committed gate and one mutation proof

Read actual outputs/cash-card-final-focused.log:

```text
194 passed, 2 warnings in 4.12s
```

Feature 99b07ccfeaa921fff528035328995146dc188110. The focused set covers cash applicability/claims, structured Markdown, figure trace, section reveal, summary schema and quality assessment. The lane also records Ruff All checks passed; full backend gate is root-owned.

Mutation 8fcc442d482a784f8429a08b3fba4e39d8f1ae40 changes only the helper to retain bank veto while omitting affirmative classification. Actual final mutation log:

```text
10 failed, 21 passed, 2 warnings in 3.57s
```

Restore 7b1e7143375eea02e1e4fa8265612f200449c458:

```text
31 passed, 2 warnings in 5.82s
```

Independently resolved feature/restore whole trees to identical 92960e5009b657c34750798354773e94dc8812ce. Reviewed head c0928f72 differs from restored state only by the 36-line task note. Independently compared all eleven locked anchors by Git blob bytes against the base: all identical, including actual T4 and the existing approved T9 state. The three changed test files are ordinary unlocked files.

## Remaining limits

Nonfinancial remains an applicability screen, not certification of economic usefulness. MELI's customer-fund/issuer-adjusted-FCF issue and the old card's less stringent date/currency relationship checks are explicitly separate work; this change must not be reported as resolving them. The old comment near markdown_render.py:448 still describes model ownership of operating_vs_one_time, which is conditional since PR842; the actual source-owned path is unaffected. No new source acquisition, historical mutation, spend or founder boundary is introduced by this local candidate.

No test was executed and no repository file was edited during this review. Publication and production acceptance remain with root.


## Final root-delta review — 2026-09-13

Read c0928f72..0be52d4f9332043bafbeae947dc05bcae19e621f. Changes are the content stamp summary-2026-09-l→summary-2026-09-m (schema remains2), its explanatory comment, the appended RUNBOOK record, and the stale operating_vs_one_time comment correction. No new runtime cash predicate/arithmetic or source/extraction/prompt code changed. The comment now correctly distinguishes model-owned unsupported disclosures from supported statement ownership. RUNBOOK preserves unknown/cache/no-replay and MELI economic-basis limitations, and explicitly requires actual COIN removal/JPM suppression plus cohort preservation. No finding survives this delta. Full committed gate was still root-running at review time.


## Full-gate fixture correction reviewed — 2026-09-13

Read final delta 0be52d4f..9c74719d5471473c7a75a1a34b62a89d7e9617bf. One ordinary synthetic CNY selected-capex surface fixture gains financial_classification.is_financial=False; every prior assertion remains unchanged. This makes its nonfinancial applicability premise explicit rather than weakening the selected-basis, currency or immutability contract. Its source metrics are controlled fixtures, not relabelled actual issuer observations. Only that test and an appended dated task correction change; backend/app has no delta. Independently re-compared all eleven locked anchors by Git blob bytes to de74f94e: identical. No surviving finding; complete gate rerun remains required. The prior eight failures are explicitly retained, not counted as a pass. No tests run by this reviewer.
