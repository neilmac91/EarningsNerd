# Corrected #799 round 2: independent financial review A

Reviewed 2026-09-09. **The reported-label improvement survives; narrative quality is not cleared.** This is a bounded acceptance review of 16 outputs, not a new full-filing review or a global defect-rate estimate.

## Scope and evidence

R2 is `work/pr799-summary-round2/eval_20260909T083945Z.json`; R1 is `work/pr799-summary/eval_20260909T075719Z.json`; C is `work/pr797-summary-round2/eval_20260909T072820Z.json`. All result numbers below are zero-based; even/odd are repeats 0/1. I read **all raw sections of R2 results 0–15**, covering AAPL, MSFT, NVDA, JPM, KO, TSLA, AMZN and XOM. I compared relevant R1/C passages and the earlier independent report `work/pr799-financial-review-a.md`, verified source windows and inspected relevant generated Markdown. I did not reread every complete SEC filing or every R1/C raw section during this pass. `G@N` means the character offset in that result’s `grounding_excerpt`; `F` means the retained full-filing packet.

For every assigned result, `source_provenance`, `grounding_excerpt` and `xbrl_grounding` are exactly equal across R2/R1/C. Source SHA prefixes are AAPL `548ae59778cf`, MSFT `99d693f6c154`, NVDA `1b5de37b973da`, JPM `4d9febdbc2038`, KO `5d3229a1ead5`, TSLA `90d5d2bc4057`, AMZN `beb1bfc28558`, XOM `3591db2246ab`; full hashes and exact public SEC URLs remain in each artifact’s provenance. Identity equality establishes a controlled comparison, not complete source coverage. No model calls, network, tests or repository edits were performed.

## Preserved improvements and controls

| Results | Observed final behavior |
|---|---|
| 0/1 AAPL | Dollar **Gross margin** is a legitimate reported subtotal, not a percentage mislabeled as dollars. Genuine operating income of $133.1B remains in repeat 0’s table and repeat 1’s earnings discussion. |
| 2/3 MSFT | Reported dollar gross margin and $128.5B operating income remain distinct from $101.8B net income and below-operating other expense. |
| 4/5 NVDA | $53.536B operating income is preserved. R1’s claim that revenue more than doubled is gone: $81.615B versus $44.062B is about 85%. Lower diluted shares correctly help EPS growth in both repeats. |
| 6/7 JPM | **Income before income tax expense**, $72.595B/$75.081B, is honestly labeled; no fabricated operating subtotal. EPS growth despite lower net income is correctly associated with lower shares. |
| 8/9 KO | $4.359B/$3.659B operating income and $3.924B/$3.330B net income remain valid. |
| 10/11 TSLA | Genuine operating income and negative revenue, automotive, net-income and EPS changes retain their proper amounts/signs. Repeat 1 no longer uses the wrong EPS denominator explanation. |
| 12/13 AMZN | Genuine operating income is retained; the R1 assertion that $15.2B other income equals 19.6% of pretax income is absent. |
| 14/15 XOM | The original pretax-as-operating row remains absent. Sales and other operating revenue is distinguished from total revenues and other income. Repeat 1 states the correct debt components without the false decline. |

These eight companies do not supply the loss-crossing controls needed to accept the new signed-delta normalization generally; the parent’s projection and other reviewers cover those cases.

## Surviving findings, ranked

### 1. TSLA repeat 0: wrong adjustment direction and accounting level — material narrative

R2 `results[10].raw_sections.earnings_quality.operating_vs_one_time` says: **“Excluding these items, core operating performance was weaker than reported operating income suggests.”** The preceding items are $494M restructuring charges and $419M other expense. G@16488 shows operating income $4,355M after restructuring; other expense is below operating income. Adding back the operating charge yields $4,849M, higher, not lower. This is a new R2 instance versus R1’s accurate placement of charges; C repeat 1 already had related weak adjustment wording.

**Refutation 1:** Automotive deterioration can make underlying year-over-year results weaker, but the sentence explicitly compares an exclusion with reported operating income; adverse charges cannot create that direction. **Refutation 2:** Non-operating bitcoin/FX expense could explain net-income quality, but cannot be removed from an operating subtotal that excludes it already. The error appears in generated Markdown too. Repeat 1’s “declined less sharply” is not charged separately: adding restructuring back in both years gives $4,849M/$7,760M, about −37.5%, versus reported −38.5%; that direction is viable, although the mixed non-operating wording should be made explicit.

Related repeat-0 table EPS commentary still says higher diluted shares **“partially offset”** the decline. G@17268 has 3,528M versus 3,498M shares: dilution worsens the decline. **Refutation 1:** Numerator/net income genuinely fell, so the EPS values are not disputed. **Refutation 2:** The higher-share denominator cannot offset positive-income EPS contraction. This is an R1 survivor; repeat 1 is improved. Fix with a signed, same-subtotal bridge and denominator-direction control, not amount parsing.

### 2. AAPL repeat 1: adverse valuation allowance described as a tax-rate driver downward — material, mitigated

R2 `results[1].raw_sections.earnings_quality.operating_vs_one_time` attributes the lower effective rate to the absent prior State Aid charge **“and a $2.1B valuation allowance increase in 2025.”** G@31424–31700 shows the allowance change **+2,091** in the tax reconciliation; State Aid is **(486)** current versus **10,246** prior. The allowance increases tax expense and offsets favorable drivers. The wrong explanation is rendered. It recurs from C repeat 1; R1 had removed it.

**Refutation 1:** Removing the prior $10.2B charge does lower the comparative rate, and that part is correct; it does not make the separately joined allowance favorable. **Refutation 2:** A valuation allowance could theoretically reverse, but the source explicitly records a positive expense reconciliation, not a release. Do not resurrect the old claim that all $10.7B is a current benefit: repeat 0 expressly calls it a year-over-year decrease. Preserve that distinction while correcting the signed bridge.

### 3. KO both repeats: cash rebound explained without the dominant prior payment — material existing residual

R2 `results[8/9].raw_sections.the_print.key_takeaways[2]` attributes the $2.021B versus −$5.202B OCF swing to **“working capital normalization”** / **“improved working capital.”** Repeat 0 also calls the prior period a working-capital drain. G@77000–77400 explicitly says the fairlife liability reached **$6,173M and was paid in March 2025**. This is a dominant explanation of the $7.223B cash swing, absent from both raw summaries. R1 and C already had this defect.

**Refutation 1:** Settlement of a contingent liability can flow through working-capital cash movements, so the broad category is not intrinsically false; it is materially incomplete when used to explain this rebound. **Refutation 2:** Correct cash figures and a generic prior outflow disclose the direction but not the acquisition-related comparator that prevents reading the rebound as ordinary operating improvement. Calendar-day and future-tax-exposure residuals also remain open; this round is not their clearance. The relevant fairlife passage is supplied to the model, so this omission cannot be blamed on absent generator text.

### 4. AMZN repeat 0: note balance promoted to total investment — material scope error, mitigated elsewhere

R2 `results[12].raw_sections.value_drivers.highlights[0]` says **“total Anthropic-related investments reaching $45.8B fair value at year-end.”** G@55481–55900 separates **$14.8B nonvoting preferred stock** from **$45.8B convertible notes**. The asserted total omits the preferred position; the combined disclosed carrying/fair-value amounts are $60.6B. This specific total claim is absent in R1/C and appears in R2 Markdown.

**Refutation 1:** $45.8B is a valid figure for the notes mentioned earlier in the sentence, but the following phrase explicitly broadens it to total Anthropic-related investments. **Refutation 2:** R2’s footnote distinguishes notes and preferred stock correctly; that mitigates rather than reconciles the conflicting headline. Preserve cost versus carrying/fair-value distinctions: the separate $8B investment-cost description in repeat 1 is not rejected. Remediation needs component/total and valuation-basis entailment, not a numeric equality classifier.

### 5. MSFT both repeats: growth confused with acceleration — existing comparator family

R2 `results[2].raw_sections.the_print.what_changed` says **“accelerated to 15% from 16%.”** G@414 has revenues 281,724/245,122/211,915, proving slowing growth. Repeat 1 now says **“accelerated across all segments.”** Full source `02-MSFT/03-FULL-FILING.txt` F02620–F02638 presents recast comparable segment years: Productivity revenue 120,810/106,820/94,151 (13.1% versus 13.5%); More Personal Computing 54,649/50,838/44,820 (7.5% versus 13.4%). Intelligent Cloud alone accelerates among these rows.

**Refutation 1:** Positive growth across all segments is supported, but “growth accelerated” asserts a change in rate. **Refutation 2:** Segment recasting could invalidate an old comparison; this check uses the filing’s same presented three-year basis. C and R1 already contained the slowing-as-acceleration defect, with repeat incidence/wording changing. Retain as a narrative comparator acceptance control.

### 6. XOM repeat 0: debt increase called decrease — persistent directional error

R2 `results[14].raw_sections.balance_sheet_liquidity.leverage` says **“$43.5B … down from $41.7B.”** G@3496–3700 gives short-term 9,296/4,955 plus long-term 34,241/36,755: total 43,537/41,710, up $1,827M. R1 had the error in both repeats; C did not; R2 repeat 1 is corrected.

**Refutation 1:** Long-term debt alone declined, but this sentence explicitly defines total debt as both components. **Refutation 2:** Correct rising net debt and the correct numerical pair reduce the damage but do not make the debt direction true. This is prose, visible in Markdown, outside the new scalar parser’s correction.

### 7. NVDA current-versus-change labels remain inconsistent — lesser numerical/basis issue

R2 `results[4].raw_sections.earnings_quality.operating_vs_one_time` calls current other income $16.1B, while repeat 1’s net-income table commentary calls the change **“a $15.9B swing.”** G@68032–68080 explicitly separates current **15,929**, prior **(180)** and change **16,109**. Repeat 0 persists from R1; repeat 1 fixes current earnings prose but newly reverses the swing label.

**Refutation 1:** $16.1B is valid as the change, not current other income. **Refutation 2:** Rounding cannot turn $15.929B into $16.1B to one decimal; total other income is $16.367B, also not that figure. The $0.18B discrepancy is small relative to $58.3B net income, so do not inflate it into a major earnings-level error. The accompanying “excluding gains, operating income” phrasing is not independently charged as a numerical bridge: it can name the separately reported operating measure, although taxes mean it is not a net-income subtraction.

## Evidence contract, diagnostics and remaining scope

Raw evidence remains imperfect despite honest empty strings in several XOM rows. AAPL repeat 1’s EPS evidence is a newly composed sentence about diluted shares, not an exact excerpt; TSLA repeat 0’s EPS evidence similarly restates the result. Exact-string checks found neither in grounding or generated Markdown. **Refutation 1:** Correct underlying figures do not satisfy a verbatim raw-field contract. **Refutation 2:** Suppression from Markdown means this is not evidence of a displayed fabricated quotation. AAPL repeat 1’s total-sales evidence discusses **Americas** sales: a located sentence does not by itself entail the consolidated row. These are evidence-contract/entailment residuals, not automatically material numerical errors or grounds for a new citation gate.

All 16 stored `gate_failures` arrays are empty. Fifteen stored delta scores are 1.0; KO repeat 1 is 0.0. Its actual Markdown operating-income row is **$4,359M / $3,659M / +19.1%**, arithmetically correct. The earlier proximity-based scorer issue remains a plausible explanation; I did not rerun the scorer or claim an exact new match trace. Passing metrics do not detect the narrative findings above.

Preview metadata consistently states `summary_call_including_internal_retries` and final-response association `not_observed`. I inspected a retained initial AAPL fallback frame; it is not the terminal financial answer. These observations do not establish per-provider association or render parity for all transient frames; the parent’s projection owns that acceptance. No claim of 16 visually verified UI outputs is made.

JPM’s earlier caveated adjusted-comparison concern is not upgraded merely because it recurs. AMZN’s $11.2B issuer FCF versus approximately $7.7B gross-capex derivation remains a separately scoped basis issue; neither amount alone is automatically false. Prior source/legal, omitted maturity/guidance and coverage limitations remain open. The proposed earnings-quality intervention should use shared signed, same-period/subtotal and component/total basis rules; if another actual readout still fails those bridges, escalate to typed adjustment provenance rather than accumulating prompt warnings.
