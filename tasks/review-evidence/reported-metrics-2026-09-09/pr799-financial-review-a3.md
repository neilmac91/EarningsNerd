# PR #799 financial readout — Pfizer, Boeing and Intel

Read all raw sections of both first d attempts for PFE (results[16/17]), BA ([24/25]) and INTC ([26/27]) in `work/pr799-summary/eval_20260909T075719Z.json`. Compared paired C tables, headlines, earnings-quality, capital allocation and liquidity in `work/pr797-summary-round2/eval_20260909T072820Z.json`, and actual Markdown table projections in both runs. All six retained grounding excerpts equal C. Source verification below uses zero-based character offsets within each result’s `grounding_excerpt`; paths otherwise start `raw_sections`. Read-only artifact/source analysis: no model, network, test or application change. This is bounded development-corpus review, not a renewed full-source coverage or release acceptance claim.

## Outcome and positive controls

PFE no longer presents $3.170B/$2.785B pretax income as operating income or manufactures its operating margin. Both attempts instead give correctly labeled attributable net income $2.687B/$2.967B. That is a real table-label improvement, even though the narrative still misuses the pretax bridge.

BA retains its genuine $4.281B operating income: repeat 0 in earnings prose, repeat 1 as the reported earnings/(loss)-from-operations table row. INTC retains actual operating loss −$3.136B/−$301M, adds gross profit $5.347B/$4.672B and attributable net loss −$3.728B/−$821M, and identifies loss/EPS basis. Do not treat removing a generic row from one table as deleting the figure from the whole summary.

INTC’s ex-impairment operating discussion improves: D[26] explicitly distinguishes $4.1B total restructuring/other charges from its $3.9B impairment component and calculates approximately $0.8B operating income excluding impairment. D[27] names impairment plus $74M severance and compares with **reported** prior operating loss. Source @0–1100 reports operating loss 3,136M; @31945 identifies severance74, asset impairment3,965 and total4,070M. Adding approximately3.9B to −3.136B yields approximately0.8B. C[26] instead says roughly breakeven while mixing non-operating items; C[27] can read as double-counting impairment and total restructuring. D does not claim a fully normalized like-for-like margin. Intel’s $111.394B parent equity and $124.989B total equity (@3160–3300) support the differently scoped equity figures in D[26/27]; do not misclassify those as a number error.

## Ranked surviving findings

### A3-01 — signed changes are corrupted in the Markdown projection; existing mechanism, additional d rows

Raw BA[24/25] says “Swung to profit”; actual `payload.executive_summary` renders attributable net income as −81.1% and EPS as −86.5%. BA[25] operating earnings renders −60.0%. Source @2162 onward shows $4,281M versus −$10,707M operating income, $2,235M versus −$11,817M attributable net earnings and $2.48 versus −$18.36 EPS. Correct transition wording is lost despite correctly displayed parentheses.

Raw INTC[26/27] says “Worsened by $2,835M”, “Worsened by $2,907M” and “Worsened by $0.54”. Markdown instead gives +941.9%, +354.1% and +284.2%. Source @0–1100 confirms negative values in both periods. These positive percentages are loss-magnitude growth, presented under signed income/EPS change without that basis.

**Refutation 1:** Percentage growth in an absolute loss magnitude can be meaningful, but the actual rows name signed income/EPS, show negative amounts, and replace explicit worsening/swing wording with unqualified percentages. BA’s loss-to-profit −81.1% cannot describe a reduction in profit consistently with those signed values. **Refutation 2:** This is not a new failure caused only by d’s parentheses: C Markdown already renders BA operating −59.8%/EPS−86.5% and INTC operating +929.9%/EPS+284.2% from leading-minus inputs. D adds attributable-net-income rows affected by the same existing mechanism and uses less rounded amounts. Correct the signed-value projection/transition behavior separately; preserve honest raw changes and valid amounts. Material representation defect, not evidence that the model emitted these rendered deltas.

### A3-02 — PFE tax bridge remains wrong; explicit tax-direction inversion returns in repeat 0

Both D[16/17].the_print.what_changed and table[1].commentary explain falling net income mainly through higher cost of sales/R&D offset by restructuring savings. Their supporting quotation instead explains **increasing pretax income**. Source @772 reports pretax3,170/2,785M, taxes461/(189)M and continuing income2,709/2,973M. Tax expense rose650M, more than offsetting the approximately385M pretax improvement. D[16].earnings_quality then says the quarter benefited from a “lower effective tax rate of 14.6% versus -6.8%”. @22948 expressly states that the rate increased, due to earnings mix and non-recurrence of favorable tax resolutions.

**Refutation 1:** The cost pressures are real, but the source says they only partially offset the pretax improvement; they cannot alone explain the reversal from pretax growth to net-income decline. **Refutation 2:** 14.6% is greater than −6.8%; neither a tax benefit convention nor underlying earnings adjustment makes it lower. C[16] correctly mentions higher tax rate; C[17] already has the weak operating-cost/net-income bridge. This is the established PFE tax/causality residual, with a new explicit inversion versus paired C[16], despite successful removal of the false operating table. Remedy: reconcile pretax, tax and attributable-net-income changes and retain the actual signs.

### A3-03 — BA still falsely identifies positive core earnings as excluding the disposal gain

Both D[24/25].earnings_quality.operating_vs_one_time say excluding the approximately$9.6B disposal gain leaves positive core operating earnings $3.236B/$3.2B. Source @81550–82400 explicitly reconciles GAAP operating4,281 less FAS/CAS service-cost adjustment1,045 to core3,236M. Its definition excludes the pension/postretirement adjustment, not the disposal gain. Source @2162 reports total disposition gains9,672M. Excluding all disposition gains from GAAP gives −5,391M; excluding the separately disclosed DAS gain9,566M gives −5,285M.

**Refutation 1:** $3.236B is a legitimate company non-GAAP figure; the error is falsely describing its adjustment basis, not rejecting non-GAAP reporting. **Refutation 2:** Both headlines and footnotes acknowledge the large gain, but the explicit “excluding” sentence still creates a false positive underlying-profit conclusion. Both C attempts already have this error; d does not resolve the original BA earnings-quality finding. Keep the company-defined core basis separate from an expressly derived ex-DAS result.

### A3-04 — PFE repeat 0 falsely says FCF covers the dividend

D[16].value_drivers.capital_allocation: “free cash flow of $2.2B comfortably covered the dividend”, beside $2.4B dividends. Source @7630 gives operating cash2,615M and capex436M, so derived FCF is2,179M; @8468 gives cash dividends2,445M. Shortfall266M, coverage0.891x. The paired C[16] does not claim coverage; D[17] avoids it.

**Refutation 1:** Operating cash2,615M alone covers the dividend, but the sentence explicitly says **free** cash flow, which deducts capex. **Refutation 2:** Rounded2.2B remains below2.4B; the post-quarter ViiV proceeds can improve liquidity but cannot turn first-quarter FCF into dividend coverage. Material capital-allocation assertion; preserve legitimate liquidity sources while correcting this comparison.

## Narrow additional issues and refutations

- **PFE[16].table[2] EPS commentary:** a higher diluted share count “partially offset” lower net income. Source @1783 has5,731M/5,710M; a larger denominator worsens positive EPS decline. **Refutation 1:** Different treatment for loss-per-share does not apply to Pfizer’s positive earnings. **Refutation 2:** Correct EPS amounts/delta mitigate but do not validate the causal wording. Both C attempts contain this; D[17] becomes neutral/correct rather than repeating the offset claim.
- **PFE[16] net-debt scope:** uses $60.6B long-term debt and concludes $47.5B net debt, omitting $3.890B short-term borrowing/current maturities (@4206). D[17] correctly includes them and gives about$51.4B. **Refutation 1:** It labels the first amount long-term, but the resulting unqualified net-debt assertion omits disclosed current obligations. **Refutation 2:** The adjacent maturity caveat is helpful but does not repair the net-debt calculation. C[16] had the fuller same-cash-basis net debt, so this is a regression in that repeat; C[17] uses a separately stated cash-only basis and is not directly comparable to the cash-plus-investments result.
- **BA[25].value_drivers.capital_allocation:** “$53.8B in long-term debt”. Source @6086 states long-term debt45,637M; total debt elsewhere in the same candidate is54.1B. **Refutation 1:** Including current maturities can justify total debt, but not the stated non-current amount. **Refutation 2:**54.1B is not rounding to53.8B, and the correct liquidity section mitigates rather than validates this contradictory number. C capital allocation contains no such53.8B statement. Narrow factual regression.
- **INTC[26/27].table[3].supporting_evidence:** the quotation describes net loss attributable to **non-controlling interests**, while the row describes loss attributable to **Intel**. **Refutation 1:** The same impairment affects both ownership groups, so the broad economic driver is plausible. **Refutation 2:** The NCI-specific sentence does not independently substantiate the parent’s3,728M/821M amounts or full bridge; the statement does. This is a traceability/entailment weakness on a newly added row, not proof that the parent amounts are wrong. The anti-dilution EPS quotation also explains excluded instruments, not by itself the actual EPS comparison.

## Scoring and residual scope

The stored hosted score objects report delta_consistency1.0 for all six, with no gate failures. No delta-warning false match needs refutation in this subset. Instead the real Markdown and narrative failures survive a perfect score: numerical matching of figures and nearby absolute percentages is not sign, subtotal or causal acceptance. Citation advisories flag PFE Metsera near-miss99.7 and INTC P&L near-misses99.7/99.6; these do not establish material content falsity or visible fabricated quotation. The more important PFE pretax-versus-net-income and Intel parent-versus-NCI entailment problems are semantic, not solved by exact substring matching. No scorer/test rerun was performed for this review.

INTC’s April Apollo purchase and financing are distinctly labeled post-quarter in both d summaries. The segment list still mixes Products with its CCG/DCAI children, but no fabricated revenue-share percentages reappear; hierarchy extraction remains separate. PFE’s ViiV transaction explicitly falls in Q2, and the source quote confirms that timing. These controls do not clear broader source/legal/forward completeness or every original Fable/Codex residual. BA’s missing credit-line quantities and PFE broader guidance/legal limits remain outside this focused closure claim.

## Retained source identities

| Company | SEC URL | Retained decoded-HTML SHA-256 |
| --- | --- | --- |
| PFE | https://www.sec.gov/Archives/edgar/data/78003/000007800326000054/pfe-20260329.htm | 3d1709528325d0b51c1f42f05508a2e43a88542306ac8efe47f7d05729721e1e |
| BA | https://www.sec.gov/Archives/edgar/data/12927/000162828026004357/ba-20251231.htm | 5e6dd009813c7851c73c30eb8a1117eab36e86a8c64bde61ad3af5444b052501 |
| INTC | https://www.sec.gov/Archives/edgar/data/50863/000005086326000079/intc-20260328.htm | 7e503a71a183a15ce714f9a4c3707d0622caae50fc0cc400b1c1c0d49d671244 |

Hashes establish retained identity only, not completeness. No new source fetch occurred.
