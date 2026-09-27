# Independent review of the candidate-r causal instruction

Reviewed commit `8c2101352e9a8826cf405bd91df4bd89538aecc3` read-only on 2026-09-27. Scope: `summary_schema.py`, the 10-K/10-Q analyst preambles, and the existing `test_recovery_context` gate. No tests, model calls, or source edits were performed during this review.

## Verdict

**Clear within the bounded prompt-contract scope.** I found no material correctness or release-blocking defect in this causal delta.

The general rule now binds an explanation to the same line, named measure, entity/component scope, period, and number role. That closes the observed transfer from net-interest-income drivers to total revenue while still allowing a source-stated total decomposition. The example distinguishes these cases directly: a filing statement that total revenue rose reflecting net interest income and noninterest income may be reported; causes and offsets stated only for net interest income stay on net interest income.

The 10-K and 10-Q preambles remove the former instruction to infer share-count causality whenever EPS and net-income growth diverge. They preserve both useful facts: report the divergence and a separately reported share-count movement, and retain a causal attribution when the filing itself states that relationship. Otherwise the supplied example uses noncausal “while” wording.

The shared support rule reaches the primary request and every recovery request. The field-specific driver contract remains on the actual model-authored explanation slots. Structured mode does not depend on the markdown preamble: its schema descriptions carry the same general source-identity rule and driver rule. The preamble provides the additional EPS example on the unstructured 10-K/10-Q path without weakening the shared rule.

The regression gate is accurately scoped. It checks exact instruction delivery through both primary modes, all four filing-form paths, recovery requests, and schema field descriptions. It does not feed a model response into a deterministic semantic accept/reject routine, enable the disabled attribution verifier, or claim that prompt presence proves model compliance. The retained implementation README says this explicitly.

## Refutation attempts

1. **Could the stricter same-line rule suppress legitimate total decomposition?** No. The rule permits a cause or attribution stated by the filing for the same total line and the driver example explicitly permits the total-revenue decomposition. It forbids only moving a component-specific X/Y explanation onto the total.
2. **Could the EPS correction discard a source-stated buyback/dilution explanation?** No. Both preambles explicitly allow the attribution when the filing states the relationship. The fallback changes only unsupported inference from co-moving net income, EPS, shares, or repurchases into a noncausal comparison.
3. **Could the test create false deterministic semantic acceptance?** No. The changed test asserts request/schema bytes and absence of the retired inference instruction. It makes no assertion about generated prose passing G2–G5, and no production verifier or admission flag changes in this delta.

## Reviewed hashes

- `backend/app/services/summary_schema.py`: `3c287f6d95c9d41fe58b4d48fb1389d566c07ffd4c2254584df19e1eeefe73b5`
- `backend/prompts/10k-analyst-agent.md`: `2ea6ff8a72237f79a5e5949e7ab3459249b4ca16f7709fd10d06caa99e06bb1c`
- `backend/prompts/10q-analyst-agent.md`: `ca3e202ce349688e43ea42de56b685aa8450f0b7b012585f1cd1daa92fe5b489`
- `backend/tests/unit/test_recovery_context.py`: `f0b73d6fb60446bde08c3212aa61d41e07be47c13b73c19958725470f3f290ad`

The remaining uncertainty is empirical model behavior under the frozen 35 × 2 cohort and the existing semantic bar. It belongs in the hosted r evidence and source-backed hand-check, not in this wiring test.

## Final cash-formula alignment reread

I reread the completed premeasurement prompt delta after the shared and legacy cash instructions were aligned. It is clear within the same bounded contract. The shared rule requires code-derived values to be named **selected operating cash flow minus absolute selected capex**, reserves **free cash flow** for a filing-defined measure, and requires the issuer's formula, reconciliation, and quoted wording to remain distinct. The structured primary path uses the same formula-owned name in its one-home rule. The 10-K, 10-Q, and 20-F legacy preambles use that name and separately preserve filing-defined free cash flow; 6-K receives the shared rule without a form-specific cash-coverage mandate. Primary and all five recovery requests receive the shared rule once for every structured/unstructured form in the existing actual-wire gate.

Two refutation passes did not identify a defect. First, the wording does not erase a filing-defined free-cash-flow measure: it explicitly permits the name and preserves the source formula or reconciliation. Second, changing the label does not alter arithmetic or silently certify total capex: the code-owned calculation still uses the selected operating-cash-flow point and absolute selected capex cash-flow amount, and the existing basis qualifier says an issuer-defined measure may differ. The test remains a request-contract gate and makes no deterministic claim that a model will obey the instruction.

The adjacent premeasurement changes are also coherent with this boundary: the primary instance extractor preserves the selected `raw_tag` for assets/equity, while companyfacts and legacy data remain unqualified; unknown ratio scope renders **scope unestablished**, which survives the placeholder filter without inventing a concept. Empirical compliance and quality remain measurement work.

Final reread hashes (uncommitted checkout state at review time):

- `summary_schema.py`: `ad127eebc543cd93aa67379b83cfa62d84df2ad6e1206b6c7761f8bfdff417c5`
- `openai_service.py`: `a5e9f1178098e3bc253c3cd917e79cde9b93e931a7d87acad0c8d76636594a08`
- `10k-analyst-agent.md`: `6aae93c1c4aea1abc52e0b1eef65dba286fb9dd9ca8961f842c3d601005d0251`
- `10q-analyst-agent.md`: `e5896afa64de0727a319911924d1a21bbd6c64787474ab750ebd9c434d101afc`
- `20f-analyst-agent.md`: `f700d4c8cce19f98d0318bc606a491a7bd01cb7cc0e7c04fdd0ec470c772e86a`
- `test_recovery_context.py`: `23c3a3b496d16524e65519a540033d74dd491e68baf9df547f508fdba430b527`
