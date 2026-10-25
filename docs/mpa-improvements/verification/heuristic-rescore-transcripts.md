# Independent heuristic re-scores (report §4, verification §9b)

Three separate model instances (Opus, each a fresh subagent with no conversation context) each
evaluated one set of screenshots. None knew whether its set was the current page or a prototype.
Each got the image paths, the page's identity, Nielsen's ten heuristics and the severity scale.
Each was told to open nothing else. The prompt was identical apart from the image paths. It is
reproduced once below, then each report verbatim.

| Set | What it shows | Screenshots (desktop tiles cut from these full pages, phone tiles likewise) |
|---|---|---|
| X | the current page (production code, local REGN reproduction) | [`before-light-full.png`](../screens/before-light-full.png), [`before-dark-full.png`](../screens/before-dark-full.png), [`before-light-mobile.png`](../screens/before-light-mobile.png), [`before-dark-mobile.png`](../screens/before-dark-mobile.png) |
| Y | prototype round 1 (ringed review letter, fixed-size †, plain-words Data notes summary, notation key in the table header) | round-1 captures (superseded in `screens/` by round 2; same layout, earlier copy) |
| Z | prototype round 2 (round 1 plus: "not that the figure is wrong", the KPI word line, "automated checks") | [`after-light-full.png`](../screens/after-light-full.png), [`after-dark-full.png`](../screens/after-dark-full.png), [`after-light-mobile.png`](../screens/after-light-mobile.png), [`after-dark-mobile.png`](../screens/after-dark-mobile.png) |

**The prompt.**

> You are an independent usability evaluator. Evaluate one web page from screenshots ONLY. Use the
> Read tool on exactly the image files listed below and open nothing else (no other files, no code,
> no web). The page is the "Multi-Period Analysis" page of a paid SEC-filing research product,
> showing one company (Regeneron, ticker REGN) over fiscal years 2016–2025, in light and dark themes,
> on desktop (1440px wide, in three vertical tiles, top to bottom) and on a phone (390px wide, in four
> vertical tiles). `<image paths>` Method: Nielsen's 10 usability heuristics — H1 Visibility of system
> status; H2 Match between system and the real world; H3 User control and freedom; H4 Consistency and
> standards; H5 Error prevention; H6 Recognition rather than recall; H7 Flexibility and efficiency of
> use; H8 Aesthetic and minimalist design; H9 Help users recognize, diagnose, and recover from errors;
> H10 Help and documentation. Severity on Nielsen's scale: 0 = not a usability problem, 1 = cosmetic,
> 2 = minor, 3 = major, 4 = usability catastrophe. Judge for the product's real audience: retail and
> professional investors deciding how far to trust each figure. Output, and nothing else: 1. A
> findings table: ID | Heuristic | Where (section, theme/device) | Problem (one sentence, specific to
> what you see) | Severity 0–4. List every distinct problem you see with severity ≥1; do not pad. Pay
> particular attention to the small marks next to figures (symbols and letters), the "Data notes"
> line, the KPI cards, the charts, the AI analysis with its sources, and the metrics table. 2. Totals:
> number of findings at each severity 1, 2, 3, 4; the sum of severities; and the sum per heuristic
> H1–H10. 3. One line: the single most damaging problem. Keep it under 700 words.

## Set X — current page

| ID | Heuristic | Where | Problem | Sev |
|---|---|---|---|---|
| F1 | H6 | Marks a, b, † on KPI cards, charts, AI, table; all themes/devices | Meanings of "a", "b", "†" live only inside the collapsed "Data notes" disclosure; "Notes a" chips don't define them, forcing users to memorize codes | 3 |
| F2 | H9 | Data notes line; Balance sheet caption | "11 figures need review (a)" / "3 unavailable (b)" never say what's wrong, why, or what the user should do (rely on it? check the filing?) | 3 |
| F3 | H1 | Superscript "a" everywhere | Review flag is the smallest, faintest glyph on the page — smaller than the adjacent † — so flagged and clean figures look nearly identical | 2 |
| F4 | H2 | KPI cards, all | "FY2025 CAGR +12.8%" / "FY2025 Chg +13.0pp" read as FY2025 movement; actual FY2025 changes were +1.0% / +0.3pp and the base period is never stated | 3 |
| F5 | H2 | KPI cards and table | Large "†" glued to values ("$4.1B†", "31.4%†") can be misread as "+"/"more than"; 50 daggers add noise | 2 |
| F6 | H8 | Phone, both themes, Revenue KPI | Floating Feedback button overlaps "$1" of "$14.3B" (reads "4.3B") and isn't dismissable | 3 |
| F7 | H2 | Cash generation, Balance sheet, Revenue charts | Same-unit USD series split across dual scales (net income on right axis vs OCF/FCF; equity $31.3B meets cash $3.1B at the same point), so line crossings are meaningless; Revenue's 0% sits on the $4.5B gridline | 3 |
| F8 | H8 | Cash generation, Balance sheet | Right axis drawn on the '25 data column, colliding with final points; irregular tick steps ($7.1B/$6.0B, $8.1B/$5.0B) | 2 |
| F9 | H6 | Margins, Cash generation charts | Floating "a" letters above/below points plus hollow markers don't show which series they belong to and aren't explained in the legend | 2 |
| F10 | H8 | Charts, phone | X-axis years run together ("'16'17'18'19…"), hard to read | 2 |
| F11 | H6 | Chart cards | Image and expand buttons are icon-only with no labels | 1 |
| F12 | H5 | AI "Red flags" / "What to watch" | Narrative states "need review" figures as fact; the whole red flag rests on three flagged margins with no caveat | 3 |
| F13 | H10 | Sources [8]–[13] | Calculated (and flagged) figures have no link to inputs or method, despite the subtitle promising "calculation methods" | 3 |
| F14 | H4 | Sources | Two unexplained labels: "Calculated figure" vs "Calculated from recorded inputs" | 2 |
| F15 | H2 | Sources | Raw machine floats shown ("24.945443390109393%", "(0.1277642638015346 (growth fraction))†") | 2 |
| F16 | H8 | AI "Growth quality" | Repetitive, templated prose ("net income growth of +2.1%" three times in one paragraph) | 2 |
| F17 | H4 | AI "Red flags" | Citation line set in different size/color/indent from the rest of body text | 1 |
| F18 | H2 | Table — Investing/Financing CF | Percent changes on negative bases (−7,527.1%, −681.6%) shown instead of n/m | 2 |
| F19 | H4 | Table | n/m defined but cells show "–" unexplained; FY2020 debt change blank; "CAGR" column also holds pp values | 1 |
| F20 | H4 | Table, both themes | Inconsistent color judgments: rising liabilities and +0.1% debt red, while capex/cash-flow rows gray | 2 |
| F21 | H1 | Results area; "Cached" chip | No as-of/generated date for data or cached AI; no header tying results to the selected range | 2 |
| F22 | H1 | Table, phone | "All 10" selected and "Showing 10 of 10 years" while only FY2024–FY2025 are visible | 2 |
| F23 | H4 | Range controls | "Last 5"/"Last 10" look like plain text with no selected state | 1 |
| F24 | H8 | AI footer, page disclaimer, site footer | Near-identical disclaimers repeated three times | 1 |

> **Totals**: Severity 1 = 5, Severity 2 = 12, Severity 3 = 7, Severity 4 = 0 (24 findings). Sum of severities = 50. Per heuristic: H1 6 · H2 12 · H3 0 · H4 7 · H5 3 · H6 6 · H7 0 · H8 10 · H9 3 · H10 3.
>
> **Most damaging**: The "a" review flag — on 11 figures including two headline KPIs and every number in the AI's Red flags — is undefined at point of use, so investors can't judge how far to trust the most important numbers.

## Set Y — prototype round 1

| ID | Heuristic | Where | Problem | Sev |
|---|---|---|---|---|
| F1 | H9 | Data notes, KPI cards, table, sources (all) | The circled ⓐ "needs a source check" never says what was checked, what failed, whether the value may be wrong, or how to verify; flagged values have no filing link and only a small "Details" link, yet it covers 2 of 4 headline KPIs | 3 |
| F2 | H5 | AI analysis: Margins, Red flags, Watch next (all) | Headline conclusions (5.9pp margin compression, FCF below net income) rest entirely on ⓐ-flagged figures but the prose states them flatly with no caveat | 3 |
| F3 | H4 | Data notes (all) | "11 need a source check" and "186 of 200 passed" while 27 ⓐ marks appear on the page; 16 flagged growth figures are counted as "passed" | 2 |
| F4 | H6 | Marks site-wide | Arbitrary letters (a = needs check, b = not in our data) and stacked †/ⓐ/ᵇ on single values; legends appear only in Data notes and the table header, so chart, KPI and AI readers must remember them | 2 |
| F5 | H4 | Margins and Cash generation charts (all) | Flagged points use a plain floating "a" (not ⓐ) plus hollow markers absent from the legend; labels sit between lines so the flagged series is ambiguous; amber warning color matches amber data series | 2 |
| F6 | H2 | Cash generation chart (all) | Net income on its own right axis ($0–8.1B) though same unit as FCF/OCF ($0–7.1B), so FY2025 FCF ($4.1B) plots above net income ($4.5B), contradicting the AI text | 3 |
| F7 | H2 | KPI cards (all) | "FY2025 CAGR +12.8%" / "FY2025 Chg +13.0pp" omit the base period (FY2016–FY2025), reading as one-year figures | 2 |
| F8 | H8 | KPI cards, phone (both themes) | Floating Feedback button covers the Revenue KPI ("4.3B", "25 CAGR") | 3 |
| F9 | H8 | All charts, phone | X-axis year labels run together ("'16'17'18'19…") with no spacing | 2 |
| F10 | H1 | Metrics table, phone | "All 10" selected and "Showing 10 of 10 years" but only FY2024–FY2025 visible; the only cue is a small "← Earlier years" | 2 |
| F11 | H2 | Metrics table (all) | Percent changes on negative/near-zero bases (Investing CF −7,527.1%, Financing −681.6%, +96.5%) shown instead of n/m; direction semantics ambiguous | 2 |
| F12 | H10 | Metrics table, last column | "—" in four rows unexplained; the note defines n/m, which never appears | 2 |
| F13 | H4 | Metrics table (all) | Green/red encodes good/bad inconsistently (Current liabilities rise shown red; Capex/Investing/Financing gray) with no legend | 2 |
| F14 | H4 | Metrics table header | "FY2016–FY2025 CAGR" header sits over percentage-point changes (−2.4pp, +13.0pp) | 1 |
| F15 | H8 | Metrics table (all) | Appended †ⓐ break right-alignment ($14.7B†ⓐ) and on phone wrap ⓐ onto its own line | 1 |
| F16 | H2 | Sources list (all) | Raw machine precision ("24.945443390109393%", "0.1277642638015346 (growth fraction)") | 2 |
| F17 | H10 | Sources list (all) | Calculated entries say only "Calculated figure" / "Calculated from recorded inputs" (difference unexplained) with no formula or inputs, despite promising "calculation methods" | 2 |
| F18 | H8 | AI analysis (all) | Repetitive, formulaic prose (net income vs revenue growth stated twice; "above 1.00×"; "Watch…" lines restate the table) | 2 |
| F19 | H4 | AI Red flags (all) | "Compressed 5.9pp" but displayed values 30.9% → 24.9% differ by 6.0pp | 2 |
| F20 | H6 | Results area (all) | No heading names company/period for the results; after scrolling, KPIs, charts and table no longer identify REGN FY2016–2025 | 1 |
| F21 | H4 | Selector (all) | "Last 5" / "Last 10" look like plain text; the active preset (Last 10) isn't highlighted | 1 |
| F22 | H8 | Charts (all) | Axis title clipped ("Fiscal vear"); ticks mix units and uneven steps ($800.0M next to $1.6B; $7.1B over $6.0B) | 1 |
| F23 | H4 | Nav vs title | "Multi-period analysis" vs "Multi-Period Analysis" capitalization | 1 |
| F24 | H1 | AI header (all) | "Cached · served from an earlier run" gives no generation date | 1 |
| F25 | H2 | Revenue & growth chart | Growth-axis zero not aligned with bar zero; the line dips into bars | 1 |
| F26 | H4 | AI Red flags evidence line (both themes) | Evidence line uses different size, color and indent from body text | 1 |
| F27 | H4 | KPI cards, phone | FCF and Net margin cards split "FY2025" and "CAGR" onto two lines, unlike the others | 1 |

> **Totals**: Findings by severity: 1 = 10, 2 = 13, 3 = 4, 4 = 0 (27 findings). Sum of severities: **48**. Sum by heuristic: H1 3 · H2 10 · H3 0 · H4 13 · H5 3 · H6 3 · H7 0 · H8 9 · H9 3 · H10 4.
>
> **Most damaging**: The ⓐ "needs a source check" mark sits on 27 figures — including two headline KPIs and every figure behind the AI's red flag — without ever saying what failed or how to verify it, leaving investors unable to decide how far to trust the numbers.

## Set Z — prototype round 2

| ID | Heuristic | Where | Problem | Sev |
|---|---|---|---|---|
| F1 | H6 | Marks — table/AI/KPI, all | Trust status rides on ⓐ (resembles "@"), superscript b and †, whose meaning must be recalled from legends in Data notes/table header | 2 |
| F2 | H4 | Charts, AI header, all | One "needs check" status is drawn four ways — circled ⓐ, loose lowercase "a" near chart points (ambiguous which line), hollow markers absent from legend, cryptic "Notes a/b" pills; amber used both for warnings and for series lines | 2 |
| F3 | H9 | Data notes, table, all | Only derived figures are flagged (FCF $4.1B flagged while OCF $5.0B and capex $898.4M pass) and the page never says what failed or what to check | 3 |
| F4 | H10 | AI sources, all | Flagged sources [8]–[11],[13] have no filing link or listed inputs, so the user cannot do the "source check" the page asks for | 3 |
| F5 | H4 | Data notes, all | Counts don't reconcile: "50 calculated" overlaps the 186/11/3 split (four numbers totalling 250) and the table shows 27 ⓐ versus the headline "11" | 2 |
| F6 | H5 | Table FY2018, Revenue chart, all | FY2018 revenue $5.1B (−12.4%, 49.3% op margin) carries no flag though Regeneron reported ≈$6.7B; the likely error also distorts FY2019 growth (+27.4%) and the YoY line | 3 |
| F7 | H2 | Cash generation & Balance sheet charts, all | Same-unit series on separate axes: FY2021 net income ($8.1B) plots level with OCF ($7.1B) and FY2025 FCF plots above net income, contradicting the AI's "FCF below net income" | 3 |
| F8 | H2 | Table cash-flow rows, all | Percent changes on negative bases (−7,527.1%, −681.6%, −45.5% for a larger outflow) shown instead of the defined "n/m"; "–" in the CAGR column unexplained | 2 |
| F9 | H2 | KPI cards, all | "CAGR +12.8%" / "Chg +13.0pp" don't state their period; KPI CAGR lacks the † the table gives the same figure | 2 |
| F10 | H4 | AI Red flags; table CAGR column, all | Rounded figures visibly don't add up ("compressed 5.9pp" for 30.9→24.9; −2.4pp for 27.4%→24.9%); rounding note appears only above the table | 2 |
| F11 | H8 | AI analysis, all | Templated, repetitive prose (net income growth +2.1% stated three times; "above 1.00×"); little insight; Red-flags evidence line in different type | 2 |
| F12 | H8 | AI sources, all | Raw floats ("24.945443390109393%", "0.1277642638015346 (growth fraction)") add noise and wrap badly on phone | 2 |
| F13 | H4 | Table deltas, all | Red/green means unfavourable/favourable not up/down (debt +0.1% red, capex grey) with no legend | 2 |
| F14 | H1 | Metrics by period, phone | "All 10" selected and "Showing 10 of 10 years" but only FY2024–FY2025 columns visible | 2 |
| F15 | H5 | KPI cards, phone (both themes) | Floating Feedback button covers the Revenue card ("$14.3B" reads "4.3B") | 2 |
| F16 | H1 | AI header, all | "Cached · Served from an earlier run" with no date; no filing or data as-of date anywhere on the page | 2 |
| F17 | H8 | Charts, phone | X-axis year labels run together ('16'17'18…); "a" marks collide with data points | 2 |
| F18 | H8 | Chart axes, all | Irregular top ticks ($6.0B/$7.1B crowding; $8.1B; $31.3B) and "$0.00" cents labels on billion-dollar scales | 1 |
| F19 | H1 | Picker / nav, all | "Last 5"/"Last 10" look like plain text with no selected state; current nav item not highlighted | 1 |
| F20 | H3 | Picker, all | Selected company sits under an empty search box with no way to clear it | 1 |
| F21 | H4 | AI sources & prose, all | "Calculated figure" vs "Calculated from recorded inputs" unexplained; prose omits † on calculated growth figures | 1 |
| F22 | H8 | Table, phone | Marks crowd cells ("24.9%†ⓐ-2.4pp†ⓐ") and the Net margin CAGR's ⓐ wraps onto its own line | 1 |

> Light and dark themes behave identically; no theme-specific defects observed.
>
> **Totals**: Severity 1 = 5, Severity 2 = 13, Severity 3 = 4, Severity 4 = 0 (22 findings). Sum of severities: **43**. Per heuristic: H1 5 · H2 7 · H3 1 · H4 9 · H5 5 · H6 2 · H7 0 · H8 8 · H9 3 · H10 3.
>
> **Most damaging**: F6 — a likely wrong figure (FY2018 revenue $5.1B vs Regeneron's reported ≈$6.7B — from my own knowledge, not the screenshots) carries no flag and counts as "passed automated checks", while figures with clean inputs are flagged with no reason or source path, inverting the trust signals.

**Checking Z-F6.** The evaluator's figure came from its own memory, so it was verified against
SEC's XBRL API (`data.sec.gov/api/xbrl/companyconcept/CIK0000872589/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json`).
The FY2018 10-K (`0001532176-19-000009`) and FY2019 10-K (`0001532176-20-000008`) report calendar
2018 at $6,710.8M. The FY2020 10-K (`0001804220-21-000008`) reports the same tag and period at
$5,145.6M, and calendar 2019 at $6,557.6M against $7,863.4M. The dataset takes the newest filing's
comparative, so it shows $5,145.6M for FY2018. The claim is confirmed. The report treats it as an
upstream finding (§1.6).
