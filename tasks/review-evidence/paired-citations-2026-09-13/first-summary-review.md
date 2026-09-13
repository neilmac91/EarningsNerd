# PR837 summary semantic review

Scoped actual-output review of `outputs/pr837-summary/eval-report-34729105583/eval_20260913T010048Z.json` against `outputs/pr835-summary/eval_20260913T003445Z.json`. No source fetch, generation, code change or paid call. Root separately verified all 52 attempt integrity records.

## Scoped preservation verdict

All 52 source_provenance, grounding_excerpt, coverage_inventory and xbrl_grounding objects are exactly unchanged. All 52 deterministic leverage fields, financing comparisons, shareholder returns, returns on capital and cash-conversion/FCF-basis fields match PR835. The paired-Copilot change has not introduced an observed summary-owner regression in these controls. This does not clear the separate ASML paired-citation failure or provide general financial-quality clearance.

Ford results 18/19 both retain full-year 2026 adjusted EBIT $8.5–$10.5 billion and adjusted FCF $5–$6 billion, with segment figures and Outlook assumptions. These match the selected Outlook source, including the distinction that the IEEPA benefit has no adjusted FCF benefit until 2027. The former omitted-Outlook/blanket-absence failure is not reproduced.

AAPL results 0/1 both retain the $100 billion May 2025 repurchase authorization and quarterly dividend change from $0.25 to $0.26 per share in the verified capital passages and final output. Financing comparison remains two outflows, and the separate commercial-paper purpose explanation remains available.

MELI results 50/51 both retain financing inflows $2,904 million versus $1,959 million and the complete source-owned Mercado Pago funding paragraph. The deterministic $10.8B conventional FCF line still explicitly defines OCF minus selected capex and disclaims issuer-defined/discretionary cash. This preserves the existing bounded owner; the lead still says bare free cash flow $10.8B, so no whole-answer issuer-basis correction is claimed. A later cash-lead candidate is separate from this assessment.

## Surviving material accounting findings — existing class, not new source drift

**MELI, results[50] and results[51].raw_sections.earnings_quality.operating_vs_one_time:** both say operating income $3,201M was reduced by the $337M foreign-currency loss. The supplied grounding_excerpt at line 2147 contains the FX row; the surrounding consolidated income statement reports Income from operations 3,201, then Other income (expenses): interest income 138, interest expense (160), FX loss (337), yielding pretax income 2,842. The interpretation incorrectly moves a below-operating item into operating performance.

Refutation 1: checked whether FX is embedded in the operating subtotal; the source statement places it after the subtotal and the arithmetic `3,201 + 138 - 160 - 337 = 2,842` confirms the separate bridge. Refutation 2: checked final rendered executive_summary rather than treating this as discarded raw prose; both retain the statement. PR835 MELI run 0 already made the same wrong inclusion, whereas run 1 described the net-income bridge without it. This is a recurring material model-interpretation class, not evidence that PR837 code changed the source or deterministic owners.

**SE, results[44] and results[45].raw_sections.earnings_quality.operating_vs_one_time:** run 0 says operating income includes debt-extinguishment and FX gains; run 1 says it includes investment loss and debt-extinguishment gain. The supplied grounding_excerpt at line 1244 contains the debt-extinguishment row; the surrounding table reports 2025 operating income 1,985,306 (thousands), followed by interest income 331,072, interest expense (33,610), net investment loss (43,443), debt-extinguishment gain 21,017 and FX gain 20,517, yielding pretax income 2,280,859.

Refutation 1: table order and exact bridge `1,985,306 + 331,072 - 33,610 - 43,443 + 21,017 + 20,517 = 2,280,859` establish these are below operating income. Refutation 2: the narrative expressly names operating income, so this is not merely a broad net-income statement; the raw earnings-quality field is rendered into the final summary. PR835 SE run 0 already included debt/FX gains in operating income. Record as the same outstanding accounting-relationship class, not a new PR837 feature regression.

## Refuted and limited observations

The correct financing paragraph does not certify unrelated earnings-quality prose. Conversely, the recurring accounting errors do not invalidate the unchanged source-owned financing/debt/cash controls. Source omission is not an explanation for the two findings above: both relevant income statements are present in the actual supplied excerpts. Ford source availability and financial-versus-adjusted guidance scope were checked directly. AAPL program retention was checked in both draws, not inferred from metadata. TSM's phrase “supported by non-operating income” remains imprecise, but this review did not elevate that ambiguous wording to a new confirmed inclusion finding.

Coverage is targeted: all 52 deterministic/source identities and earnings-quality narratives were inspected, with deeper selected-source checks for the requested preservation controls and the material survivors. This is not an exhaustive full-filing or every-output-sentence audit. No claim of world-class quality, universal quote fidelity or release acceptance follows.
