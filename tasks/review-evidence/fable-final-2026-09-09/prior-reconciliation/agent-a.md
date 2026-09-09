# Seven-case frozen comparison

Original frozen verdicts and scores remain unchanged. One new material omission is accepted: BYND Sonate exposure, shared by A/B. NVO remains provisional; TSM is pending. Source references below resolve within `outputs/fable-full-review/cases/{case_id}/`; full exact candidate paths, quotes, two refutation checks, coverage and input hashes are in `agent-a.json`.

| Case | Codex A / B | Fable A / B | Comparison |
|---|---|---|---|
| 03-NVDA | material / material | no material / no material | complete |
| 09-PFE | material / material | material / material | complete |
| 12-COST | no material / no material | no material / no material | complete |
| 15-PLTR | material / no material | no material / no material | complete |
| 18-BYND | material / material | material / material | complete |
| 21-TSM | no material / material | missing | pending |
| 24-NVO | material / material | material / material | provisional |

## 03-NVDA

Shared smaller issues: working-capital date, diluted-share direction, return-ratio basis, and growth rounding. Fable identifies synthetic/weak evidence phrasing. The S supplement contains no recovered passages, so absent S ranges do not create a substantive coverage gap. Annualizing a quarter mechanically does not establish a real annual return.

**NVDA-01 / NVDA-04 — severity difference.** Retain material: the broad $72.102B calculation is valid but the net-cash label omits lock-ups on $27.4B of equity. Management including equity among liquidity resources and B separating the asset classes do not disclose sale restrictions. Show $41.865B excluding equity separately. Sources: F00469-F00479; F01188; G00562-G00568.
Refutations: (1) The broad securities-minus-debt calculation is arithmetically valid: 50.335+30.237-8.470=72.102B. It is not a cash-equivalent balance. (2) Other representation separates equity from debt securities but never gives lock-ups. A uses the narrower 50.335-8.470=41.865B cash/debt-securities basis.
Action: Call $72.1B net cash and marketable investments, disclose $27.4B short-term lock-ups and equity risk, and separately show $41.9B excluding equities.

**NVDA-02 / NVDA-07 — severity difference.** Retain material: both rates are correct, but same-quarter YoY and sequential changes cannot establish acceleration. This appears in the lead performance interpretation, so presentation-only understates its consequence. Sources: F00985-F00994; G01247-G01263.
Refutations: (1) Source headers show 20% compares April with January, while 85% compares April with April; 20% is not previous YoY growth. (2) 81615/68127-1=19.8%; 81615/44062-1=85.23%. B avoids this specific invalid comparison.
Action: State revenue grew 85% YoY and 20% sequentially; remove accelerated from this comparison.

## 09-PFE

Shared smaller issues: disclosed credit facilities, share-count EPS direction, working-capital date, and return ratios. Codex also flags capex/shareholder-return wording and Sciwind payment scope. Fable’s patent-expiry and historical-growth questions remain unverified with supplied periods; do not turn them into factual contradictions.

**PFE-01 / PFE-05 — severity difference.** Retain material: correct pretax labels in supporting evidence do not repair operating labels in headline and tables. Other deductions include net interest; do not add interest a second time. Rename the measures rather than inventing an operating convention. Sources: F220–229; F573–590; G52; G608–640.
Refutations: (1) Source statement explicitly labels 3170/2785 pretax, not operating income; supporting quote in both candidates even preserves the correct label. (2) Other deductions 861/953 include net interest 554/511, equity losses 9/370, and pension credits; a company-specific operating convention is neither stated nor reconciled.
Action: Rename these rows pretax income from continuing operations and pretax margin; retain amounts and growth.

**PFE-02 / PFE-01 — agreement.** Both identify the reversed tax direction; B’s correct higher-tax statement elsewhere creates an internal contradiction rather than curing it. Sources: F602; F229–235; G652; G52–64.
Refutations: (1) 14.6 minus(-6.8)=+21.4 percentage points; tax 461 vsbenefit 189 corroborates direction. (2) B top what_changed correctly says higher tax, proving internal contradiction; neither GAAP nor adjusted tax basis produces the claimed benefit.
Action: Replace with tax headwind from higher rate, jurisdiction mix and absence of prior favorable resolutions.

**PFE-03 / no matching material finding — Codex-only material.** Retain material with a narrow qualification: the three-item bespoke pretax adjustment can improve, so this is not false arithmetic. Its unqualified core-performance conclusion omits company Adjusted income/EPS declines and A attributes improvement to restructuring after excluding it. Identify the chosen basis and show the company bridge. Sources: F1799–1827; F1662; F1325; G6625; G5478–5480.
Refutations: (1) Adding only listed 100/137/295 vs 678/9/8 to pretax produces 3702 vs 3480, so a narrow bespoke pretax measure can increase; do not call this arithmetic false. (2) But company Adjusted income falls 18.1%, EPS 18.5%; prior accrued-royalty credit remains in operating comparison, and restructuring cannot drive growth once excluded. Neither candidate labels its narrow measure or reports adjusted decline.
Action: Specify exact bespoke pretax basis if retained; include company adjusted income/EPS decline and prior royalty-credit comparator. Avoid unqualified core-improved claim.

**PFE-04 / PFE-02 — agreement.** Both identify the missing tax explanation in A. Real operating cost increases do not explain why net income fell while pretax income rose. Sources: F229–235; F602; G52–64; G652.
Refutations: (1) Costs did increase and are real headwinds, but pretax income rose 385m on displayed numbers. (2) Tax provision rose 650m; discontinued loss 13m and NCI changes reconcile remaining decline. No tax explanation elsewhere in A offsets this omission.
Action: Explain pretax improvement but higher effective tax due to jurisdiction mix and nonrecurrence of prior resolutions drove net-income decline.

## 12-COST

Same verdicts and all dimension scores. Shared minor issues concern working-capital date, margin drivers, growth rounding, return-ratio basis and debt scope. Fable additionally prioritizes omitted adjusted comparable-sales slowdown. Its objection to EPS slightly outpacing net income is overbroad: the diluted share count falls slightly and the arithmetic supports a tiny difference; avoid claiming a meaningful EPS advantage. No new material defect. The S supplement contains no recovered passages; there is no substantive recovery-coverage gap.

## 15-PLTR

Shared minor issues: working-capital date, return basis and capex misclassified as shareholder returns. Fable adds accurate metric values paired with gross-margin rather than operating-margin evidence. Increased diluted shares are real, but they offset rather than drive positive EPS growth; Fable’s refutation of the count itself does not refute Codex’s causal criticism. Net income attributable to shareholders versus consolidated income is a legitimate basis difference. The whole $68.2M other-income line is not established as realized gains alone.

**PLTR-01 / PLTR-02 — severity difference.** Retain material for A’s precise unsupported 71% historical benchmark and segment acceleration. The supplied 71% is geographic mix; current growth arithmetic is correct but supplies no prior growth rate. General acceleration in B remains unverified, not proven false. Sources: F664–672; G786–794; F778; F1029–1035; X1–45.
Refutations: (1) The relevant 71% source statistic is the prior-year United States share of total revenue; recalculation 628494/883855=71.1% confirms mix, not growth. (2) Income tables and retained X series contain Q 1 2026 and Q 1 2025 sales, establishing 84.7% current growth but not Q 1 2025 growth versus Q 1 2024. No independent historical rate is supplied; do not invent the true earlier rate or assert the general direction is false.
Action: Remove the unsupported 71% comparison and segment acceleration, retaining current consolidated and segment YoY growth.

## 18-BYND

Shared smaller issues: working-capital date, weak evidence, and historical first-positive-margin claim lacking prior quarters. “Restated” overstates the source’s immaterial corrections terminology. Carrying debt differs legitimately from principal. Fable over-credits B’s explanation of share growth solely through 2030 conversions; the dominant prior 2027 exchange remains omitted (F00926 vsF 01022). Sonate is the sole newly elevated material finding in this comparison; original frozen counts remain intact.

**18-BYND-01 / BYND-03 — severity difference.** Retain material: the expressly current-inclusive total omits $29.459M current debt. Correct components elsewhere do not cure the liquidity headline. Carrying versus principal differences are legitimate and are not this defect. Sources: F865–884; F968–989; G56–74; X552–595.
Refutations: (1) Tested legitimate carrying versus principal bases: $382.178M exactly equals long-term net 2030 Notes plus term loans; neither gross principal nor current-inclusive carrying debt. (2) Checked current classification and B’s risk/maturity sections: both identify $29.5M current 2027 Notes, so the omission is not a scope choice.
Action: Use $411.6M carrying debt excluding leases, or label $382.2M long-term debt and disclose current debt separately.

**18-BYND-02 / BYND-09 — severity difference.** Retain material for A only: below-operating gains cannot change GAAP operating loss. B’s statement that operating loss remains significant is not the same false counterfactual. Recurring remeasurement labelled one-time remains a separate minor qualification. Sources: F339–356; F1887–1897; G154–176; G1572–1574.
Refutations: (1) Checked statement order: derivative, warrant and debt-extinguishment gains all appear in Other income after operating loss. (2) Checked independent MD&A and adjusted EBITDA reconciliation F1942–1952/G1618–1657: these gains are removed alongside other nonoperating items, not added to GAAP operating loss.
Action: Say net loss excluding the three gains is about $47.7M; operating loss remains $41.1M.

**BYND-09 / BYND-02 — agreement.** Both retain material current-control omission. Management’s fair-presentation assurance mitigates any allegation of actual current misstatement, and curing filing-delivery default does not remediate inventory and complex-transaction controls. Sources: F02216–F02250; F02020; G01997–G01999.
Refutations: (1) F02218 says management believes current statements fairly presented and expects no adjustments. This prevents alleging current misstatement but does not negate the control weaknesses. (2) Both complete representations omit current weakness status; B’s cured default concerns late financial-statement delivery, not accounting controls. G ends before the control conclusion.
Action: Disclose ineffective controls and unremediated inventory/complex-transaction weaknesses, alongside management’s fair-presentation assurance.

**BYND-10 / no matching material finding — Codex material; Fable omission-only.** Retain material unavailable ATM access in the conditional liquidity discussion. Existing cash and possible alternative funding do not restore ATM eligibility; zero remaining facility availability is context, not a prediction of funding failure. Sources: F01968; F02016; F02030–F02050; G01681; G01770; G01803–G01804.
Refutations: (1) 191M unrestricted cash and management’s conditional twelve-month assessment are supported. This is not an imminent-insolvency finding or a claim that all equity financing is prohibited. (2) Source permits other potential financing but warns availability is uncertain; neither representation communicates lost ATM access. Fully drawn 100M principal and 81.7M net carrying value legitimately differ, so no separate unused-capacity error is alleged.
Action: State that Form S-3 ineligibility prevents ATM access and the facility has zero remaining availability; preserve conditional sufficiency and other possible financing options.

**New: Sonate / BYND-01 — Fable-only material; newly accepted.** Accept material omission with uncertainty preserved. This is a disclosure addition, not a finding of unrecorded loss or imminent cash failure. Sources: F00296; G00062; F01474–F01476.
Refutations: (1) Checked both representations: risk lists cover recurring losses/Nasdaq/debt or covenants, and footnotes cover historical errors, derivative remeasurement and conversions. Lower legal expenses in supporting evidence does not surface Sonate. This is the Sonate trademark jury verdict, not a class-action accrual or the separate settlement receivable. (2) The $38.9M is already accrued in 2025 and remains a current liability; do not expense it again inQ 12026, add it again to total liabilities, or assume immediate payment. Competing post-trial motions may reduce/eliminate or increase the award. Nevertheless it equals about 20.4% of $191M unrestricted cash amid losses, so the omission is material despite conditional twelve-month liquidity sufficiency.
Action: Add Sonate’s November 2025 verdict and $38.9M outstanding accrual, pending competing motions/appeal and uncertain ultimate cash timing. Do not net the separate $11M settlement receivable against it.

## 21-TSM

Fable absent. Codex’s B revenue-acceleration finding and minor maturity-bucket/return-basis/note-reference findings are carried forward as original findings only; no comparison verdict is issued.

**TSM-01 / no matching material finding — pending.** Fable report absent; no comparative adjudication or agreement inferred. Sources: G739–751; X1–43; F3376–3412.
Refutations: (1) The source comparison consistently uses annual TWD consolidated revenue for 2023–2025; this is not a quarter/YTD or USD-convenience comparison. (2) Recalculation gives 2024 growth 33.89% and 2025 growth 31.61%. Operating-income growth did accelerate from 43.5% to 46.4%; that does not validate the distinct revenue claim. Both representations repeat it, despite correct current growth elsewhere.
Action: Say revenue grew 31.6%, below 33.9% in 2024, while operating-profit growth accelerated and margins expanded.

## 24-NVO

Fable explicitly incomplete: targeted E exhibit reads leave extensive ranges unreviewed. All comparative conclusions remain provisional. Do not assume that unread exhibit financial statements are absent or unsupported. Conventional OCF-minus-PP&E FCF differs legitimately from company-defined historical FCF. Reported diabetes-care sales flat and CER growth can coexist.

**NVO-04 / NVO-03 — agreement.** Provisionally agree material. Company net debt excludes DKK 8.572B leases: 130.958-8.572-26.464-0.498=95.424B. Including leases gives 103.996B. Neither supports net cash; correct the incomplete arithmetic in Fable’s verification prose. Sources: E14726–14744; E17055–17088; F592/G175.
Refutations: (1) Borrowings total DKK 130.958 billion, including DKK 8.572 billion leases. Even excluding leases and subtracting cash DKK 26.464 billion plus securities DKK 0.498 billion gives net debt DKK 95.424 billion. (2) Including leases gives DKK 103.996 billion net debt; neither legitimate basis supports net cash. Management liquidity sufficiency is distinct from absence of debt.
Action: Report company-defined net debt DKK 95.4 billion, excluding leases, and net debt/EBITDA 0.64x; distinguish liquidity resources.

**NVO-06 / NVO-02 — agreement.** Provisionally agree material. DKK 8B restructuring and DKK 7.316B total impairments overlap and must not be added. No individually material IP impairment does not establish absence of aggregate or PP&E impairments. Sources: E1299–1302; E16837–16955; E13208–13216; E13374–13392.
Refutations: (1) Exhibit explicitly calls approximately DKK 8 billion restructuring one-off and says operating profit would grow 13% CER without it, versus 6% reported CER. Adjustment table separately lists DKK 8.014 billion and DKK 1.352 billion restructuring IP impairments; do not double count these. (2) Note 3.1 says no individually material IP impairment in 2025; that narrow statement does not establish no material aggregate or PP&E impairments. Restructuring PP&E impairment alone is DKK 2.370 billion, total PP&E impairment DKK 4.556 billion, and all impairment losses DKK 7.316 billion. The 2024 ocedurenone DKK 5.650 billion charge belongs to the comparator.
Action: Describe the DKK 8 billion headline restructuring charge, relevant impairments, prior-year impairment comparison, and adjusted earnings; retain the separate 2026 340B event.

**NVO-07 / NVO-01 — agreement.** Provisionally agree material. Adjusted sales and operating profit guidance is a decline of 5%–13% CER, not an entirely double-digit range. Preserve the reported/adjusted distinction and 340B special item. Sources: E1825–1862; E1944–1970; E1867–1930.
Refutations: (1) This is annual 2026 guidance, not a historical rate: outlook table labels adjusted sales and adjusted operating profit separately, each with -5% to -13%. (2) Non-adjusted midpoint guidance is -1% sales and +11% operating profit CER; USD 4.2 billion 340B recognition explains why reported and adjusted trajectories differ. Quantitative guidance is in the incorporated exhibit, not contradicted by limited generator excerpts.
Action: State both adjusted ranges and basis, DKK FX headwinds, plus capex around DKK 55 billion and FCF DKK 35–45 billion under the new OCF-minus-PP&E definition.

**NVO-01 / NVO-04 — severity difference.** Retain material currency ambiguity provisionally: DKK 4.2B(USD) conflicts with USD 4.2B source and other B sections. Parenthetical USD and correct repetitions elsewhere do not make DKK correct. The revenue-recognition direction issue remains a separate minor defect. Sources: F731; G317.
Refutations: (1) Both full 20-F and retained generator explicitly say USD 4.2b, with no DKK 4.2b conversion. (2) Other B sections correctly say USD 4.2b, demonstrating local inconsistency rather than alternative accounting basis; parenthetical USD does not make DKK correct.
Action: Replace DKK 4.2B(USD) with USD 4.2B.

## Scope and next action

Prioritize tax/operating labels (PFE), cash/debt scope and funding/control/legal exposure (NVDA/BYND/NVO), and unsupported growth comparisons (NVDA/PLTR/TSM original). Finish NVO exhibit review and obtain TSM Fable output before final comparison coverage sign-off. This comparison does not change frozen defect counts or imply missing reports passed.
