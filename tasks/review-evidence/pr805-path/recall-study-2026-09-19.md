# E4 — retained-artifact recall study, 2026-09-19

**Recommendation:** first improve candidate discovery for the measured `driven in part by` shape, then measure weak subject/metric matches as candidates rather than treating token overlap as verified attribution. Keep both production flags off. A blanket expansion of slots or deletion on lexical mismatch is not justified by these twelve attempts: several initially suspicious statements are explicitly supported by the retained source.

This is an offline, read-only study, not an implementation or a new model evaluation. No model calls, paid calls, application/test changes or pytest execution occurred. The analyses below are this reviewer's hand reads and pure-function replay. They are not recovered Fable rationales.

## Inputs and exact denominator

- Generation artifact: `eval_20260917T221422Z.json` from [run 35280067189](https://github.com/neilmac91/EarningsNerd/actions/runs/35280067189), SHA-256 `aec45283d49c32439513ccaae32b7061670a83ea92b261428c6b71b6ad13fe30`.
- Retained judge index: `tasks/review-evidence/pr805-path/fable-judge-per-attempt-2026-09-18.json`, SHA-256 `d0f0971694225334640b8adbb72f9b00779700e6d33e7833467a1cc2542c5dfa`.
- Use **only `runs.o3_fable`**, contract v2, `cli:claude-fable-5-1`. Join `(ticker, form, run)` to raw artifact `(ticker, filing_type, run)` and to `verify_audit[ticker|form|run]`. Run numbers are zero-based.
- Artifact harness: generation source `2bbb012ce9fa421a8eecd602c6075ad782db6805`, 35 filings ×2, DeepSeek Flash; attribution verification on and deletion off. This precedes the #912 evidence-ranking change.
- Define this cohort exactly as a judge attempt whose codes contain `G4` **and** whose `verify_audit.unverified` list is empty. There are **12**. There are **22** Fable-G4 attempts in all; ten have at least one flagged clause. Thus the known metric is **10/22 = 45.5% attempt-level overlap**. It is not clause recall: the index contains repeated G4 codes but not the offending quotations/reasons, and a surfaced clause may differ from the judge's defect.

| Attempt | Retained clauses checked / verified | Fable codes (including repeats) | Hand-read characterization |
|---|---:|---|---|
| AAPL / 10-K / 1 | 22 / 22 | G4, G4, G3 | Weak subject/scope acceptance; a later attribution in an enumeration escapes the extracted clause |
| ASML / 20-F / 1 | 12 / 12 | G4, G5, G5 | Unrecognized `as` ratio explanations; exact G4 remains uncertain |
| BABA / 20-F / 0 | 6 / 6 | G3, G4, G4 | Omitted red-flag surface exists, but the tested OCF attribution is explicitly stated; exact G4 unlocalized |
| BABA / 20-F / 1 | 7 / 7 | G3, G4, G5, G5 | Omitted FCF explanation and unrecognized headline `as`; exact G4 unlocalized |
| BRK.B / 10-K / 1 | 3 / 3 | G2, G2, G4, G5, G3 | Generic earnings/driver overlap accepts a consolidated causal bridge; `reflected`/`with` escape discovery |
| COIN / 10-Q / 0 | 5 / 5 | G4, G4, G4 | Accounting components presented as explanation; source-match acceptance can use non-GAAP definitions |
| MELI / 10-K / 0 | 13 / 13 | G4 | `driven in part by` is completely missed; component/total co-movement |
| MSFT / 10-K / 1 | 20 / 20 | G4 | Weak lexical evidence exists, but matched causal statements also have exact valid source support; exact G4 unlocalized |
| NVDA / 10-Q / 0 | 12 / 12 | G4 | Wrong-metric support: financing-cash-flow repurchases certify a diluted-share-count explanation |
| RIVN / 10-K / 0 | 7 / 7 | G4 | Component revenue increase promoted to consolidated driver; boilerplate passes subject test |
| WMT / 10-K / 0 | 15 / 15 | G4, G5 | Candidate scope-transfer allegation refuted by consolidated source; exact G4 unlocalized |
| XOM / 10-K / 0 | 6 / 6 | G5, G4, G3, G5 | Segment earnings promoted to consolidated driver; broad boilerplate passes lexical test |

Every retained audit has `decider: none`, empty `unverified` and empty `dropped`. No verifier could rescue discovery on these attempts because discovery sent it nothing. They are not cases with an empty source or zero checked clauses.

## Reproduction and limits

Read `attribution_gate.py` and replayed its pure slot/clause/source-index/verification functions against each final `raw_sections` and its retained `grounding_excerpt`. Application imports were omitted so the analysis did not initialize Settings, database connections or services. The only substituted entry guard was non-empty source normalization; every source is non-empty. The current replay returned zero candidates for all twelve. Checked counts match the retained audit except MELI (current final payload 11 versus retained audit 13). MELI's final earnings-quality section contains the structured reported-statement replacement rather than the earlier prose slot. Do not claim this final-payload replay is an exact reconstruction of that earlier pipeline stage or use it to overwrite the retained audit.

The compact Fable file explicitly stores only the first code of each failure string, not its offending text. The documented `/tmp/judged-verify-fable/judged.json` and `.md` files are absent; a narrowly checked known former workspace path also has no copy. No broad iCloud search was made. Raw generation rows have `judge: null`. Exact attribution of each G4 to a sentence is therefore unavailable. Statements below identify concrete candidate failures, refuted suspicions, or remaining uncertainty; they do not manufacture a judge reason or classify the judge as wrong.

Offsets below refer to character positions in that attempt's `grounding_excerpt`, not the original filing's pages. Source snippets are normalized for whitespace in this report. For lexical support examples, the reported window is one highest-coverage witness returned in source order; other witnesses may exist. It proves the algorithm can accept that witness, not that it is the unique intended evidence.

## Findings by attempt

### 1. AAPL / 10-K / run 1

`results_that_matter.table[0].commentary` is attached to **Total net sales**: “Management attributes the increase primarily to higher net sales of iPhone and Services across most reportable segments.” The supporting source at approximately 65,349 states that cause specifically for **Americas**. Europe names Services, iPhone and Mac; Japan names iPhone, Services and **iPad**; Rest of Asia Pacific names iPhone, Services and **Mac**. Source availability is not the problem.

The accepted driver token set is `{iphone, reportable, sales, segment, servic}`; the threshold is 0.5. A segment-definition window has four of those five tokens and the generic subject `sales`, producing **0.8 coverage** without certifying this consolidated movement. This is a concrete weakness in subject/driver ownership, not a missing connective.

A separate visible error occurs in `the_print.what_changed`, which groups “Japan and Rest of Asia Pacific” under higher iPhone/Services/**Mac** sales. Source at 65,908 explicitly gives Japan **iPad**, not Mac. `_clauses` extracts the initial Americas/Europe attribution only up to `, and`; the following Japan/Rest clause has “primarily to” without a fresh recognized attribution verb and is never checked as its own relationship. The segment's own Japan commentary correctly says iPad, so the initial suspicion that that segment row was defective was refuted. Proposed fixture must preserve this distinction.

**Next small target:** an attribution-list continuation case, plus a scoped metric/segment check. Do not replace broad `sales` overlap with another arbitrary token threshold and call that entity matching.

### 2. ASML / 20-F / run 1

Two table rows say “Operating margin expanded **as** income from operations grew 25.3% while total net sales grew 15.6%” and “Net margin expanded **as** net income grew 26.9% while total net sales grew 15.6%.” Neither yields a candidate because bare `as` is absent from `CONNECTIVE_RE`. The retained source provides financial statements and explicit gross-margin drivers near 12,927/26,211, but the targeted searches did not find those operating/net-margin explanation sentences.

The basic EPS explanation is **not** a miss: the source says the increase in basic net income per ordinary share was primarily driven by higher net income, and the algorithm's 1.0 match is appropriate for that statement. Forward-trend fields are omitted from `_slots`, but the quoted advanced-node/AI drivers resemble source forecasts; their omission alone is not evidence of unsupported content.

**Classification:** visible discovery gap for `as`, but only a provisional localization of this G4. A ratio's numerator/denominator explanation may be a transparent arithmetic relationship rather than a fabricated economic driver. Obtain the original Fable quotation before turning this case into an automatic deletion rule. If the product wants these explanations, a code-owned ratio explanation with a clear arithmetic basis is more precise than pretending it is a filing-stated driver.

### 3. BABA / 20-F / run 0

`earnings_quality.red_flags[0]` says OCF decreased 53% and the filing attributes it to investment in quick commerce and cloud infrastructure expenditure. This field is omitted from `_slots`, which initially suggests a surface omission.

That suspected defect is **refuted**. At approximately 192,832 the source explicitly states the same OCF amount, decrease and quick-commerce/cloud cause. Expanding slots would not validly count this as recovered unsupported attribution; hypothetical application of the current matcher accepts it at 1.0 coverage. The source's apparent economic oddity does not license changing its attribution.

The headline joins the operating-income decline to the sales/marketing increase with bare `as`, which is not discovered. Also, the earnings-quality narrative claims non-GAAP income still includes the entire CNY87,512M interest/investment line despite the source's explicit investment-gain exclusions. That latter issue involves accounting scope/inclusion and no recognized causal connective; the compact codes cannot tell whether Fable assigned it G3, G4 or another line.

**Classification:** actual omitted surface and unrecognized syntax, but exact G4 remains unlocalized. Keep the supported OCF sentence as a negative control in any later recall experiment. Do not report a recovered G4 from this row without the judge's quotation.

### 4. BABA / 20-F / run 1

The same bare-`as` headline is undiscovered. `earnings_quality.red_flags[1]` says negative FCF of CNY46,609M, versus positive CNY73,870M, is “reflecting capital expenditures of CNY126,063M.” The slot is omitted, so no check occurs.

The source near 193,000 explains **investing cash flow** using that capex figure. Its separate FCF definition near 51,200 excludes certain land/office-campus and acquisition items and adjusts buyer-protection deposits. A single capex amount is not a complete source-owned FCF explanation. Nonetheless the output can also be read as a partial description, and there is no retained Fable sentence-level rationale to settle that reading.

Counterfactual lexical replay of this omitted clause yields **2/3**, rounded audit coverage `0.67` but below the actual threshold `0.67` (unrounded 0.666…), because the synthetic token `cny` is absent from RMB-denominated source text. This would be a currency-token accident, not a robust semantic fix. Do not count it as proof that simply adding red flags solves recall.

**Classification:** promising omitted-surface/accounting-basis case, unconfirmed as the exact G4. Preserve both source definitions and consider it separately from automatic cause deletion.

### 5. BRK.B / 10-K / run 1

The headline attributes the consolidated net-earnings fall to lower investment gains and $8.3B impairments. The source at 70,275–71,172 presents an after-tax earnings decomposition. A top lexical witness combines general earnings volatility, a **2023** Pilot remeasurement gain and **2025** Kraft Heinz/Occidental impairments. It achieves **1.0 driver coverage** and matches subject token `earn`; this cannot establish that whole compound cause for the current consolidated movement.

`the_print.what_changed` and the net-earnings commentary repeat this relationship using **“reflected”**, which the regex does not recognize (`reflecting` is recognized). The sales/service row uses **“with”** to attach lower service/retailing and higher manufacturing revenues. The source's manufacturing/service/retailing table near 122,279 has total revenues $214.3B, a different scope from the consolidated sales-and-service line $199.5B. These are exactly the scope distinctions an overlap score cannot certify.

**Classification:** accepted compound relationship with weak subject/period grounding, plus lexical variants. Strong candidate for hand-labeled negatives under contract v2, which explicitly says component co-movement is not cause. Exact Fable sentence remains unknown.

### 6. COIN / 10-Q / run 0

The net-income row says net loss “reflecting the operating loss and $482.4M of losses on crypto assets held for investment,” followed by tax-benefit/other-income offsets. The source near 3,140 has the statement components; near 70,951 it states the crypto-loss line's own decline was due to fair-value remeasurement. A table's component relationship is not automatically a filing-stated explanation for the net-income swing.

The lexical matcher accepts the driver at **1.0** using a general Adjusted EBITDA exclusion-policy window: source tokens cover operating/loss/assets/crypto/investment and shared `income`/`loss` anchors. That definition is about why management excludes components from a non-GAAP measure, not why this quarter's net loss changed. The raw statement also includes $22.6M interest expense, showing why the narrative must not masquerade as a complete reconciliation.

The operating-income row has another unrecognized “as total operating expenses rose” sentence. There are three Fable G4 codes, but those counts do not identify these sentences, and this report does not assign all three.

**Classification:** clear semantic ownership weakness plus unrecognized connective. Proposed next measurement should distinguish a sourced accounting reconciliation from management attribution, and reject definition-only witnesses for current-period movement explanations.

### 7. MELI / 10-K / run 0

`the_print.key_takeaways[3]`: “Total assets grew 69.3% to $42.7B, **driven in part by** restricted cash and cash equivalents rising to $9.9B from $2.1B.” This recognized slot yields **zero clauses**. The regex permits `driven by` and a short list of intervening adverbs, but not `in part`.

The balance sheet near 160,000–161,200 supplies restricted cash 9,867/2,064 and total assets 42,667/25,196. The candidate has turned those co-moving balances into an explicit driver. Source searching around the cash/asset terms did not locate a corresponding causal statement; the figures alone are not sufficient under G4. This is the cleanest small candidate-discovery fixture in the cohort.

**Next small target:** include exactly measured `driven in part by`/equivalent bounded modifier handling in advisory discovery, preserving recognition of measure names. First counterfactually route it to verification and assess evidence; merely finding the phrase is not a proved correct drop. Retained 13-versus-final-replay-11 checked counts remain a pipeline-stage caveat, unrelated to this directly visible unmatched phrase.

### 8. MSFT / 10-K / run 1

The headline uses bare `as Microsoft Cloud revenue increased 23%`, so it is not checked as an explanation. Other accepted clauses expose weak witnesses: `higher impairments` can match accounting-estimate boilerplate with 1.0 coverage; `higher losses on equity derivatives` can match a derivatives accounting policy.

Those weak witnesses do **not** establish an actual unsupported statement. The source at 94,051/94,211 explicitly states both movements and causes, and at 94,323 says Other, net primarily reflects equity-method losses including OpenAI. The overall revenue sentence also has a direct source sequence describing consolidated growth and each segment's driver. The original suspicion that these were invented causes is refuted by a second source pass. Reading the component `Other, net` as the consolidated `Other income (expense), net` would be a scope risk, but the output preserves both names rather than unambiguously equating them.

**Classification:** exact G4 unlocalized. Bare `as` is a candidate discovery shape, not proof that this headline is what Fable rejected. Use these exact valid source causes as positive preservation controls when changing weak-anchor logic.

### 9. NVDA / 10-Q / run 0

The diluted-EPS commentary says weighted-average diluted shares fell to 24,391M from 24,611M, “reflecting share repurchases during the period.” The source EPS note near 11,576–11,677 gives basic shares, equity-award dilution and diluted shares. Separately, at approximately 70,667, the source attributes an increase in **cash used in financing activities** to higher share repurchases.

That financing-cash-flow passage certifies the diluted-share explanation in the current matcher: driver tokens `{repurchas, share}` both match, and the sole subject overlap is **`share`**. Coverage **1.0** therefore means “same words,” not “same financial movement.” The source may establish repurchases occurred, but the inspected statement does not state their effect on this particular weighted-average diluted-share change.

**Classification:** strongest concrete wrong-metric false-support witness. A future advisory rule should route this case to the verifier with the actual share-count passage and financing passage both visible, asking for the precise metric rather than accepting generic `share` overlap. Do not delete a mathematically plausible explanation solely from this lexical observation.

### 10. RIVN / 10-K / run 0

A takeaway says consolidated revenue increased, “driven by Software and services revenues of $1,557M versus $484M,” while Automotive declined. The source near 97,162 explicitly explains the **Software and services** increase using architecture/development, remarketing and repairs. It supplies component movements; a separate explicit consolidated causal assertion was not found in the inspected passages.

The consolidated-driver clause is accepted at **1.0** against a revenue-recognition policy about EV sales and over-the-air software updates, using only generic `revenu` as subject overlap. This is not current-period causal evidence.

The total-gross-profit row also uses a valid **Automotive gross profit losses** explanation from approximately 94,819. Since the sentence names Automotive, its component attribution is itself sourced; attaching it to a consolidated row risks misleading scope but should not cause the valid automotive clause to be called fabricated. The “resulting from”/“due in part to” automotive driver is also unrecognized in other slots, but source supports it. Preserve these as controls.

**Classification:** component-to-total causal promotion, with demonstrably unrelated lexical witness. Scope-aware measurement is more useful than a global threshold adjustment.

### 11. WMT / 10-K / run 0

Initial suspicion: the consolidated net-sales commentary borrows average-ticket/transaction drivers from Walmart U.S. The first matched passage at approximately 77,802 is indeed U.S.-specific. That allegation is **refuted** by the consolidated MD&A passage at approximately 92,352, which states the same average-ticket, transactions and unit-volume drivers after describing U.S. and international comparable sales.

Another suspicion: operating-margin pressure borrowed from operating-expense drivers. Source near 81,499 names liability claims, PhonePe and depreciation; the next operating-margin sentence at 82,094 explicitly connects the margin decrease to the factors above and membership income. This is not merely adjacent unrelated text. The PhonePe segment attribution similarly has a surrounding “as a result of factors discussed above” connection.

`earnings_quality.red_flags[0]` uses `driven in part by` and is outside `_slots`, but its claims-expense fact is sourced. This supplies another preservation control, not an unsupported-cause finding.

**Classification:** exact G4 unlocalized. Do not add a blanket component-scope rejection based on the first source hit; search the full retained excerpt before assigning a negative label.

### 12. XOM / 10-K / run 0

The consolidated net-income row states the decrease was “driven by lower Upstream earnings, partially offset by higher Energy Products earnings.” The retained filing separately supplies segment earnings/driver discussions and consolidated income. Searches for the consolidated bridge did not find this source statement; under the judge contract, a segment moving with the total is not automatically its stated cause.

The driver `{earn, upstream}` passes at **1.0** in a broad forward-looking-statements window, with generic company anchor `exxonmobil` sufficient for the subject test. That disclaimer does not explain the reported annual consolidated movement. `_clauses` stops before the offset; the Energy Products offset has no fresh recognized connective and is unchecked. The revenue and pretax rows also use `reflects`, another unrecognized form.

**Classification:** accepted component-to-total attribution plus omitted offset/verb forms. A bounded candidate experiment should retain complete driver/offset relationships and demand current subject/period support, without using boilerplate as proof.

## What the mechanics establish

1. **Discovery is narrower than its prose description.** `driven in part by`, `reflects`, `reflected`, bare `as`, and some “resulting from”/“due in part to” phrases do not match. This cohort contains both unsupported-looking and demonstrably sourced examples of those shapes. Discovery coverage and truth are distinct.
2. **Accepted lexical overlap bypasses the verifier.** `_verify` needs just one subject token anywhere in a three-piece window (with an additional previous piece for subject matching), any source causal marker, and driver coverage as low as 0.5. It discards numbers, periods and many movement/direction words. Weak subject matches include `share`, `earn`, `sales`, `revenu`, and a company name. A different metric, accounting policy or old-period passage can satisfy these conditions. Changing #912 evidence ranking cannot fix cases that never become candidates.
3. **Compound spans can be partly unchecked.** The clause ends at comma-and and offset boundaries. The continuation may have no connective of its own; the audit counts extracted clauses, not all semantic relationships. AAPL's Japan continuation and XOM's offset make this concrete.
4. **Omitted slots are real, but expansion is not demonstrated recall recovery.** `_slots` omits red flags, forward prose, risk summaries and footnote impacts; quotations/evidence and code-owned source blocks need intentional exemptions. The examined BABA OCF, WMT expense and NVDA tax-footnote examples have source support. Do not turn surface coverage into a claimed false-cause count.
5. **Raw causes and arithmetic explanations need separate treatment.** A statement reconciliation or ratio relation can be accurate without being management's stated economic driver. Contract v2 prohibits presenting mere co-movement as cause. A renderer may own explicitly labeled arithmetic explanations; the attribution verifier should not silently redefine that contract.

## Proposed next small steps, in order — no implementation here

**A. Preserve the offline cohort and label only observed statements.** Keep the exact twelve keys, retained audits and source offsets. Mark seven rows with concrete discovery/false-support candidates (AAPL, BRK.B, COIN, MELI, NVDA, RIVN, XOM), ASML as a provisional arithmetic/connective case, and BABA×2/MSFT/WMT as sentence-level localization unresolved. These are reviewer categories, not reconstructed Fable labels. Obtain the original judged.json from its known former owner/location when available; do not rerun another model and call it the same evidence.

**B. A bounded advisory discovery change for `driven in part by`.** Use MELI as the target and WMT's sourced claims-expense phrase as a preservation control. Measure candidate count and verifier evidence sufficiency on all retained 70 attempts before a paid fresh run. Do not claim better drop precision from more candidates. Keep the existing independent deletion authorization and production flags unchanged.

**C. Separately measure weak-match routing.** Prototype an offline audit classification for candidates accepted only through a different metric/scope or boilerplate source window, starting with NVDA share count versus financing cash flow. Compare it to explicitly supported same-metric positives from MSFT, BABA and WMT. The deliverable should be a reviewed list of extra verifier candidates and their evidence, not automatic lexical deletion. Raising thresholds alone will not fix NVDA/XOM because both currently score 1.0.

**D. Only then address clause continuation and omitted surfaces.** Add complete subject/driver/offset identities, not an unbounded bag of every string. Validate AAPL's named-segment list and XOM's offset separately. If slot coverage expands, include non-verbatim model-authored prose but preserve quote/evidence/code-owned fields. The existing 12-clause per-generation cap means broad expansion can displace useful candidates; record overflow and ordering and keep unknowns visible.

**E. Fresh acceptance remains future work.** Same judge/model/knobs; at least the required paired fresh runs under the repository's measurement policy; explicit clause-level hand labels and preservation rate. Report attempt-level overlap separately from clause-level precision/recall and cannot-judge counts. Do not arm either flag from this study. The offline study is complete; exact Fable sentence attribution and new-run improvement are not established.

## Related E3 context-loss finding — independent of this cohort's recall count

Inspection of `attribution_verify.build_prompt` confirms that the verifier sees a slot path plus the connective/driver clause, but not `Candidate.value` (the full summary sentence) or the metric/segment anchor supplied by `_slots`. `Candidate` does not retain that explicit anchor. The instruction nevertheless asks the model to decide the same line, measure and period. For a table path such as `table[4].commentary`, the row index does not identify a financial metric.

This is a concrete information-loss mechanism worth measuring in E3, not a proven explanation of Pfizer's wrong verdict. It cannot explain these twelve attempts' missing calls: all twelve bypassed verification entirely. It matters before routing additional weak matches to the verifier; sending more ambiguous clause fragments could increase wrong decisions. A later isolated E3 change should carry explicit claimed subject/metric and bounded sentence context, then preserve the same-line positive examples and different-line negatives. The module docstring also says three source passages while `_EVIDENCE_WINDOWS` is four after #912; correct that stale prose alongside any later E3 implementation, not as a separate test-bearing change.
