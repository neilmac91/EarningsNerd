# Final #799 review — COIN, BYND, MELI — September 9, 2026

All six raw section objects reviewed by exact diff against the fully read first-d objects; truncated BYND fields were separately reopened. Retained sources/excerpts are identical. Source and actual payload checks below distinguish semantic residuals from the deterministic normalization corrections. No new model calls or source fetches.

## Material survivors

**MELI run 1, value_drivers.highlights[1]: invented $4,900M note issuance.** Output attributes the amount to the exhibit index. Refutation1: the supplied index says **4.900% Notes due2033**, a coupon, not principal; it contains no $4,900M amount. Refutation2: full filing F01867 and F04704 independently identify **$750M** principal, and note table F04675 gives735M carrying amount. Neither supports4.9B. This instance is absent from first d; it is a newly observed semantic fabrication, not a proven effect of the correction code. The missing principal text in the generator excerpt explains a coverage limitation, but does not excuse turning an explicitly percentage-valued coupon into an invented amount. It belongs to evidence-role/basis work, not the display scalar parser (the model already emitted $4,900M).

**BYND both, debt total:**382.2M is still called total including300.5M+81.7M+29.5M. Refutation1: source balance sheet separately reports those three components, totaling411.7M. Refutation2: current29.5M disclosure elsewhere does not correct the stated total. First d run1 had the correct total; both final repeats now share the historical error. Do not promote a selected noncurrent anchor to total debt.

**MELI both, cash availability:**10.8B OCF less selected capex remains unqualified; issuer adjusted FCF1.481B and customer-fund restrictions remain unused. Refutation1: narrow arithmetic is valid, so no numeric fabrication claim. Refutation2: a generic regulatory-reserve risk in final run1 partly mitigates but does not reconcile discretionary cash/5.341B customer-fund contribution. Same material Fable family remains; prepared deterministic basis labeling and separate issuer-reconciliation work are needed.

## Narrower residuals / judgment limits

**BYND adjustment wording:** both now say excluding non-operating gains leaves substantial operating loss; run1 explicitly retains41.1M. The previous 'would be wider' assertion is gone. Source puts these gains below operating loss (refutation1); the operating subtotal is correctly still negative even without those gains (refutation2). Therefore retain ambiguous bridge wording as should-fix, not the earlier stronger claim of a newly wrong operating amount.

**BYND run0 going-concern statement:** risk says losses/negative cash flow raise substantial doubt without additional capital. Full primary and supplied excerpt contain no 'substantial doubt' or 'going concern' language, while F02030 supports12-month funding under the current plan. Refutation1: independent analytical concern may be legitimate, so this is not a fabricated auditor quotation. Refutation2: conditional liquidity risks do not establish a formal present substantial-doubt conclusion; the wording should distinguish the analysis from issuer disclosure. Retain as should-fix unsupported certainty, with severity judgment explicit.

**BYND both derivative liability change:**11.9M is the fair-value remeasurement gain, while39.152−26.137=13.015M total balance movement also includes conversions. Refutation1: source explicitly calls11.9M change in fair value, so that narrowly phrased reading is supportable. Refutation2: do not conflate it with the entire liability movement. Final wording is less explicit than first d's39.2→26.1 causal statement; no new material finding retained.

**COIN run1:**303.3M Adjusted EBITDA described as positive 'core operating cash generation'. Source's non-GAAP EBITDA bridge is not a cash-flow definition (refutation1), but actual182.7M OCF is positive elsewhere (refutation2). Thus the sign is not false; the measure conflation remains a narrow basis wording defect, not a fabricated cash amount.

## Improvements / refuted candidates

Both COIN repeats now correctly include current debt in long-term carrying debt7.2B and derive about3.0B net cash on that named scope. This fixes first-d run0's explicit5.94B-inclusive mistake, but does not establish a universal total-debt definition. COIN0 no longer treats lower transaction expense as causing the operating loss. BYND no longer calls current12.6M other income its year-over-year swing. MELI1 correctly describes financing inflow as funding, removing the first-d reversal. Genuine operating and per-share rows remain throughout.

Scorer rerun from the exact final payloads: COIN0 and MELI0/1 score1.0; COIN1 flags diluted EPS~30.5% versus720.8%, and BYND0/1 flag net loss~15.3% versus53.4%. Two refutations establish all three are proximity false positives: the prose percentages describe revenue; actual table/source arithmetic for EPS/loss is correct. No scorer or baseline change was made. Corrected helper projections, not the raw prose or aggregate scorer, are the evidence for signed numeric repair.

This is acceptance of bounded numeric/identity behavior with residual quality work, not world-class or unseen human acceptance. Preserve the new MELI coupon/principal failure in the next implementation controls.
