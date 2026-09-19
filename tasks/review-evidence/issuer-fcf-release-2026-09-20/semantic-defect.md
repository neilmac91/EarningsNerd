# AMZN retained semantic defect — corrected PR #927

**Observed defect, not a code-owned reconciliation failure:** AMZN 10-K draw 0 describes $128.3B as exceeding $139.5B. The source-owned issuer table is arithmetically correct and separate from conventional FCF. This note preserves the limitation for scoped release assessment; it does not claim broad semantic acceptance or attribute the model error causally to this change.

## Evidence

- Exact candidate head: `9ebce0b6261a9d92639559d1cccc38a2cdda248b`.
- CI run: 35471622833; report: `baseline/eval_20260919T220102Z.json`.
- Identity: `(baseline, AMZN, 10-K, 0)`; field: `raw_sections.earnings_quality.red_flags[1]`.
- Filing: accession `0001018724-26-000004`, year ended December 31, 2025; retained source URL: https://www.sec.gov/Archives/edgar/data/1018724/000101872426000004/amzn-20251231.htm .
- The exact output is visible in both final `executive_summary` and compatibility `management_discussion`:

> Purchases of property and equipment, net of proceeds from sales and incentives, rose to $128.3B in 2025 from $77.7B in 2024, exceeding net cash provided by operating activities of $139.5B and reducing company-defined free cash flow to $11.2B from $38.2B.

The selected source's physical rows below are retained verbatim; its immediately preceding reconciliation paragraph specifies **2024 and 2025 (in millions)**:

```text
Year Ended December 31,
 202320242025
Net cash provided by (used in) operating activities$115,877 $139,514 
Purchases of property and equipment, net of proceeds from sales and incentives(77,658)(128,320)
Free cash flow$38,219 $11,194 
```

## Two independent refutations

1. **Period alternative:** the output explicitly uses the 2025 amounts, and the source has the same 2025 column. Exact values are 128,320 < 139,514 million. A prior-year comparator does not rescue the stated inequality.
2. **Definition alternative:** issuer net-PP&E purchases are $128.320B; the independently selected conventional capex amount is $131.819B. Both are below $139.514B OCF. Issuer FCF is correctly $11.194B and conventional FCF correctly $7.695B. The code-owned table therefore does not make the separate model-authored “exceeding” clause true.

Draw 1 states that issuer FCF declined as purchases rose; it does not repeat this false comparison. Both actual draws retain the same correct source-owned issuer object, and the compatibility dictionary leak is fixed. All 68 non-AMZN rows have no issuer binding. The deterministic baseline's 70/70 and Copilot's 18/18 green outcomes did not detect this statement.

## Scope and causal limits

Diff against release base `1c644e867832831bc8f6874ca7d71b72e35197fc` changes no prompt/recovery module or red-flag generation rule. The complete primary `_assemble_structured_summary` AST through primary request construction, response parsing and source binding boundary is identical; all three primary/recovery request-call ASTs are identical. Added recovery source association runs after recovery returns. The renderer adds the separate issuer blocks before the existing unchanged red-flag rendering loop; compatibility handling excludes only the owned issuer field from a copy. The new leaf neither reads nor writes red flags. Static evidence is retained in `request-parity.json`.

All 70 retained source excerpts and XBRL inputs, and the captured generation configuration other than source SHA, match the original #927 run. That verifies source/configuration and request-construction parity. These artifacts do not retain every raw outbound request or prove identical provider scheduling, backend state, sampling or behavior. The differing model prose is observed; a causal implementation regression or purely stochastic explanation is not proven. No new model run, implementation, or deployment action was performed for this note.
