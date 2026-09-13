# Derived cash-card applicability — September 13, 2026

Both conventional cash presentation owners now require affirmative nonfinancial classification and retain the existing bank-components veto. Model-authored cash_conversion is removed before eligibility on every path. Unknown classification abstains for new generation; no old stored summary, extraction, cache, prompt, provider call or historical replay is changed.

Actual retained PR842 COIN current rows/classification now suppress its cash-versus-loss card. JPM remains suppressed. Integrated controls preserve all three basic reported cash-flow amounts and a qualitative disclosure through final generation, partial preview, web sections, Markdown, PDF HTML and CSV. A controlled nonfinancial variant retains the old calculation; controlled unknown and contradictory bank-component variants abstain. Source-classification tests retain the insurer/BDC/SIC cases and source/prompt parity assertions. Ordinary calculation and preview fixtures explicitly declare their nonfinancial premise; all previous arithmetic assertions remain.

This is applicability, not economic certification. The retained MELI classification remains nonfinancial and its cash-conversion ratio remains eligible. Customer balances, issuer-adjusted FCF and economic meaning of that ratio remain unresolved separate work. No arithmetic or ratio band changed.

## Committed verification

Feature 99b07ccfeaa921fff528035328995146dc188110:

```text
194 passed, 2 warnings in 4.12s
All checks passed!
```

The focused set covers cash applicability/claims, structured Markdown, figure trace, partial section reveal, summary schema and quality assessment. Full PostgreSQL 15/performance gate and actual paid assessment remain root-owned prerequisites, not claimed complete here.

One new invariant, one mutation: remove affirmative classification from the shared predicate while retaining the bank veto. Final mutation 8fcc442d482a784f8429a08b3fba4e39d8f1ae40:

```text
10 failed, 21 passed, 2 warnings in 3.57s
```

This includes the actual COIN and unknown integrated controls. Restoration 7b1e7143375eea02e1e4fa8265612f200449c458:

```text
31 passed, 2 warnings in 5.82s
```

Feature and restored entire trees are identical: 92960e5009b657c34750798354773e94dc8812ce. All eleven locked anchors remain byte-identical against base de74f94e0422e72ceff0b20a943ae5ef59069749. The three changed test files are ordinary, not anchors.

## Dated verification corrections

Initial committed controls omitted the cash-flow section from their offered preview payload; preview intentionally does not introduce an unreceived section. Five assertions failed, 116 passed. Adding that section to the fixture yielded 121 passed. Expanding affected-reader coverage then exposed an ordinary preview fixture lacking affirmative classification (1 failed, 193 passed). Its eligibility premise was added, preserving every assertion, producing the final 194-pass run. The same applicability mutation was re-established after these fixture corrections; earlier proof logs are retained in outputs and are superseded by the final tails above. No failed partial run is a passing gate.


September 13 root full-gate correction: committed 0be52d4f9332043bafbeae947dc05bcae19e621f failed eight parametrized ordinary selected-capex-basis surface checks, with 3253 passed in116.93s. Their synthetic nonfinancial CNY metrics omitted the new eligibility premise, so the expected derived card correctly abstained. The fixture now explicitly declares nonfinancial classification; all prior basis/currency/immutability assertions remain. No production-code change or locked-test edit was required. The complete gate will be rerun; the failed run remains work/cash-card-publication-gate.log.
