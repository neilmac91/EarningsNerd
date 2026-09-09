# PR 799 first d financial readout — assigned eight filings

Reviewed all raw sections in **16 d outputs**, results[0]–[15], both repeats of AAPL/MSFT/NVDA/JPM/KO/TSLA/AMZN/XOM, against corresponding #797 final tables and relevant prior narrative fields. Recovered truncated reads in smaller chunks. This is a bounded financial comparison, not a fresh complete-filing audit or visual-preview acceptance. No network/model calls, tests or edits. Pure deterministic replay of the existing delta scorer was used diagnostically.

**D** = `work/pr799-summary/eval_20260909T075719Z.json`; **C** = `work/pr797-summary-round2/eval_20260909T072820Z.json`. Indexes below are zero-based, paths follow `results[i].raw_sections`. Source citations `G@N` mean character offset N in that same result's exact retained `grounding_excerpt`, not an HTML line. All 16 assigned grounding strings equal their corresponding C strings. Each result retains exact public SEC URL/hash in `source_provenance`; offsets are reproducible from D. This establishes a same-input comparison, not attribution of every stochastic change to d.

## Main result

d removes the confirmed false operating basis in both XOM repeats and corrects JPM's pretax row labels. Genuine operating income survives across MSFT, NVDA, KO, TSLA and AMZN in both repeats; AAPL run 0 retains its $133.1B operating result in earnings-quality prose rather than a table row, while run 1 includes it in the table. Broad table preservation succeeds; several narrative errors remain or appear for the first time in this comparison. Do not equate corrected labels with complete analytical acceptance.

| Filing | Actual row/basis outcome | Residual distinction |
|---|---|---|
| AAPL | Total net sales, net income and diluted earnings preserved; run 1 adds issuer-reported dollar **Gross margin** and operating income. | Dollar Gross margin is a legitimate reported concept, not a percentage error. Prior tax-swing framing improves: both now explain the prior $10.2B charge rather than removing a $10.7B current benefit. Current legal-restriction coverage remains unresolved. |
| MSFT | Operating income 128,528/109,433M (rounded in run 1), dollar Gross margin 193,893/171,008M, net income and diluted EPS preserved. | Prior 16→15 acceleration error survives in run 1, absent in run 0. OpenAI expense discussion is more explicit; noncash lease/capital commitment coverage is not thereby closed. |
| NVDA | Revenue 81,615/44,062M, operating income 53,536/21,638M and diluted EPS 2.39/0.76 correct. | New doubled-revenue claim and EPS-direction error in run 1; current other-income/swing confusion in both. Prior liquidity availability issue is not certified resolved. |
| JPM | Both now correctly name **Income before income tax expense**, 72,595/75,081M; no synthetic Operating margin row. | C called those same pretax amounts operating. G@1131 explicitly names pretax. Bank NII components and correct guidance survive; adjusted-core interpretation remains an older issue, not a new d finding. |
| KO | Operating Income 4,359/3,659M and 19% change correct; broad P&L rows retained. | Delta-score failures are false positives; prior cash-flow causal omission and six-extra-days omission persist. |
| TSLA | **Income from operations** 4,355/7,076M and −38.5%, EPS 1.08/2.04 and −47.1% correct. | New wrong EPS-denominator explanation; restructuring discussion improves over C's faulty exclusion framing. xAI amount/conditions still incomplete. |
| AMZN | Operating income 79,975/68,593M, net income 77,670/59,248M and diluted EPS preserved. | New pretax-share denominator error in run 0. Existing $11.2B company FCF versus $7.7B derived FCF ambiguity remains; both arithmetic bases can be valid. |
| XOM | Both omit C's false Operating income 41.3/48.9B and Operating margin; run 1 adds correctly labeled sales versus broader revenues/other income. | G@1099 labels 41,268/48,873M **Income (loss) before income taxes**. New debt-direction wording; older guidance/maturity/segment completeness remains. |

## Ranked surviving findings and refutations

### 1. Material narrative regression: NVIDIA revenue falsely more than doubled

D results[5].the_print.what_changed: **“Revenue, net income, and EPS all more than doubled year-over-year”**. G@262 reports Revenue 81,615 versus 44,062M, an 85.2% increase (1.852×), not over 100%. Both C repeats instead say revenue/profitability accelerated and Data Center nearly doubled; this exact false assertion is new to the compared d output, though comparator/causality defects are an existing corpus family.

Refutation 1: the adjacent headline and table correctly say 85%; that mitigates reader harm but does not make the categorical summary correct. Refutation 2: net income/EPS did more than double, and the prose might loosely summarize them; it expressly includes revenue, so those valid neighboring facts cannot support it. Correct the authored claim or preserve as a failed acceptance case; no ticker-specific workaround.

### 2. Material basis error in AMZN's earnings-quality contribution

D results[12].earnings_quality.red_flags[1] says $15.2B other income **“accounted for 19.6% of pre-tax income”**. G@9991–10450 states other income 15,229M, pretax income 97,311M, net income 77,670M. The actual pretax share is 15.65%; 19.6% is approximately the net-income denominator. C's red_flags are empty; C discussed the nonoperating gain without this percentage.

Refutation 1: rounding 15.2 versus 15.229 does not bridge 15.6% to 19.6%. Refutation 2: 19.6% is a defensible size comparison to net income, but the candidate explicitly labels pretax; taxes and equity-method items make the bases different. This overstates the claimed earnings-quality contribution by about four percentage points. Retain as a new source-backed basis error, not a claim d caused all existing AMZN cash issues.

### 3. New but numerically mitigated direction errors

**XOM both**, results[14/15].balance_sheet_liquidity.leverage: debt **“$43.5B ... down from $41.7B”**. G@3469–3670 gives current/previous notes 9,296/4,955M plus long-term debt 34,241/36,755M: total 43,537/41,710M, **up** 1,827M. C did not claim this decrease. Refutation 1: long-term debt alone fell, but the sentence explicitly sums notes/loans plus long-term debt. Refutation 2: current net-debt/cash numbers are correctly presented and run 0 explicitly says net debt increased, mitigating to a wording/direction defect rather than hidden false balances. Both runs still require correction.

**TSLA both**, results[10/11].results_that_matter.table[8].commentary says higher weighted-average shares **partially offset** the EPS decline. G@17132 gives diluted shares 3,528 versus 3,498M: higher denominator worsens a positive-income EPS decline. C correctly says higher shares contributed to the decline. Refutation 1: net income falls more slowly than EPS (46.5% versus 47.1%), independently confirming dilution's direction. Refutation 2: the dollar EPS values/deltas remain correct, so this is explanatory, not a numeric-row failure.

**NVDA run 1**, results[5].results_that_matter.table[4].commentary similarly says lower diluted shares partially offset EPS growth. G@808 gives 24,391 versus 24,611M: lower shares help growth. Refutation 1: 214% EPS growth exceeds 211% income growth, agreeing with denominator arithmetic. Refutation 2: share repurchases are real and C correctly described their help; their existence does not reverse the effect. These denominator errors are new in the compared statements; classify as narrow narrative regressions with correct adjacent numbers.

### 4. New current-versus-change confusion, NVIDIA other income

D results[4/5].earnings_quality.operating_vs_one_time calls **$16.1B current other income**. G@567 reports other income (expense), net 15,929M versus −180M; the change is 16,109M. Both C repeats correctly used $15.9B current other income. D's net-income row commentary calls the $16.1B an increase/swing, which is valid.

Refutation 1: total other income net is 16,367M, also not 16.1B. Refutation 2: 13.4B public-equity plus 2.6B nonmarketable gains approximately explain the category but do not convert a comparative swing into its current balance. The ~$171M difference is small against income; retain as a basis/precision regression, not the material doubled-revenue finding.

## Delta-consistency advisory: assigned failures are not wrong financial deltas

Direct replay reproduces assigned scores: KO results[8/9] **0.0**, TSLA result[11] **0.75**, other 13 results **1.0**. The actual flags are:

- `Operating Income: prose ~12% vs table 19%` (both KO).
- `Automotive sales: prose ~46.5% vs table 9.2%` (TSLA run 1).

The scorer searches −40/+80-character windows around exact metric names. KO's narrative discusses 12% revenue growth near operating income; its actual table/source state operating income 4,359/3,659M = 19.13%. TSLA's headline links the 46.5% **net-income decline** to automotive sales; actual automotive-sales row/source 65,821/72,480M = −9.19%. Refutation 1: direct source and row arithmetic agree. Refutation 2: the cited prose percentages have different subjects, so proximity is not a contradictory assertion about the row. Retain the score/advisory unchanged; report these as measurement collisions exposed by expanded/source-reported row names, not a reason to revert honest labels. These explain this assigned subset only, not the entire .8606 versus .9466 cohort movement. A 1.0 score also misses the true direction errors above.

## Older unfixed scope, not new regressions

MSFT result[3] repeats C's “accelerated from 16% to 15%.” G@414–460 gives 281,724/245,122/211,915M: growth slowed 15.67%→14.93%. Refutations: different rounded precisions cannot reverse the trend; Intelligent Cloud's higher growth does not change consolidated revenue's comparator. Run 0 avoids the error; do not count it newly introduced.

KO both still attribute the OCF rebound to working-capital improvement and omit the six extra days. G@77000 identifies the **$6,173M fairlife liability paid March 2025**; G@64710 explicitly states **six additional days**. Refutations: ordinary working capital may contribute but does not explain away the dominant prior cash payment; correct 12% reported revenue growth does not establish comparable daily growth. These were final Fable/Codex residuals and already appeared in C. Tax exposure coverage remains prior open scope, not re-certified here.

AMZN's two FCF/capex bases, MSFT lease/commitment scope, AAPL current legal restrictions, NVDA investment availability, JPM core adjustments, TSLA xAI quantified terms and XOM broad disclosure coverage remain tracked residuals. No absence in this bounded comparison is clearance. Raw supporting-evidence composition also persists; it must be distinguished from visible verified citations and belongs to the separate evidence/projection acceptance. First d artifacts remain intact; this review does not authorize regeneration or broaden acceptance.
