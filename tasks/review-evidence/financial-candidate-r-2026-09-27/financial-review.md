# Financial candidate r — independent code review

Reviewed read-only at `8c210135` against its parent, with the dated-comparator delta `1ec2546f` checked against `origin/main`. I excluded the causal prompt/schema changes I authored from the independent verdict. I ran no pytest or provider calls.

## Verdict

Two should-fix findings remain before candidate measurement. The dated comparator, unknown legacy behavior, selected-cash deterministic output, issuer disclosure coexistence, and debt-subset wording otherwise read correctly. No locked contract test changed.

## Findings

### P1 — the production extractor discards denominator concepts before the new ratio custody layer

The derived ratio now copies its selected `numerator` and `denominator` into each ratio point (`backend/app/services/edgar/xbrl_service.py:1242-1250`), but the primary instance extractor only preserves `raw_tag` for cash and debt. `shareholders_equity` and `total_assets` take `instant_series_with_currency`, which discards the winning qualified concept (`backend/app/services/edgar/xbrl_service.py:461-470`). The companyfacts fallback likewise calls `select_fact_data` rather than `select_fact_data_with_concept` for both `net_income` and `total_assets` (`:1037-1042`). Consequently, an actual primary ROE denominator has no concept, and a fallback ROA has neither operand concept, despite the candidate record claiming that each ratio retains both selected operands “including their concepts.”

This matters most for equity: the live candidate list includes parent equity, equity including noncontrolling interests, IFRS total equity, and equity attributable to owners of the parent. The stored denominator value/date is correct, but its exact scope is unrecoverable after extraction. The new test does not exercise the producer shape: it manually injects `raw_tag` into equity/assets rows at `backend/tests/unit/test_xbrl_narrative_section.py:477-483`, then proves that the downstream copy preserves those synthetic tags. It therefore passes while production drops them.

Minimal correction: preserve the qualified winning concept for `shareholders_equity` and `total_assets` in the existing instant extraction loop, preserve the selected `net_income`/`total_assets` concept in the companyfacts fallback, and extend an existing accession/companyfacts producer-path gate. Keep absent historical metadata unknown; do not infer or borrow it.

Refutation attempt 1: perhaps another provenance sidecar restores these concepts before ratio construction. It does not: `normalise_series` can only carry `entry["raw_tag"]`, and the raw instant rows above omit it. Debt observations are separate and do not own equity/assets.

Refutation attempt 2: perhaps the concept is invariant and therefore unnecessary. Assets is narrow, but equity is explicitly first-candidate-wins across materially different parent/NCI scopes. The README’s concept-custody claim and the synthetic test also make the intended contract explicit. The finding stands.

### P1 — provider instructions still define the selected subtraction as “free cash flow”

The deterministic surfaces now correctly call the value “selected operating cash flow minus absolute selected capex” and say an issuer-defined FCF may use another formula. The actual provider prompt still gives the opposite instruction in current production mode: the 10-K prompt requires “free cash flow (operating cash flow − capex)” (`backend/prompts/10k-analyst-agent.md:106`), the 10-Q prompt does the same (`backend/prompts/10q-analyst-agent.md:93`), the 20-F prompt requires free cash flow (`backend/prompts/20f-analyst-agent.md:137-140`), and the shared provider instruction calls the deterministic slot “free cash flow” (`backend/app/services/openai_service.py:406`). The form prompt is inserted into `OUTPUT REFERENCE`, so these are live generator instructions, not comments.

The deterministic filler removes model content only from `earnings_quality.cash_conversion`. Other model-authored fields can still repeat a derived amount under the issuer-facing FCF name. `qualify_cash_lead` repairs only four exact regex sentence shapes; it deliberately leaves arbitrary prose untouched. Thus the candidate can still regenerate the same WMT-class measure-name collision that motivated the code-owned wording change.

Minimal correction: align the provider-facing coverage wording with the deterministic owner: request the selected OCF-minus-absolute-selected-capex value under that formula name, and permit “free cash flow” only for a filing-defined measure with its disclosed formula/basis. Apply the shared instruction to every form; do not alter the bounded issuer-disclosure owner.

Refutation attempt 1: perhaps code ownership strips every model FCF claim. It strips only `cash_conversion`; the remaining nine-section model fields survive, and the lead rewriter only recognizes finite whole-sentence patterns. The contradiction can therefore reach output.

Refutation attempt 2: perhaps the new grounding caveat overrides the old instruction. It supplies a caveat beside the value, but the same request explicitly tells the model to call OCF-minus-capex “free cash flow.” An instruction-delivery test for the deterministic phrase does not resolve contradictory instructions. The finding stands.

## Cleared checks

- **Prior basis:** the shared validator strips valid date text and rejects missing, blank, placeholder, and non-string prior periods on both render and grounding surfaces. Current and prior numerator scope is derived from each ratio point independently; absent legacy operand metadata renders as `(numerator scope unavailable)` rather than borrowing the sibling net-income metric. Dating the admitted point does not make it YoY, and the wording makes no change claim. Preserving the existing prior-selection policy matches the retained disposition.
- **Cash and issuer disclosure:** the deterministic value and cash-lead rewrite use the exact selected subtraction name; the issuer’s separately source-owned reconciliation remains labeled and visible. The second finding concerns live model instructions around those owners, not their deterministic arithmetic or coexistence.
- **Debt:** absence and subtotal claims are now explicitly limited to selected standardized XBRL. The code no longer claims that the filing text lacks debt or that a component set covers every borrowing the filing reports. Existing positive figures and complete-partition subtotal protections remain.
- **Tests and rules:** the changed tests retain prior arithmetic, band, source, and surface assertions; debt tests add negative assertions against the old filing-wide wording. The locked T1-T10/auth/Stripe inventory is byte-identical across `8c210135^..8c210135`. The ratio custody test is meaningful downstream but needs the real-producer addition described above. No baseline, judge constant, model flag, or network path changed.
- **Security/performance:** no new I/O, authorization, deserialization, or network surface. Operand copies are bounded small dictionaries. The shared `net_income_basis` helper removes duplication.

## Final rereview — `e17b6b63` against `origin/main` (`b63bee6b`)

I reread the complete financial candidate delta after the accepted fixes, including the changes I had authored earlier. This pass was read-only. I made no provider calls and did not run pytest. The working tree was clean. Root reports the focused producer/narrative/preview gate at 122 passing and has separately retained fail/restored-pass mutation evidence; those are supplied results, not tests I independently reran.

### Verdict

**CLEAR for one bounded hosted measurement.** I found no remaining material source-custody, semantic, or runtime-correctness issue that should block generation of the candidate-r measurement. This is **not adoption clearance**. The new prompt bytes require the unchanged-contract hosted cohort, retained-source/runtime identity checks, independent judging, both JPM outputs, all 18 negative controls, and all nine retained q G2/G3 identities. The RUNBOOK bar remains unchanged; deterministic checks and a better mean cannot waive the no-G4/G5-control/no-new-G2/G3 requirements.

One nonblocking release-hygiene item remains: `git diff --check origin/main` reports a blank line at EOF in `tasks/review-evidence/return-ratio-stamp-2026-09-23/current-runtime-measurement/p-v-q2-comparison.md:96`. It does not affect hosted execution or semantics, but should be removed before a clean push/check.

### Three-lens review

1. **Source custody and financial correctness — clear.** The primary filing-instance producer now preserves the winning qualified concept for equity and assets (`xbrl_service.py:461-470`), and each derived ratio copies the exact selected numerator and denominator point (`:1230-1252`). Current and comparator labels read their own ratio-owned numerator, so an income point skipped for lack of a matching balance cannot lend its scope to another ratio point. The real producer-path gate checks the selected income/equity/assets concepts and denominator date/value (`test_accession_xbrl_extraction.py:850-901`). The unchanged companyfacts and historical shapes do not fabricate missing provenance: they render `numerator scope unestablished`. Prior ratios are admitted only with an in-band value and a usable, stripped period on both grounding and deterministic presentation; the existing selection policy and arithmetic are unchanged.

   **Refutation 1:** I looked for another normalization or projection step that could strip or replace the new concepts before ratio construction. `normalise_series` carries `raw_tag`, the ratio stores copies of those normalized points, and the actual producer-path assertion crosses both steps. This does not reopen the original finding.

   **Refutation 2:** I tested the stronger objection that legacy/companyfacts values might silently inherit the sibling standalone net-income tag. `return_ratio_basis` consults only the ratio point's nested numerator; absent/custom metadata stays unestablished. The final shared projection is covered, so the former placeholder collision no longer removes the ratio sentence. Unknown fallback is an honest bounded disposition, not fabricated custody.

2. **Narrative semantics and source ownership — clear.** Deterministic output consistently names the computed amount as selected operating cash flow minus absolute selected capex and separately permits a filing-defined free-cash-flow measure with its literal formula/reconciliation (`xbrl_narrative.py:42-57`, `markdown_render.py:493-496`). The shared instruction reserves “free cash flow” for that filing-defined measure and reaches primary and recovery traffic; legacy 10-K, 10-Q, and 20-F prompts use the same rule. The actual-wire test exercises all four forms, both structured modes, and five recovery requests per case (`test_recovery_context.py:305-366`). Source-stated total-revenue decomposition remains allowed, while component causes/offsets stay on the component; EPS/share-count attribution now requires the filing to state the relationship. Debt absence and subtotal text is limited to selected standardized XBRL rather than the whole filing.

   **Refutation 1:** I searched the live shared rule, ONE HOME rule, and all three legacy form prompts for the prior instruction that equated the selected subtraction with issuer FCF. The old phrases are removed from the actual primary wire, while the shared instruction reaches recovery. The 20-F wrapping issue was confined to an exact test assertion and is now normalized as prose; it did not alter source or prompt bytes.

   **Refutation 2:** I checked whether the correction could erase a real issuer-defined FCF or issuer ROE/ROA disclosure. The source-owned issuer cash disclosure remains separate and literal, and the JPM coexistence gate retains the real issuer table excerpt beside the formula-qualified derived ratios. The correction narrows code-owned labels; it does not relabel quoted issuer measures.

3. **Runtime, rules, and tests — clear for measurement.** The delta adds no network, authorization, deserialization, model flag, generator flag, baseline, judge contract, arithmetic rule, or selection-policy change. Ratio operands are bounded flat dictionary copies with no circular reference. The prompt stamp is `summary-2026-09-r`, preserving the measured q identity. The named locked contract/auth/Stripe inventory and the eval baseline/golden/judge/scorer/runner files are byte-identical to `origin/main`. Tests cover actual source production, current/prior basis differences, malformed/blank/non-string comparator periods, all presentation surfaces, actual prompt/recovery wiring, source-defined cash coexistence, and selected-XBRL debt wording.

   **Refutation 1:** I considered whether nested operand copies could mutate the selected source or cause recursive/large serialization. Both inputs are normalized flat point dictionaries, copied once per bounded ratio series; the tests retain source equality and no new I/O is introduced.

   **Refutation 2:** I considered whether instruction-delivery tests could justify adoption. They cannot. They establish only that the intended bytes reach each request. Candidate behavior remains stochastic and must be measured and independently judged under the preserved corpus and bar. That limitation blocks adoption, not the single hosted measurement needed to obtain the evidence.
