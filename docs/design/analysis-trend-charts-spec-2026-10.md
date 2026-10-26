# SPEC: the four Multi-Period Analysis trend charts (final contract)

`$S` names the working directory of the 24 October 2026 chart audit. It stays outside this repository; the `$S`
paths below record where each number came from, and the audit's published report (“report §n”,
<https://claude.ai/artifact/62qsH9r3W3rJn7o1L3LJw6>) carries the measurements. §0.5 says what of this spec is in
the repository and where the repository's engine departs from it.

**Status.** Final. The founder approved the migration plan built on it (report §10) on 2026-10-24. This is `$S/design/SPEC-draft.md` with the reconciliation decisions of §0.4 applied everywhere
they touch. Where the draft and the verified prototype differ, this spec states the prototype's behaviour unless
§0.4 says otherwise.

**Provenance.**

- **Spine: proposal A (perception).** Highest combined judge score: data judge 48/60, product judge 45/60,
  total 93. C scored 47 + 45 = 92 and B 41 + 38 = 79.
- **Grafts:** the per-section winners the two judges named (`design/judge-data.md` §3 and §5,
  `design/judge-product.md` §2, §3 and §5).
- **Fixes:** every defect the judges listed is either fixed or marked "rule not adopted" (§5.3).
- **Disagreements:** where the judges disagree, the decision and a one-line reason are in §0.2.
- **Reconciliation:** §0.4. The prototype in `$S/proto-app/features/chart-proto/` implements this spec: the spec
  engine (`spec/scale.ts`, `spec/model.ts`, `spec/layout.ts`, `spec/theme.ts`, `spec/marks.tsx`), a reference
  renderer, the HTML card (`ProtoCard.tsx`) and the export (`exportSvg.ts`). It was verified on the gallery (150
  pages: 73 datasets plus REGNPN in both themes; 600 cards, of which 566 render a chart and 34 are not-applicable)
  with 0 failures, and by a blind readout.

**Numbers.** "Brief" means `$S/BRIEF.md` and `$S/stats_summary.txt`. "Sim" means the reference implementation of the
draft's rules, `$S/design/merged/sim.py`, run over all 73 datasets plus REGNPN for the notes band:

- output in `$S/design/merged/sim_out.txt`;
- legend fit in `$S/design/merged/legend.py` and `legend_out.txt`;
- contrast from `$S/apca.py` (APCA 0.0.98G-4g) and WCAG 2, final values in `$S/apca_table.txt`;
- colour-vision ΔE76 from `$S/design/c_robust/cvd.py` (Machado 2009);
- glyph coverage from `$S/design/c_robust/font/cmap.mjs` against the built Geist Mono WOFF2 files.

"Gallery" means the verified prototype run: `$S/gallery_spec/` (one PNG per card, `checks.json`) and
`$S/model_checks.json` (550 chart renders, 7,722 same-panel order pairs, 0 failures). "Readout" means the blind
readout in `$S/readout/`, scored by `$S/score_tiers.py`. "Report §n" means a section of the verification report built
by `$S/report/build_report.py`; §9 is the independent verification. Sim counts are kept wherever the rule they
measure is unchanged.

**Notation.** Vega-Lite v5 JSON with `//` comments.

- `«m.x»` is a value supplied by the pure planner `buildChartModel(dataset, chart, view, theme, width)` (§4.0).
- `«t.x»` is a theme token (§3.8).
- Anything Vega-Lite cannot express is an explicit algorithm, numbered A1–A13 plus A1b, A3b and A13b (§4.5).
- The renderer draws model values only. It never computes a domain, a tick, a label, a position or a colour.

---

## 0. Summary of decisions

### 0.1 Decisions

| # | Decision | Deciding numbers | From |
|---|---|---|---|
| D1 | **No dual axes anywhere.** One y-scale per panel. No right axis, spine, tick mark or axis tag. | Today's dual axes misorder 29% of Cash pairs (68/72 datasets) and 28% of Balance pairs (64/73), with 165 + 154 drawn crossings that do not exist. REGN FY2025 draws FCF $4.08B *above* NI $4.50B. Prototype: 7,722 same-panel order pairs drawn in the true order. | all three |
| D2 | **Revenue & growth: two aligned panels sharing x.** Panel A: top-line bars from $0, each labelled with its value. Panel B: YoY growth as diverging bars around a drawn 0% rule, each labelled with its signed value at the bar end. Missing or structural growth prints "—" and n/m prints "n/m" on the 0% rule. There is no separate YoY row. | Growth is negative in 41/65 datasets, and today 0% floats mid-plot. Growth direction is printed for 562/562 valued periods, with no exemption. 0 text collisions in 566 rendered cards. Blind readout: growth sign 100%, growth within ±1 pp 100%, printed values transcribed exactly 100% (report §9). | A panels, A labels (§0.4 #1) |
| D3 | **Margins: one % axis**, lines with a marker on every point. | >10× between margin series in only 2/59 datasets (LCID, RIVN), both caused by outliers. | A |
| D4 | **Cash generation: one $ axis** for OCF, FCF and NI. | If all three shared one axis, >10× would occur in 1/73 datasets (JPM/q, 11.9×). OCF/NI median 1.5×, FCF/NI median 1.3×. | all three |
| D5 | **Balance sheet: two aligned panels, 60/40 of the plot height.** Panel A: long-term debt and cash, lines on one $ axis. Panel B: equity as bars from $0. A bar shorter than 2 px is drawn as a 2 px stub anchored at the zero rule on its value's side (A13) and prints its value (A13b). | On one axis, 30/73 datasets (41%) have >10×: cash vs equity 19/73, debt vs equity 12/58. Debt vs cash is >10× in only 10/58. Equity is negative in 16/73. 11 equity points in 7 datasets are under 2 px and print their value. | A, split from C (§0.4 #6, #17) |
| D6 | **Clipping only on percent panels, with A's two-condition outlier rule (A3).** Clipped values are always printed: margins in the off-scale band at the plot edge (A3b), growth on the bar label. $ panels never clip. | Margins: 11 points clipped in 3/59 datasets. Growth: 6 points in 4/70. All annual (sim S4). Model checks: 34 off-scale points across both views, every one printed. No PLUG, BYND or RIVN FY2022 margin is clipped. | A (§0.4 #3) |
| D7 | **No log scale, no symlog, no indexing, no broken $ axis.** | Negatives: growth 41/65, operating margin 22/59, FCF 28/73, NI 24/73, equity 16/73. LTD is exactly 0 at 14 points in 11 datasets. Owner rule "audit D2" (no indexing). | all three |
| D8 | **Ticks from A1: a fixed interval cap per panel, the densest legal grid, and A1b for small crossings.** Ticks are view-independent: card, expanded and export show identical ticks. Unit from max\|tick\|. Zero is always a tick, printed "$0" or "0%". U+2212 minus. | Caps: Revenue 5, growth 4, margins 8, cash 8, debt and cash 6, equity 4. Model checks: 0 non-uniform, 0 mixed-unit, 0 wrong-zero and 0 over-cap axes in 550 renders (report §9). A1b fires in 6 of 290 panels. Gridlines ≥ h/cap apart: ≥ 17 px in every panel (§3.1). | C grid, A view independence (§0.4 #5) |
| D9 | **Notes leave the plot.** They go into one **always-reserved 16 px union band** under the period axis (under the strip in expanded) and into footnote lines. † appears only as a band glyph, at periods where a partly calculated series was calculated. A fully calculated series gets a footnote sentence and no symbol. *2026-10-25: the band's marks follow the approved quiet scheme (§3.3's note; `docs/mpa-improvements/coherence.md` §2.6, D-061): no † glyph, and a letter only for a note that questions the number.* | ≤ 1 letter per cell in 73 datasets + REGNPN. ≤ 2 glyphs per cell ("a †") (sim S9). The user flagged a large † beside a KPI value as confusing. | B band, C glyphs (§0.4 #4, #7) |
| D10 | **Printed values where position cannot meet the task:** top-line and growth bar labels; near-zero equity labels (A13b); off-scale values at the plot edge (A3b); the latest value of every series in the legend; and in expanded, a **value strip** with every margin, cash and balance value. | Margins ±1 pp: met by the expanded strip in 59/59 datasets (sim S5). The card's position tolerance per dataset is measured in the report §9. | A (§0.4 #1, #3, #6) |
| D11 | **Tolerance `T = max(step/8, 4 px·span/h)`.** Order questions are scored wherever the true gap > T. T is frozen per dataset from this spec's geometry and applied unchanged to current and proposed renders. Tier P is exact transcription of the printed strings. | REGN FY2025 FCF < NI (gap $0.42B, T $0.25B) is in scope on the card. The count of out-of-scope pairs is measured in the report §9. | B formula, product-judge freeze (§0.4 #13) |
| D12 | **Series colours chart-1..k in order over the *present* series** (DS §10: "never skipped"), plus marker shape by the same index (circle, square, triangle). | Two-series charts (21 margins, 12 cash, 15 balance datasets) get teal + honey, never the weakest CVD pair (teal–cornflower, deutan ΔE 31 dark / 37 light). | C + A shapes (§0.4 #9) |
| D13 | **Fixed geometry.** Card SVG 320 px tall in every chart. Expanded SVG 520 + strip. Height never depends on width. Minimum slot 36 px in both views (a labelled chart up to 42 px, §3.7 A7); below it the SVG scrolls inside its card. | All cards in a grid row align: 566/566 rendered cards are 320 px tall, and not-applicable cards keep 320 px. 0 sideways page scroll in the 390 px phone run (report §9). | A height, B reserved band (§0.4 #11, #16) |
| D14 | **Export serialises the on-screen SVG node** at fixed 2×, with both Geist Mono subsets embedded, each keeping its `unicode-range`. | † (U+2020) exists only in the latin-ext subset. U+2009, ▲ and ▼ exist in no subset (cmap). Export differs from the screen on 0.000% of pixels; today's method on 1.39–2.37% (report §9). The header/footer composition is specified, not yet verified. | C (§0.4 #14) |
| D15 | **FY-end caption from the latest FY or fiscal-Q4 row, with day ≤ 7 rolled back** to the previous month. | 0 wrong in 72/72 datasets that have such a row: CPRT Jul, LOVE Jan, SBUX Sep, NVDA Jan, DECK Mar, MSFT Jun, AAPL Sep, CLFD Sep, 56 Dec. XOM/q has none, so the segment is omitted (sim S11). | B rule, product-judge fix (§0.4 #12) |
| D16 | **Top-line fallback `revenue → net_interest_income → premiums_earned`.** Reason-specific not-applicable copy. | 70/73 top-line charts (today 65/73): 59 revenue, 6 NII, 5 premiums. Margins not applicable 14/73: 6 NII, 5 premiums, 3 with no top line. | all three |
| D17 | **Growth state taxonomy:** value, structural, n/m, unavailable. Every non-value prints "—" or "n/m" on the 0% rule; nothing is left blank. | Of 754 growth slots: 562 value, 162 structural, 28 unavailable, 2 n/m (RIVN FY2020–21, zero base) (sim S12; the model checks count the same 2 n/m). | B taxonomy + A/C "—" (§0.4 #12) |

### 0.2 Judge disagreements and the decision taken (one line each)

| Topic | Data judge | Product judge | Decision and why |
|---|---|---|---|
| Revenue & growth | A: two panels, every growth bar labelled | C: printed YoY row, no growth graphic | **A's labelled bars, no row.** The draft kept both; the prototype showed the labels meet the product judge's requirements on their own: collision-free (A4 planner, 0 collisions in 566 cards), exact (100% transcription in the blind readout) and never hidden by clipping (a clipped bar's label prints the true value). The row stays a documented fallback (§0.4 #1). |
| Equity mark | A: bars | C: line, because near-zero bars vanish | **Bars with a 2 px minimum anchored at the zero rule on the value's side, plus a printed value under 2 px (A13, A13b).** A different mark type is the only proposed mitigation for cross-panel misreading. The vanishing-bar defect (11 points in 7 datasets) is fixed by the stub, and the printed value carries sign and size where the stub cannot. |
| Notes band | B: one union row, always reserved | C: one row per series, reserved per grid row | **B's union row.** Measured ≤ 1 letter per cell. Fixed 16 px keeps each card independent of its neighbours; C's per-grid-row reservation couples cards and puts empty rows into a single-card export. DS §10's value-vs-YoY independence is kept in the footnote lines, which list value and YoY comparison references separately, and in tooltip rows (specified, not yet verified). |
| Colour assignment | B: fixed slots | C: in order over present series | **C (in order).** It is DS-compliant ("never skipped", and already today's behaviour, see `$S/gallery_regnpn`). It puts every two-series chart on teal–honey instead of teal–cornflower. Cross-company colour stability is listed as an owner option (§0.3). |
| Cash generation | B "by a hair" (tolerance) | A (spec), with B's threshold | **A's spec with B's threshold.** The marks are identical in all three proposals. The difference was only the order threshold, which both judges graft from B. |
| End labels vs legend values | B legend; borrow A's "latest value (period)" | A's HTML legend with latest values | **No end labels.** Latest values go in an inline HTML legend (swatch, name, value) that wraps by whole items. The plot keeps its full width. |
| Legend medium | B: in SVG, Geist Mono | A: HTML, DS type roles | **HTML (DS roles).** Export fidelity for the legend depends on the export composition drawing the same model strings at the same width (E2, E6), which is specified, not yet verified. |
| Tick density by view | A's view-independent ticks, if export-from-card matters | C's height-derived cap | **A's view-independent ticks, on C's grid.** Fixed caps per panel make card, expanded and export identical, so no rule about which view an export came from is needed (§0.4 #5). |
| String identity with the table | B7 is a defect: table strings use hyphen-minus and "$0.00" | Adopt B's I8: chart strings = table strings | **One chart formatter** (U+2212, "$0", one decimal tier per panel) plus **numeric agreement** with the table at the table's precision (check M15). Byte identity follows once `lib/format.ts` adopts U+2212 and "$0", which is out of chart scope. |
| Layout heights | B: fixed 256 px, reserved band | A: fixed 320 px, plot flexes when the band appears | **320 px with an always-reserved band**, so nothing flexes with the notes. B's 256 px would shrink the plot below today's 224 px. |
| SSR | A: server renders at reference widths | B: model at the default width, ResizeObserver re-run, plus C's D9 | **B + D9.** Heights are width-independent, so only x-dependent planning moves after hydration. |

### 0.3 Owner sign-offs this spec requires

1. **Bar value labels return, on both Revenue & growth panels.** This reverses the "labels removed after the AAPL
   field test" decision. They are collision-free by construction: the A4 planner tests every label box in 2-D
   against [0, W] and a 2 px gap, and the gallery measured 0 text collisions in 566 rendered cards. AAPL must be
   re-field-tested. If the field test finds crowding, the fallback is the draft's printed YoY row (§0.4 #1).
2. **Percent-panel clipping** departs from "every pixel is a citable value" for 11 margin and 6 growth points.
   Every clipped value is printed: margins at the plot edge, growth on the bar label.
3. **Dark-theme tokens.** New dark series hexes, dark tick ink, dark review ink, and new grid tokens. This changes
   DS §1's "same hexes in both themes". In chart scope, the card's dark HTML subtitle, legend names and footnotes
   use `chart.label.dark #B8BEC7` instead of DS `text.secondary.dark`.
4. **Card SVG height** goes from 224 px plus axis to 320 px.
5. **Column-wash hover on line charts** (specified, not yet verified). This replaces DS §10's crosshair for line
   charts, so one cursor spans both panels and the band.
6. **Colour stability across companies.** In-order colours mean operating margin is teal for REGN (which has no gross
   margin) and honey for AAPL. Fixed slots remain available as an option, at the cost of a DS change and the
   teal–cornflower pair for banks.
7. **Product questions (no chart rule changes):**
   - bank operating cash flow (JPM/q OCF −$252B…+$148B against NI $13–21B);
   - backend YoY for the first window period(s) (162 structural nulls);
   - `nm` for zero-base growth.

### 0.4 Reconciliation with the verified prototype

The draft was built as a prototype and verified: the gallery (600 cards, 0 failures), the model checks (550 renders,
0 failures), the hard-case renders in both views and the blind readout. Rows 1–15 are the final reconciliation
decisions. Rows 16–28 record smaller differences where this spec now follows the verified code. Where a draft
number no longer applies, the rule is given and the number is measured in the report §9.

| topic | draft | final | why/evidence |
|---|---|---|---|
| 1. Growth magnitude | A printed, signed YoY row (16 px) under panel B: F0 on the card, F1 in expanded. Growth bars unlabelled. | Each valued growth bar carries a signed label at its end: above for ≥ 0, below for < 0. One decimal tier per panel: 1 dp, falling back to 0 dp when 1 dp would collide or leave [0, W]. The planner is A4, applied to both panels. Values ≥ 1,000% print 0 dp in either tier. REGN `+20.8% −12.4% … +1.0%`; BYND card `+170% +239% +37% …`. Missing or structural growth prints "—" on the 0% rule; n/m prints "n/m" there. A clipped growth bar gets a «t.surface» break mark and its label prints the true value (LCID `+2,143%`). The YoY row is removed from §3.7, §4.1 and every check. | 0 text collisions in 566 rendered cards. Blind readout: growth sign 100%, growth within ±1 pp 100%, exact transcription 100% (report §9). **Fallback:** if field tests find crowding, restore the draft's row (a 16 px band under panel B, taken from the flex height, signed values in «t.value», "—"/"n/m" in «t.tick») and drop the growth labels. |
| 2. Top-line label precision | F$: 3 s.f. per value in its own unit; A4 drops the whole panel to 2 s.f. | One decimal tier per panel in the panel's unit (A4). d0 gives 3 s.f. on the largest \|v\|; A4 drops one decimal at a time until every label lies inside [0, W] and keeps 2 px from every other label in 2-D (the prototype's test; it does not compare a label with its slot width). A printed value with fewer than 2 s.f. at that tier prints 3 s.f. in its own unit. Ticks never use the own-unit rule. Zero prints `$0`. | REGN `$4.9B … $16.1B $12.2B`; LCID `$4.59M $3.98M $27.1M $0.61B …`; BYND equity legend `−$997K`. One formatter serves labels, legend and strip. |
| 3. Off-scale values | `↓`/`↑` in the notes band; exact values in footnote line 2; an axis-break glyph on the gutter edge | Off-scale values (percent panels only; A3 unchanged) print at the plot edge (A3b). A planned band sits directly above or below the clipped edge: a dashed edge rule in «t.tick», then per item `↑`/`↓` in series ink followed by the true value in «t.value». Rows are assigned greedily by x so boxes keep 4 px of padding on each side, at a 14 px row pitch; each item is clamped inside [1, W − 1]. Footnote: `↓↑  Values beyond the axis range are printed in the band at the plot edge.` The notes band carries no ↑/↓. Lines run toward the clipped point and are cut at the plot clip; the off-scale point has no marker. | Gallery run 1 had 6 failures from overlaps in this band (LCID, RIVN and SNAP annual margins); greedy row planning fixed them, 0 on the re-run (report §9). Model checks: 34 off-scale points across both views, all printed. |
| 4. † | † after the name of a fully calculated series (legend, caption "YoY growth †"); in band cells for partly calculated series | † never appears on series names, legend items or captions. A fully calculated series (margins, FCF, YoY growth) gets a plain footnote sentence and no symbol: `Operating and Net margin are calculated by EarningsNerd from reported figures.` † appears only in notes-band cells, at periods where a partly calculated series has a calculated value, with the footnote `†  Calculated by EarningsNerd from reported figures in the marked periods (<series>).` G6 becomes "† appears only as a notes-band cell glyph". | The user flagged a large † beside a KPI value as confusing and too similar to a dollar figure. One symbol now has one meaning (this period was calculated) and never sits beside a name or number. |
| 5. Ticks | Height-derived cap max(5, 1 + ⌊h/30⌋); expanded gets denser ticks; domains always end on ticks | View-independent ticks. Fixed interval caps per panel (A1): Revenue 5, growth 4, margins 8, cash 8, debt and cash 6, equity 4. The step is the densest legal grid, m·10^e with m ∈ {1, 2, 2.5, 5} and nmin = 2. Card, expanded and export show identical ticks. A1b, small crossing: if every value on one side of zero is within 5% of the chosen step, recompute without them and give that side 10% of a step of room with no tick. Domains end on ticks except at an A1b side. | Export = screen in every view without a view rule. A1b fires in 6 of 290 panels (PLUG equity −$3.6M against +$4.6B would otherwise cost a whole interval). Gridlines are ≥ h/cap apart, ≥ 17 px everywhere (§3.1). Expanded tolerances no longer halve (§1.6). |
| 6. Near-zero signed bars | 2 px stub in the sign direction, reading "≈ $0"; the value only in the strip and tooltip | A bar whose true length is < 2 px is drawn as a 2 px stub anchored AT the zero rule on the value's side; the stub never straddles zero (A13, every bar). An equity bar drawn as a stub also prints its value (A13b): 2 s.f. in its own unit (`−$3.6M`, `$85M`, `$997K`), centred on the slot, on the side of the zero rule with ≥ 14 px of room. It is dropped if it won't fit `slot − 2` or would touch the previous label; it is still in the strip. An exact zero draws the plain stub with no label (prototype). | The blind readout found a +1.0% stub drawn below 0% (REGN FY2025); PLUG's $85M and $70M equity stubs also straddled zero (report §9). A13b fires on 11 points in 7 datasets. |
| 7. Notes band | 16 px reserved; glyphs joined by spaces, collapsed to "a+" on overflow; 3 px halo; "Notes" right-aligned at G_L − 6; `—` for nulls without a letter; ↑/↓ cells | Always reserved, 16 px, under the x-axis (under the strip in expanded). One `<text>` per glyph at x = slot centre + (i − (n−1)/2) × (0.6 em + 1.5 px); glyphs are separated by spacing only; no halo. Review-kind letters take «t.review». "Notes" row label at x = 0, only when a cell is non-empty. The "+n more notes" truncation is optional for production; the verified build shows every footnote line. | Prototype. Every null value carries an unavailable-kind note letter, so the band needs no "—". |
| 8. Legend | HTML, stacked (name over value), superscript note letters, hollow swatch for an absent series; M19 checks the stacked width ≤ 502 px | Inline HTML: swatch, name, latest value, and `(FY2024)` when the latest value isn't the last period. It wraps by whole items. No superscripts. An absent series shows a neutral dashed swatch in «t.tick» and claims no palette slot: `Long-term debt — not in dataset`. M19: legend wraps by whole items; no item splits. | Prototype, 566 cards. The prototype shows the absent item only for long-term debt (missing debt must never read as $0); absent gross margin and FCF are not listed (§3.6). |
| 9. Marker shapes | circle Ø6, square 5×5, diamond 6×6 | circle Ø6, square 6×6, triangle 8 × 7, by present-series index | Prototype marks. |
| 10. Tokens | grid light `#DEDDD6` (Lc 14.7); tick dark `#B8BDC6` (−63.1); dark subtitle and footnotes at DS `text.secondary.dark`; dark legend names at `text.primary.dark` | grid `#DCD9D0` (Lc 16.8) / `#525C6B` (−15.0); tick `#636A77` (74.1) / `#B8BEC7` (−63.6); value `#374151` / `#D7DADC`; zero `#6B7280` / `#9CA3AF`; review `#92400E` / `#FBBF24`; dark series `#62B2A6 #D3A55C #8CA6E3 #E8927C #97A6C2 #AFA2DE`, light series unchanged. Dark HTML subtitle, footnotes and legend names use `chart.label.dark #B8BEC7`. | DS `text.secondary.dark #9CA3AF` measures Lc −48.6, under 60 for 12 px text (`$S/apca_table.txt`). |
| 11. Bars and slot | Bars min(44 card / 56 expanded, round(0.62·slot)); growth min(24 / 32, round(0.36·slot)); slotMin = max(24, widest slot-centred string + 4) | Top-line and equity bars min(44, round(0.64·slot)); growth bars max(4, round(0.6·barW)); same in both views. Minimum slot 36 px in both views; a labelled chart widens until A4 finds a tier, up to 42 px a period (§0.5); below it the SVG scrolls inside its card. The card shows "Values don’t fit at this width. The metrics table lists them." when no tier fits even at 42 px; scrolling alone does not show it. Card SVG 320 px; expanded 520 + strip. | Prototype finding at a 390 px viewport: 27 px slots dropped every printed value of an annual chart; with 36 px slots they print. The phone run shows 0 sideways page scroll (report §9). |
| 12. FY caption, n/m, missing growth | A9; n/m = sentinel or zero prior; separate footnotes for structural and unavailable growth | A9 kept: day ≤ 7 rolls back to the prior month. n/m is the backend `nm` sentinel or a prior value of exactly 0. Missing-growth footnotes use period runs (`none for Q3 ’23–Q4 ’24`), one line for every "—". | n/m and runs: prototype. The prototype implements A9's annual branch; its quarterly subtitle prints `· fiscal quarters ·` and it has no change segment. This spec keeps the full A9 (sim S11: 0 wrong in 72). |
| 13. Tolerances | T = max(step/8, 4 px·span/h), frozen; tiers P, V, O, S | Unchanged. The step-6a scoring uses this T, from the spec's card geometry, identically for current and proposed renders, with ordinals scored where the true gap > T. Tier P is scored as exact transcription of the strings the chart prints. | `$S/score_tiers.py`, `$S/readout/tol_T.json`. |
| 14. Not yet prototyped | — | Tooltip, keyboard stepping, column wash, loading and error skeleton states, and the export header/footer composition are **specified, not yet verified** (§3.9, §3.11, §3.13). | Outside the prototype's scope; kept, not deleted. |
| 15. Checklist | M19 checks the stacked legend width | M19: legend wraps by whole items. New M21 (every bar rect on its value's side of the zero rule, model) and D14 (the same in the DOM via `data-v`/`data-zero`). Checks that mentioned the YoY row now name the bar-label layers. | The stub defect of row 6. |
| 16. Layout heights | Fixed panel heights: single 266/254; Revenue A 118/106, B 80, YoY row 16; Balance 109/103 each | The panels of a chart share a flex height (H minus fixed bands, §3.7). Card: single 256/244; Revenue A 113/106, B 75/70; Balance A 124/116, B 82/78. Label pads 14 px; tick pads 8 px; gap 10 px (16 expanded). Off-scale rows come out of the flex height. | Prototype; H never moves. |
| 17. Balance split | Two equal panels | Weights 0.6 (debt and cash) / 0.4 (equity) | Prototype. Panel A carries the order question B1. |
| 18. Percent formats | F%: 1 dp everywhere (`−18,093.1%`); zero `0.0%` | 1 dp, 0 dp at \|v\| ≥ 1,000 (`−18,093%`); margin zero `0%`; a non-zero value that rounds to zero keeps its sign and 1 dp | Prototype formatter. |
| 19. Legend and strip USD | 3 s.f. per value in its own unit | The panel's tier d0, with the own-unit fallback (AAPL `$99B`, REGN `$4.98B`, PLUG `$3.90M (FY2023)`) | Same formatter as row 2; prototype. |
| 20. Text halos | 3 px «t.surface» halo under bar labels and band glyphs | No text halos. Labels sit outside their bar ends; band, strip and off-scale text sit outside the plot. Markers keep their 1.5 px surface ring. | Prototype draws none; 0 collisions. |
| 21. Gutter, "Notes" | G_L = max(36, ⌈6.6·chars⌉ + 8, 41 if the band is non-empty) | G_L = max(36, ⌈6.6·chars⌉ + 8); "Notes" sits at x = 0 | Prototype. |
| 22. Strip row label | Swatch only | Marker at x = 6, then the legend name's first 6 characters at x = 14 in «t.tick» | Prototype. |
| 23. Revenue legend | Every chart has a legend | Revenue & growth has no legend: both panels are captioned and every bar is labelled | Prototype. |
| 24. Marker size by view | 28 card / 38 expanded (point area) | One size in both views | Prototype. |
| 25. Footnote letter lines | Kind prefix ("Needs review", "Unavailable") and a "View note" link | `a  <series> <period runs> — <message>`; the message is the note's reason text. Opening the note Modal from the letter is specified, not yet verified. | Prototype. |
| 26. Not-applicable copy | A12 copy | A12 copy kept, plus a Cash row. The prototype's interim sentences differ in wording. | Wording is not measured; presence is (0 not-applicable cards without a sentence, report §9). |
| 27. Apostrophe | ’ (U+2019) | ’ (U+2019) in x ticks and captions. The prototype prints U+0027 in x ticks and in the equity caption; both glyphs are in G2. | Matches the period strings in the legend and footnotes (`Q1 ’25`). |
| 28. Draft numbers that no longer hold | Longest tick "−$20.0B" and gutter 36–55 px; card margin T distribution (median 1.25 pp, ≤ 1 pp in 13/59); out-of-scope pairs 72/610 and 41/524; growth-panel fill; stacked legend width 417 px | The rules that produce them are stated in §1–§3; the numbers are measured in the report §9 | Ticks, heights and the legend layout changed. |


### 0.5 In this repository

The engine landed under `frontend/features/analysis/lib/charts/` ahead of any renderer (report §10, step 3), and
the export rule D14 landed for today's charts (step 1). Where the repository departs from this spec, the line below
says so; everything else follows the spec.

- **Where each rule lives.** `scale.ts`: A1, A1b, A2, A3, F$ and compact $. `model.ts`: A5, A8, A9, A11, A12, the
  legend items and values (A10 without the wrapping, which is the renderer's) and the footnotes. `layout.ts`: A3b,
  A4, A6, A7, A13 and A13b, and every pixel a renderer draws: bar rects with their stub and clip flags and label
  baselines, the "—" and "n/m" gap texts, the off-scale bands, and the note glyphs' x. §4.0's interfaces are the
  prototype's shape; the repository's types carry the same values, split between the model (data and strings) and
  the layout (pixels).
- **Currency.** Amounts carry their filed currency (`lessons/frontend-xbrl-amounts-carry-their-own-currency.md`).
  Every `$` in this spec stands for the panel's own symbol from `lib/format.ts`'s `currencySymbol`: `¥2B`, `CA$2B`,
  and a code-like symbol followed by a space, `CHF 2B`. A unit that is not an ISO 4217 code prints no symbol, and the
  subtitle's `USD` segment is the filed currency's code. A chart whose amounts are filed in more than one currency
  draws nothing and says: “These figures are filed in more than one currency, so one scale can’t show them. The
  table lists each in its own currency.”
- **Copy.** The engine's x ticks print ’ (row 27 of §0.4); today's Recharts ticks keep the ASCII apostrophe until the
  renderer replaces them. Strings follow `docs/voice-and-style.md` and its gates: an absent long-term debt's legend
  item reads `Long-term debt not in dataset` beside its dashed swatch, with no em dash, and its footnote says “not
  shown as zero” for “not shown as $0”, since amounts carry their own currency. A company with revenue but no margin
  series, a case A12 does not list, reads “Margin figures aren’t in this company’s filed data.”
- **A1 with no values.** A panel with no values, or only zeros, draws its zero rule alone: ticks `[0]` over the
  domain `[0, 1]`. A1's `V = {0, 1}` would label an empty growth panel `0%`, `+0.25%` … `+1.00%`, and an all-zero
  panel `0%` and `+1%`, values no figure has.
- **The notes band.** A comparison the chart prints as `n/m` carries its note letter in the band too, as its
  footnote names it; A5 takes letters only "where the YoY is a number", which left a footnote naming a period whose
  cell had no letter. Glyphs sit 1.5 px apart, each as wide as its text: A5's pitch for one letter, with no overlap
  for `aa`.
- **The absent debt's legend item** reads `Long-term debt · not in dataset`, all of it the name, with no value and
  no palette slot (`color: null`).
- **The value strip** (§3.10) is collision-free by construction, as §3.10 says, which its geometry did not ensure:
  in the expanded view, every slot holds the strip's widest cell with 2 px each side, and the gutter reaches past
  the rows' short names, so a narrow expanded view scrolls rather than crowd. Each row carries its short name (the
  legend name's first 6 characters) and the legend's swatch (equity's is the bar).
- **A negative top line** (the spec takes it never to be one) gets a label pad under panel A, so its labels stay
  in their band.
- **Readings where the spec is silent or loose**, each now a test:
  - A2's decimals go past 2 when a step needs them: a growth panel within ±0.1% steps by 0.025 and prints
    `+0.025%`, where A2's {0, 1, 2} leaves the label undefined. A1's grid runs from 1e−12 to 5e20 a step.
  - F%'s 0 dp from 1,000% and F$'s d0 test the value as printed: 999.96% reads `1,000%`, and 999.7M on a $B axis
    reads `$1.00B` (3 significant figures), not `$1.000B`.
  - A period run compresses only fiscally consecutive periods, so it never spans a period the window skips (MCD's
    quarterly window has no Q4 ’23).
  - A growth slot with no value of its own is unavailable even in the window's first year, as D17 counts them
    (562 value, 162 structural, 28 unavailable, 2 n/m); both print `—` under one footnote line.
  - A12's sentences follow the top line's own order: a company with revenue and no margin series reads “Margin
    figures aren’t in this company’s filed data.”, whatever else it reports.
  - A4's planning box (12 px, 3 px off the bar's end) reaches 1 px past its 14 px pad at a bar that ends on the
    domain edge; the glyphs themselves (8.8 px above the baseline) stay inside it.
  - A currency code prints a symbol only when the browser's list of ISO 4217 codes holds it, so `ABC` and `XXX`
    print none.
- **A labelled chart widens to print its values (E192).** At the 36 px minimum slot, A4 found no label tier for six
  of the audit's 72 top lines (LCID, NVDA, PLUG, REGN, REGNPN and RIVN, all annual): labels of six characters
  ("$4.86B") cannot keep 2 px apart at a 36 px pitch, and RIVN's "+2,915%" cannot either. On a 342 px phone card
  five of them printed no top-line value; LCID's card already gives it 41.9 px a period. The
  layout (`minChartWidth`) now gives a chart with labelled marks the narrowest whole-pixel width, at most 42 px a
  period (`LABELLED_MAX_SLOT`), at which every labelled panel has a tier; a phone card then scrolls a little
  further inside its card (REGN and NVDA 409 to 465 px, PLUG 432, RIVN 382; LCID's 342 px card already holds them).
  All 72 print their values at 342, 390 and 502 px. A chart that fits its card is never widened, and a chart with
  no labelled marks keeps 36 px.
  - Labels no slot up to 42 px holds keep their chart's minimum, and the card says
    "Values don’t fit at this width. The metrics table lists them." It no longer offers "expand the chart":
    on a one-column phone the expanded view is no wider. A code-prefixed currency's labels ("CHF 4.9B") can reach
    it on a desktop card.
- **The renderer (step 4, E192)** draws behind `NEXT_PUBLIC_CHARTS_V2`, off in production until the founder's switch
  decision (F66). `components/TrendChartSvg.tsx` paints one chart's plan as one SVG with visx's `Group`, `Bar` and
  `LinePath`, in literal attributes; `TrendChartCard.tsx` is the card, which every chart keeps (a chart that does not
  apply says why at the card's height); `TrendCharts.tsx` loads it as its own chunk while the flag is on.
  `lib/charts/theme.ts` holds §3.8's tokens for both themes (owner decision 3 in §0.3), held to the table by
  `tests/unit/chart-theme.spec.ts`; Tailwind holds them from step 6 (E194, two lines down). Step 5 (E193) adds the ways to read it, in
  the next line. The SVG sets `text-rendering="geometricPrecision"`: under full font hinting at 1×
  (headless Chrome's default, and some desktops) Blink snaps each advance to a whole pixel, 7 px where G1 counts 6.6,
  which moved a `CHF 20B` tick label 2 px out of the SVG (D1) and every string off D8. Two readings of D4, which binds
  a series colour to its data: a line run's path names its periods in `data-period`, space-separated, since it spans
  them; the value strip's swatches sit in a `data-strip` group. The tolerance file (§1.0, M20) is readout tooling and
  stays out of the product.
- **Reading a chart (step 5, E193).** `components/TrendChartPlot.tsx` holds the plot and the ways to read it,
  `lib/charts/readout.ts` each period's readout (the tooltip's header and rows, and the sentence a screen reader
  speaks), and `layout.ts` the slot under a pointer, a period's column and the sticky gutter's width. Where it departs
  from §3.9, §3.10, §3.13, A7 and DESIGN_SYSTEM.md §10's contract for today's charts:
  - The values stop is a slider over the periods whose `aria-valuetext` is the period's readout, named
    `{title} chart values`, not `role="application"` beside a live status. A screen reader enters focus mode for it
    unbidden and speaks the value text on focus and on every move, with no live-region timing, and VoiceOver on iOS can
    step it by swiping, where an application stop is out of a touch screen reader's reach. It is a transparent layer
    laid over the viewport, after the overflow region in the Tab order: the pointer passes through it to the plot, its
    brand ring rings the viewport whatever the plot's scroll (an inset ring on the scrolled plot would leave the view
    and lie under the gutter), and a touch screen reader finds it anywhere on the chart. Down and Up step too, and Home and End jump to the
    oldest and newest; a step past either end, which changes no value, says "Oldest period." or "Newest period." in a
    status line. A pointer's tooltip announces nothing: only the keyboard speaks.
  - It starts at the newest period, the one the legend and the metrics table quote, and a plot opens scrolled there
    whenever its view or window starts to overflow: on first layout, after expanding or collapsing (§3.10), whether or
    not the other view overflowed, and for a new window. Never on a resize or zoom, which would lose the reader's
    place: a plot that overflows is planned at its minimum width, which a resize leaves as it is. Today's stop starts
    at the oldest.
  - The header prints a quarter as the app does, `Q2 2026 · quarter ended Jun 30, 2026`, not `Q2 FY2026`: its end
    date tells a fiscal quarter from a calendar one. An amount prints at 4 significant figures in its own unit
    (`$987.6M`), cents at the finest in dollars. A growth row never says Calculated, since every growth rate is a
    calculated comparison and the top line's footnote says so. A note letter takes the band's ink: «t.review» for a
    review note. The state texts carry no dash, as `docs/voice-and-style.md` asks: `Unavailable (a)`,
    `n/m · not meaningful` and `No prior-year period in this window`.
  - The spoken readout spells out what screen readers garble: whole month names, `billion` for `B`, `minus` and
    `plus` for the signs, `Year-over-year growth`, a margin and operating cash flow by their full names, `not
    meaningful` for `n/m`, and a note as the metrics table speaks it (`data note b`).
  - Escape dismisses a tooltip first, wherever focus is when a pointer raised it (WCAG 1.4.13), and then collapses an
    expanded card and returns focus to its toggle, so D13's one Escape is two while a tooltip shows. The tooltip sits
    flush beside its column, so a pointer crosses onto it without passing over another period, and resting on it keeps
    its period. A tap pins it until a second tap on its period or a press outside the chart; a swipe that scrolls the
    plot pins nothing.
  - The tooltip lies outside the scrolling viewport, so 200% text never clips it, inside the viewport's sides and at
    the plot's top. The wash, the gutter and the tooltip sit outside the node the PNG export serialises, so none needs
    A7's `data-export="skip"`.
  - A7's sticky gutter repeats the plot's own gutter while that has scrolled away: the surface over it, each panel's
    caption on a backing as wide as the caption (captions run past the gutter), the tick labels, "Notes" and the
    expanded strip's row names. It shows only while the plot is scrolled, so at rest it never covers an off-scale
    value that reaches into the gutter. Past the gutter it also covers the column a scroll leaves cut at its edge, out
    to the next slot boundary, with the plot's gridlines and edge rules carried across, and the rest of any value that
    runs past its column across that edge: a bar label, which A4 keeps apart in either direction (up to 5 px over),
    and an off-scale value, centred on its column whatever its width (up to 12 px over). So no value shows in part
    beside the axis, where a cut `−19%` would read `19%`; a pointer under the cover reads no period.
  - A grid row's cards share its rows (CSS subgrid: header, plot, notes), so a row's plots start at one height
    whatever its legends wrap to (chief design's review of #1609).
  - §3.9's and §3.10's states (E200):
    - `loading`: while its font loads (G4) a plot's box holds bones from its own plan, four gridlines a panel and a
      bar a slot (`TrendChartBones.tsx`), and its card is `aria-busy`; the plot then replaces them with a fade, the first
      data paint's `duration-base` fade (DESIGN_SYSTEM.md §11, skeleton→content). While the renderer's chunk loads,
      the grid holds four cards of bones, each a header, a two-line legend, a 320 px plot and three lines of notes,
      under one `role="status"` ("Loading charts"), where it drew nothing. Bones are `Skeleton`s, so static under
      reduced motion.
      "The exact final height" is the plot's, a two-line header's and three lines of notes, about a first grid row's: a
      card whose legend wraps to more lines, or whose footnotes run longer, grows when the renderer replaces its bones.
      The status names the wait without `aria-busy`, which may hold a live region's words back; the cards carry it.
    - `exporting`: the export control is `<Button loading>` while its PNG is drawn (the spinner in its glyph's
      place, `aria-busy`, a second press refused), never natively disabled.
    - §3.10's height: a toggle runs the plot's row from its old height to its new one (`duration-base`,
      `ease-standard`, clipped while it runs), and not at all under reduced motion. The card's width changes at once,
      as the grid places it.
- **The renderer's gates.** `frontend/tests/unit/trend-charts-v2.spec.tsx` holds the drawing to the plan on the 19
  datasets, every chart, both views and both themes: D3 on the plan's own geometry, D4, D5, D7, D11, D12 and D14,
  every printed string by its role and ink (D6 on the plan), paint the export can serialise, and the reading contract
  above. The renderer names each text's role (`data-text`) and each panel's plot rect (`data-plot`) for these checks.
  `frontend/tests/unit/chart-readout.spec.ts` holds every readout to the model, and the golden plans carry the six
  datasets' readouts. The unit specs also run M14, and M19 on the PNG's legend (`chart-export.spec.ts`). In a browser,
  under full font hinting, in CI's `e2e-charts-v2` job (a required check on `main`; step 7 moves its specs into
  `e2e-tests`, E195):
  - `frontend/tests/e2e/charts-v2-gallery.spec.ts` draws twelve datasets chosen for their cases, in both themes at
    1280 and 390 px, card and expanded. It holds each chart to the plan the engine makes at the width the page
    measured (its size, and every text by role and ink), and to D1, D2, D3, D5, D6 on the computed colours (the card's
    text too), D8, D9, D10, D14, M6 with A7's sticky gutter, and M19.
  - `frontend/tests/e2e/charts-v2.spec.ts` runs D13, the reading contract above, and the job runs the export's
    fidelity check (E1) against the renderer.
  - The readings the gallery takes:
    - D1 holds a text box to its SVG's edge, not 1 px inside it: the spec's own layout sets captions and "Notes" at
      x = 0.
    - D3's "on the zero rule" is a gap's baseline 3 px above its panel's zero line (A11's placement), within a pixel.
    - D6 measures each paint's computed colour against the card's computed background, itself held to «t.surface»;
      each role takes its §3.8 floor, the ↑ and ↓ arrows a mark's. The column wash is held at the token level only.
    - D9's "before and after hydration": no chart is in the server's HTML (the page draws them after a run), so each
      card's heights are recorded from the moment it is inserted, and it keeps one.
    - M19 lets an item break inside only when it is wider than its legend's whole line: no wrapping avoids that
      without the page scrolling sideways (CLAUDE.md rule 11's 200% text). No item reaches past its legend.
    - It runs at DPR 1 under full hinting, the harder case for D1 and D8, where §6 names DPR 2.
    - The unit fixtures lose their wire `data_notes`, which describe the full datasets the audit rebuilt and which the
      page's contract therefore refuses; the page groups the notes from the points, as for any dataset without them.
  - `frontend/tests/e2e/analysis-layout.spec.ts`, the analysis page's layout gate, runs in that job too and reads the
    charts through `fixtures/trendChartDom.ts`: the renderer's `data-text` and `data-plot` with the flag set, today's
    Recharts layers without it. On the renderer, every chart prints all twelve quarters and keeps its marks whatever
    the metrics table shows; y tick labels sit inside their axis on one line; no chart scrolls at a desktop card's
    width, in Swiss francs too (M6); and a phone's quarter keeps `MIN_SLOT`. Recharts' keyboard and notes case runs on
    Recharts alone, and step 7 retires it (E195).
- **M15** (`frontend/tests/unit/chart-table-agreement.spec.ts`) holds every value a chart prints on the 19 datasets,
  card and expanded at 342, 502 and 1030 px, to the metrics table's cell for the same figure: bar and growth labels,
  A13b labels, off-scale values, strip cells, legend values and the tooltip's readouts. "Rounded to the metrics-table
  precision" is read as: both strings could print one value, less than half a unit of each one's last digit apart,
  since the chart is often the coarser ("$16B" on a phone's bar, "$16.1B" in the table) and a coarser string cannot
  be rounded finer. Rounding both to the coarser precision fails correct pairs too: the true $89.498B prints "$89B"
  and "$89.5B", and "$89.5B" rounds to $90B. Each chart string is also held within half its own unit of the true
  value. A growth value agrees with the YoY the table prints, since the growth panel is YoY, where a quarterly table
  shows QoQ when it has it.
  - M15 found the engine rounding a value on an exact decimal half down: it rounded on the binary double (`toFixed`;
    $143.35M is 143.3499… as a double), where the table rounds the decimal half away from zero (Intl). `scale.ts`'s
    `fixed` now rounds as the table does, so PLUG's 2024Q2 revenue reads "$143.4M" in its tooltip as in the table,
    and the values on a half in five of the golden plans moved away from zero (REGN's FY2025 free cash flow,
    $4,080.5M, reads "$4.081B"). Today's Recharts tooltips and axes take the same formats.
- **The tokens (step 6, E194).** §3.8's Token change list is taken as far as it leaves production as it is until F66:
  - Tailwind holds the renderer's colours as pairs of their own: `chart.s1…s6` (light halves `chart-1…6`, dark halves
    the table's), `chart.tick` (`#636A77`, and `#B8BEC7`, the table's `chart.label.dark`), `chart.value` (`#374151`
    and, since D-063, `#EAECEF`, the figure ink), `chart.gridline` (`#DCD9D0`/`#525C6B`, its
    `chart.grid`) and `chart.review` (`#92400E`/`#FBBF24`). Item 1's dark siblings of `chart-1…6` would make
    `themePairs` require `dark:bg-chart-1-dark` on the landing page's `RevenueBars`, and its new `chart.label` and
    `chart.grid` values would repaint that page's axis labels and leave `components/ui/Chart.tsx`'s mirror behind:
    production surfaces the founder's F66 decision covers. Until then two gates keep the pairs off them:
    `designTokenParity` admits a hex only the pairs hold in `lib/charts/theme.ts` alone, and `chart-theme.spec.ts`
    fails any class that names a pair. E195 folds the pairs into item 1's names.
  - Item 2 waits too: `Chart.tsx` and the shared `chartExport.ts` text mirror keep today's values, since the
    Fundamentals and Peers charts stay on Recharts. The renderer's PNG takes the card's own inks instead: its header
    and notes paint in the legend names' ink. That was `#B8BEC7` on dark while the export's own dark secondary
    measured Lc −48.6 (`#9CA3AF`); #1606 raised the DS secondary to `#D1D5DB` (−77.3), and since E194 the legend
    names take it, so on dark the PNG's header and notes paint in the export's own secondary, a step above the
    card's notes on screen (`#B8BEC7`).
  - `DESIGN.md` (item 3) records the pairs as omitted from its frontmatter until they ship, so its sidecar, which
    copies the frontmatter, is unchanged. DS §1 and §10 name the pairs (item 4). Of item 5, DS §10's paragraph on the
    renderer states its inks; the rewrites of today's contract (hollow markers, the crosshair, "dark labels use
    `secondary`" and †) belong to E195 with the charts they describe, and the font-loader note came with the loader
    (item 6, E199: "Fonts (E199)" below). Item 7 is E195's.
  - `tests/unit/chart-apca.spec.ts` recomputes every Lc the tables print, the Source column's included, and holds
    every token to its floor in both themes, on the card and under the column wash (`cursor`, which the table leaves
    unmeasured). The narrowest clear their floors by less than half a point, on the dark wash: the tick ink at
    Lc −60.3 and the zero rule at −45.4.
- **The gate.** `frontend/tests/unit/chart-engine.spec.ts` runs the model checks M1–M6, M8–M13, M18 and M21, M7,
  M16 and M17 in part, A4 (apart from its planner), A5's letter order and spacing, A7, A13b, G6, L1 for bar labels
  and §3.10's strip, on 19 datasets in `tests/unit/fixtures/chart-datasets.json`
  (chosen from the 73 for their cases, trimmed to the plotted concepts and their quality fields, values unchanged),
  for every chart and both views, at 342, 502 and 1030 px. Golden plans for REGN, LCID, PLUG, BYND, JPM and PGR are
  in `tests/unit/fixtures/chart-golden/`. Before landing, the same checks passed on the audit's 75 datasets (600
  tests). M14, M15 and M19 run on the renderer (above), and M20 stays out of the product.
- **Export.** `features/analysis/lib/chartExport.ts` embeds the page's Geist Mono faces whose `unicode-range` covers
  a character the plot paints, each with its range. That is the subsets a plot needs rather than every subset, and
  the paint is the same. When a face cannot be read, or the plot paints in a family the page loads from a stylesheet
  the script cannot read (one served from another origin), the export stops with an error toast rather than paint a
  fallback. `tests/e2e/chart-export-fidelity.spec.ts` holds E1 for every panel in both themes, in Chromium, the one
  browser CI runs (at most 0.1% of plot pixels may differ by more than 25 in a channel; the worst panel measured
  0.011%, and 1.5–1.7% with the faces left out). Safari and Firefox are not yet checked; F66's preview check covers them.
- **Fonts (E199).** `app/fonts.ts` takes G1's fallback (`adjustFontFallback: false` and the monospace list), so a face
  still loading paints in a monospace one, and keeps `subsets: ['latin']`. `subsets` chooses only the files `next/font`
  preloads, and the root layout preloads them on every route; every subset's face is declared with its `unicode-range`
  either way. A `latin-ext` preload would put 14.7 KB more on every route's critical path for glyphs only the analysis
  surfaces print, and would make † likely, not certain, before first paint. G3's purpose is met by G4's wait instead:
  it loads and checks `11px "Geist Mono"` with the text `0†₹₪₱`. The Font Loading API picks a family's faces by their
  `unicode-range`, and with no text it takes a space, so G4's call as written waits for the latin face alone. With the
  sample the plots paint once the latin face and the latin-ext one (†, and the ₹, ₪ and ₱ that `moneyPrefix` prints)
  are both in, or 1,500 ms pass, so † never swaps after a plot's first paint, and no other route fetches latin-ext
  before its text needs it. The export embeds the faces itself, so it needs no preload either.
  - `trend-charts-v2.spec.tsx` holds the sample to every glyph outside the latin face that the engine prints over the
    ISO 4217 list, and `designSystemDoneGate.spec.ts` holds the loader's two options.
  - Outside the plots, a † or a foreign sign set in the data face (the KPI strip, the metrics table, the card's
    footnotes) can still swap once on a cold cache, now between two monospace faces.
  - ₩ (KRW) and ₫ (VND) are in no Geist Mono subset, so the engine prints their codes ("KRW 120,000T"), as it does a
    code-like symbol (E203); so does XOF, whose "F CFA" holds a narrow no-break space no face draws. `moneyPrefix`
    prints a symbol only where the face draws every glyph past ASCII in it (`DATA_FACE_SIGNS` in `scale.ts`, read by
    hand from the faces' cmaps in a 2026-10-25 build; next/font fetches the faces at build). `chart-engine.spec.ts` holds every prefix over the ISO 4217 list to that
    list, and the wait's sample test holds it to the sample, so a sign the face lacks paints in no plot (G2).
  - Outside the spec renderer, `lib/format.ts`'s `fmtCurrency` still prints ₩ and ₫ in the data face, so in the
    fallback, on four surfaces: the KPI strip, the source dialog's figure (`font-figure`, which falls through to Geist
    Mono), What changed's figures, and today's Recharts charts (`Chart.tsx`). The metrics table prints bare figures.
    A code is wider than the sign, so the fix waits on the KPI strip's narrow cards (E197) and checks each surface's
    width (E203; chief design on #1652).
- **What this spec supersedes, and when.** When the renderer replaces today's charts (report §10, step 7), this spec
  replaces three rules of `docs/design/analysis-data-notes-redesign-2026-10.md` §4.7 for the four trend charts. Note
  letters move off the plot into the notes band (§3.3), and review letters take «t.review»: in the band they sit on
  the card surface, away from the series inks the label-ink rule guarded against. Affected points lose their hollow
  markers. The legend's "Notes a" chip gives way to the footnote lines. Decision 7's filled bars stand. Until the
  flag flips, §4.7 governs the charts in production.

---

## 1. Reading tasks & tolerances (the acceptance test)

### 1.0 Views, tiers and scoring

**Views.** Every tolerance names its view. The reader gets **only the PNG**: no tooltip, no table, no hover.

| View | Capture | Geometry |
|---|---|---|
| **Card** | Browser capture at viewport 1280×900, device scale factor 2: element screenshot of the card (HTML header, legend, SVG, footnotes). Both themes. | SVG 502 × 320 CSS px (1004 × 640 image px) |
| **Expanded** | Same viewport and scale, with the card expanded. | SVG 1030 × (520 + strip) CSS px |
| **Export** | The PNG produced by the export button from either view. | The view's SVG region at 2× (E1), so its tolerance is that view's tolerance |

**Tiers** (from B; pass marks from B):

| Tier | What is read | How it is scored | Pass mark |
|---|---|---|---|
| **P (printed)** | Top-line and growth bar labels, near-zero equity labels, off-scale values, legend values, expanded strip, footnote values | Exact transcription: the number read must equal the value of the printed string. The implied accuracy is ±½ unit in the last printed digit. | 100% |
| **V (position)** | A value read off gridlines | \|read − true\| ≤ **T** | ≥ 90% of in-window values per chart and view |
| **O (ordinal)** | Sign, order of two series in one panel, direction between adjacent periods, peak or trough | Scored only where the true difference > **T**. Below T, "flat" or "tied" also counts as correct. | 100% |
| **S (state)** | Missing, reported zero, n/m, structural, not in dataset | Must name the right state. Any number reported for a missing slot is a fail. | 100%, no tolerance |

**Tolerance T** (B's formula; the 4 px floor is the human placement limit):

```
T(panel, view) = max( step / 8 , 4 px × span / h )      step = printed gridline interval; span = domain; h = panel px
```

- **Frozen.** T is computed once per (dataset, chart, panel, view) from *this* spec's geometry and written to
  `$S/readout/tolerances.json` (check M20). Ticks are view-independent (A1), so step and span are the same in every
  view; only h changes.
- **The same T scores the current design.** Each series uses its panel in this spec. A design with coarser ticks
  therefore cannot pass more easily (product-judge rule). The step-6a comparison scores current and proposed renders
  with the same T from this spec's card geometry (`$S/readout/tol_T.json`), and scores ordinal items only where the
  true gap > T.
- **Where the 4 px floor binds.** step/8 < 4 px·span/h exactly when gridlines are closer than 32 px. Single panels
  on the card hold ≤ 8 intervals in 256 px (annual) or 244 px (quarterly), so gridlines sit ≥ 32 px or ≥ 30.5 px
  apart: T = step/8 on annual cards, and the floor binds slightly on quarterly cards at 8 intervals. Two-panel cards
  usually sit below 32 px, so the floor binds there (REGN, §1.6).

**Report for step 6a**, current vs proposed:

- pass rate per tier, chart and view;
- median and p90 of |err|/step for Tier V.

Today's blind readers already read positions to a median of 0.1–0.6% of the axis span
(`$S/readout/scored_current.json`). Tiers O and S are expected to separate the designs. Today's failures were PLUG
debt vs cash ×6, PLUG debt direction ×5, BYND equity sign ×2 and missing YoY ×5.

**Mechanical scoring aid (from C).** Every panel `<g>` carries `data-axis-step`, `data-axis-domain` and
`data-panel`. Every bar `<rect>` carries `data-v` (true value) and `data-zero` (y of the zero rule). The scorer reads
these; the PNG reader never sees them.

### 1.1 Revenue & growth (title = top line: Revenue / Net interest income / Premiums earned)

| Q | Question | Tolerance | View | How the readout test scores it |
|---|---|---|---|---|
| R1 | What was the top line in each period, and in which period did it peak? | P: bar label at the panel's tier (A4). The largest bar prints 3 s.f.; smaller bars print what that tier gives (REGN `$4.9B`); a value under 2 s.f. at the tier prints 3 s.f. in its own unit (LCID `$4.59M`). Peak: O. | Card, expanded, export | Reader transcribes each label. Scored as exact transcription. Peak period exact where the top two values differ by > T. |
| R2 | Did it grow or shrink against the same period a year earlier, **in every period**? | **O with no exemption.** 100% of the 562 valued growth periods, because the sign is printed on every bar label and drawn as bar direction. | Card, expanded, export | Sign per period from the growth labels. "—" must be read as "no comparison" and "n/m" as "not meaningful", never as 0% (Tier S). |
| R3 | By how much, and is growth accelerating or decelerating? | P at the panel's growth tier (A4): on the card, 1 dp in 33/35 annual and 11/35 quarterly panels, 0 dp in the rest (gallery, `$S/gallery_spec/checks.json`); values ≥ 1,000% print 0 dp. Implied accuracy ±0.05 pp at 1 dp, ±0.5 pp at 0 dp. Expanded re-runs A4 at its width. Acceleration is exact where the printed values differ. | Card / expanded | Value transcribed from the bar label. The direction of Δg is derived from the transcription. Blind readout: 100% within ±1 pp (report §9). |

### 1.2 Margins (gross, operating, net; % of revenue)

| Q | Question | Tolerance | View | How scored |
|---|---|---|---|---|
| M1 | What was each margin in each period? | **Expanded: P ±0.05 pp from the strip, in 59/59 datasets** (meets the user's ±1 pp everywhere). Card: V ±T (REGN ±1.25 pp); the distribution over 59 datasets is measured in the report §9. Off-scale values: P from the off-scale band, every view. Latest value: P from the legend, every view. | Expanded (±1 pp target); card (±T) | Expanded: strip transcription. Card: position read against frozen T. |
| M2 | Was operating and net margin positive or negative in each period? | O against the drawn 0% rule, where \|m\| > T. Expanded: 100%. | Card, expanded | Sign per point |
| M3 | Is each margin expanding or compressing, year to year? Does operating ≥ net hold? | O where \|Δm\| > T, or where \|operating − net\| > T. Expanded: 100% (strip). | Card, expanded | Direction or order per pair. REGN FY2023→24→25 operating (−2.8 pp, −3.2 pp) must read "compressing": 2.8 > T = 1.25 on the card. |

### 1.3 Cash generation (operating cash flow, free cash flow, net income)

| Q | Question | Tolerance | View | How scored |
|---|---|---|---|---|
| C1 | Was FCF above or below net income in each period (cash conversion)? | O where \|FCF − NI\| > T. **REGN FY2025: gap $0.42B > T $0.25B, so it must read "below".** The count of pairs out of scope on the card is measured in the report §9. Expanded: 100% (strip). | Card, expanded | Order per period. Zero drawn misorderings is a model check (M10). |
| C2 | In which periods was OCF, FCF or NI negative? | O against the $0 rule where \|v\| > T. Expanded: 100%. | Card, expanded | Sign per point |
| C3 | What was each series' value? | Card: V ±T (REGN: ±$0.25B). Latest: P (legend, panel tier). Expanded: P (strip). | Card, expanded | Position read, or transcription |

### 1.4 Balance sheet (long-term debt and cash in panel A; equity in panel B)

| Q | Question | Tolerance | View | How scored |
|---|---|---|---|---|
| B1 | Net cash or net debt each period: is cash above or below long-term debt? | O in panel A where \|cash − LTD\| > T_A. The out-of-scope count on the card is measured in the report §9. Expanded: 100%. | Card, expanded | Order per period |
| B2 | Is equity positive or negative each period, and is it rising or falling? | O in panel B where \|E\| > T_B, and \|ΔE\| > T_B for direction. Where a bar is under 2 px, its A13b label is read as P, sign included. Expanded: 100%. | Card, expanded | Sign and direction |
| B3 | What were debt, cash and equity? | Card: V ±T of the panel (REGN ±$0.13B debt and cash, ±$1.95B equity). Latest: P (legend). Expanded: P (strip). | Card, expanded | Position read, or transcription |

**Not a reading task (stated on purpose):** comparing equity with debt or cash by eye. They sit on two scales.
Panel captions, separate tick labels and different mark types say so.

### 1.5 Q0: every chart, every view

| Q | Question | Tolerance | How scored |
|---|---|---|---|
| Q0 | Which periods have no value? Is each one a **reported zero**, **unavailable**, **not meaningful (n/m)**, **before the window (structural)**, or **not in this dataset**? | S, 100%, in every view | Each null or zero slot is named. "Unavailable" must not carry a number. |

### 1.6 Worked tolerances, REGN annual (this spec's geometry; card values in `$S/readout/tol_T.json`)

Ticks are identical in both views (A1), so only h differs.

| Panel | Ticks | Card h → T | Expanded h → T |
|---|---|---|---|
| Revenue (A) | $0–$20B, step $5B | 113 px → ±$0.71B (floor), labels printed | 229 px → ±$0.625B, labels printed |
| YoY growth (B) | −50…+100%, step 50 | 75 px → ±8 pp (floor), labels printed | 153 px → ±6.25 pp, labels printed |
| Margins | 0–60%, step 10 | 256 px → **±1.25 pp** | 456 px → ±1.25 pp (strip: ±0.05 pp) |
| Cash | $0–$10B, step $2B | 256 px → **±$0.25B** | 456 px → ±$0.25B |
| Debt & cash (A) | $0–$4B, step $1B | 124 px → ±$0.13B (floor) | 240 px → ±$0.125B |
| Equity (B) | $0–$40B, step $10B | 82 px → ±$1.95B (floor) | 160 px → ±$1.25B |

REGN card growth labels: `— +20.8% −12.4% +27.4% +29.6% +89.1% −24.3% +7.8% +8.3% +1.0%` ("—" for FY2016, on the
0% rule).
REGN card bar labels: `$4.9B $5.9B $5.1B $6.6B $8.5B $16.1B $12.2B $13.1B $14.2B $14.3B` (tier d = 1).

---

## 2. Axis strategy per chart, with the justifying numbers

The following are each used only where a measured number requires them, and each use is cited:

- dual axes;
- log scales;
- indexing;
- small multiples;
- clipping or broken axes.

| Chart | Strategy | Justifying numbers | Rejected, and why |
|---|---|---|---|
| **Revenue & growth** | Two aligned panels with a shared band x. A: top line, linear, domain from A1. B: growth, linear, zero-anchored, A3 clip. Signed labels at each growth bar's end. | Growth is negative in 41/65 datasets, so a visible 0% rule is needed in most of them. $ and % share no scale, and today's 0% floats at an arbitrary dollar height (REGN 0% ≈ $4.5B). \|g\| > 100% in 8/65 and > 50% in 17/65. A3 clips 6 points in 4/70 (BYND FY2018–19, ETSY FY2020, LCID FY2021–22, RIVN FY2022). The top line is never negative (0 negative values in 73 datasets). Within-ticker top-line range: median 1.7×, p90 11.9×, max **340×** (LCID). | **Dual axis:** misreads, as above. **Log:** growth is negative in 41/65; RIVN has $0 revenue in FY2019–20; bar length is meaningless on a log scale. **Indexing:** owner rule. **Growth as text only (C):** drops the graphic sign cue. **Growth line over bars:** it is a dual axis again. |
| **Margins** | One linear % axis. Zero always in the domain. A3 clip; clipped values printed at the plot edge (A3b). | >10× between series in only 2/59 datasets (LCID 794×, RIVN 10.1×), caused by outliers. Operating margin is negative in 22/59; margins cross zero in 21/59. Below −100% in 9/59 (LCID −18,093%, RIVN −8,524%, PLUG −679%). A3 clips 11 points in 3/59: LCID FY2019–21 (6), RIVN FY2021 (3), SNAP FY2017 (2). PLUG/a, PLUG/q, BYND/a/q, LCID/q and RIVN FY2022 plot in full: LCID/q on −600…0% and PLUG/q on −700…+10% (A1b: its one positive value, +2.4%, gets room rather than a tick), in every view. | **Fixed ±100% clip:** would clip all 22 LCID/q points (B measured 97 points). **Small multiples:** demote the M1–M3 comparison to non-aligned scales to serve 2/59 datasets. **Log/symlog:** negatives in 22/59. |
| **Cash generation** | One linear $ axis, zero-anchored, never clipped. | Ratios on one axis: >10× in 1/73 (JPM/q 11.9×); OCF/NI median 1.5×, FCF/NI median 1.3×. 39/73 datasets have a series crossing zero. FCF and NI swap order inside the window in 52/60 datasets, so order is the question, and only a common scale shows it truthfully. | **Dual axis:** 29% misordered pairs. **Clipping:** "every pixel is a citable dollar"; the max ratio of 11.9× stays readable. |
| **Balance sheet** | Two aligned panels (0.6 / 0.4 of the plot height). A: debt and cash, one $ axis from $0. B: equity, zero-anchored both ways. | One axis would be >10× in 30/73 (41%): cash vs equity 19/73, debt vs equity 12/58. The dual axis misorders 28% of pairs. Equity is negative in 16/73, while debt (0/629) and cash (0/788) are never negative. The net-debt sign flips inside the window in 24/58 datasets, so debt and cash must share a scale. Debt vs cash is >10× in 10/58 (PLUG 119×, NEE 32×, ROKU 23×, CLFD 17×, POOL 13×, MCD 12×). These are kept on one scale on purpose: "one is negligible" *is* the B1 answer, and the smaller series is printed in the legend (latest) and in the strip (all periods). | **Single axis:** 41% compressed. **Dual axis:** 28% misordered. **Three panels:** split debt from cash and break B1. **Log:** equity is negative and LTD = 0 at 14 points. |

**Tick-label width.** Under A1/A2 the gutter is G_L = max(36, ⌈6.6 × maxTickChars⌉ + 8); the longest label and the
gutter range are measured in the report §9. Today the longest label is "−19,500.0%" (10 chars, 73 px) in a 56 px
band, which drops its minus sign, and "3,000.0%" sits in a 48 px band.

---

## 3. Shared rules

### 3.1 Number and tick formatting (exact algorithms)

**A1. Domain and ticks** (C's densest-grid search with fixed caps; view-independent).

```
input: in-range values V of one panel (true values; for percent panels after A3); the panel's interval cap N
caps N: Revenue 5 · YoY growth 4 · Margins 8 · Cash 8 · Debt and cash 6 · Equity 4;   nmin = 2
if V is empty: V = {0, 1}

core(V):
  lo = min(0, min V);  hi = max(0, max V)                       // zero-anchored, always
  if lo == hi (every value is 0): return domain = [0, 1], ticks = [0, 1], step = 1
  for e = −3, −2, … : for m in [1, 2, 2.5, 5]:                  // ascending ⇒ the densest legal grid wins
      s = m·10^e;  a = floor(lo/s + 1e−9);  b = ceil(hi/s − 1e−9);  n = b − a
      if nmin ≤ n ≤ N: return step = s, ticks = [a..b]·s, domain = [a·s, b·s]

A1b. Small crossing. base = core(V); try side = −1 (below zero), then side = +1 (above zero):
  S = { v ∈ V : sign(v) = side };  R = V \ S
  if S ≠ ∅  and  every v ∈ S has |v| ≤ 0.05·base.step  and  R holds a value of sign −side:
      ax = core(R)
      if every v ∈ S still has |v| ≤ 0.05·ax.step:
          return ax with its domain end on that side set to side · 0.1·ax.step        // room, no tick there
  return base
```

Properties: uniform steps; 0 is a tick; ticks depend on the data only, never on the view or the width; the domain
ends on ticks except at an A1b side; dataMax is never appended. A1b fires in 6 of 290 panels. Example: PLUG equity
(−$3.6M against +$4.6B) gets ticks $0, $2B, $4B, $6B and the domain −$0.2B…$6B.

Gridline spacing is h/n ≥ h/cap (h/(cap + 0.1) at an A1b side):

| Panel | Cap (intervals) | Card h annual / quarterly | Expanded h annual / quarterly | Smallest card spacing |
|---|---|---|---|---|
| Revenue A | 5 | 113 / 106 | 229 / 222 | 21.2 px |
| Growth B | 4 | 75 / 70 | 153 / 148 | 17.5 px |
| Margins | 8 | 256 / 244, less off-scale rows | 456 / 444, less off-scale rows | 30.5 px without off-scale rows |
| Cash | 8 | 256 / 244 | 456 / 444 | 30.5 px |
| Debt and cash (Balance A) | 6 | 124 / 116 | 240 / 233 | 19.3 px |
| Equity (Balance B) | 4 | 82 / 78 | 160 / 155 | 19.5 px |

Panel fill (the share of the domain the data use) is measured in the report §9.

**A2. Tick labels**

- **Unit:** one per axis, the largest of {T 1e12, B 1e9, M 1e6, K 1e3, none} with unit ≤ max(max\|tick\|,
  max\|v\|). The domain covers the data, so this is the unit of the largest tick, never "−$1,000M".
- **Decimals d:** the smallest d ∈ {0, 1, 2} at which step/unit × 10^d is an integer. One d per axis.
- **USD:** `[−]$<|t|/unit, grouping ",", d dp><unit>`. Zero is exactly `$0`.
- **Percent:** `[−]<|t|, d dp>%`, with 0 dp when \|t\| ≥ 1,000. Zero is exactly `0%`. Growth ticks are signed:
  `+50%`, `0%`, `−50%`.
- **Minus** is U+2212 everywhere in the SVG.
- **Ticks never use the own-unit rule of F$.**
- **Gutter:** `G_L = max(36, ⌈6.6 × maxTickChars⌉ + 8)`, taken over every panel of the chart; one gutter per chart.
  Tick labels are right-aligned at x = G_L − 8. The right pad is 8 px. There is no right gutter.

**F$. Printed USD values** (top-line bar labels, legend, strip)

- **Panel tier.** d0 is the number of decimals that gives 3 significant figures on the panel's largest \|v\| in the
  panel's unit: `d0 = max(0, 2 − ⌊log10(max|v| / unit)⌋)`. Bar labels drop below d0 only through A4. Legend latest
  values and strip cells always use d0.
- **Format:** `[−]$<|v|/unit, grouping ",", d dp><unit>`: REGN `$4.9B`, `$16.1B`; AAPL `$99B`; ISRG `$3.03B`.
- **Own-unit fallback.** If \|v\|/unit < 10^(1−d), the value would print with fewer than 2 significant figures. It
  then prints 3 s.f. in its own unit instead: x = \|v\|/ownUnit at max(0, min(2, 2 − ⌊log10 x⌋)) dp. LCID revenue
  `$4.59M $3.98M $27.1M $0.61B …`; BYND equity `−$997K`; PLUG debt `$3.90M (FY2023)`. If the own-unit mantissa rounds
  to 1,000, it steps up one unit.
- Exact zero is `$0`.

**Compact USD** (A13b only): 2 significant figures in the value's own unit, x at max(0, 1 − ⌊log10 x⌋) dp, so a
3-digit mantissa prints whole: `−$3.6M`, `$85M`, `$997K`.

**F%. Printed margins** (legend, strip, off-scale band): 1 dp with grouping, 0 dp when \|v\| ≥ 1,000: `24.9%`,
`−679.0%`, `−18,093%`. Exact zero is `0%`. A non-zero value that rounds to zero keeps 1 dp and its sign (`−0.0%`).
Strip cells fit their slots by construction: one cell per slot per row, and the widest cell is 8 characters
(52.8 px).

**F±. Growth labels** (panel B)

- Signed, at the panel's tier (A4): 1 dp, or 0 dp for the whole panel when 1 dp would collide or leave [0, W].
- \|g\| ≥ 1,000 prints 0 dp in either tier: `+2,143%`, `+2,915%`.
- Zero prints `0.0%` at 1 dp and `0%` at 0 dp. A non-zero value that rounds to zero keeps its sign and 1 dp
  (`+0.3%` at the 0 dp tier, `+0.0%` at the 1 dp tier).
- Non-values print `—` or `n/m` on the 0% rule (A11).

**Tooltip** (specified, not yet verified): 4 s.f. USD (`$14.34B`), 1 dp percent, with the same sign and zero rules.

**X ticks:** annual `’25` (U+2019); quarterly two lines, `Q2` over `’26`, the second line 12 px lower. Every period
gets a tick (D2 kept). There is no axis title in the SVG.

### 3.2 Fonts and glyphs (C's G-rules, with the product judge's correction)

- **G1. Font stack.** All SVG text is Geist Mono 11 px, weight 400, via `CHART_FONT`. `var(--font-geist-mono)` stays
  first, per DS §12.3. The Arial-based "Geist Mono Fallback" is fixed at the loader instead, in `app/fonts.ts`:

  ```
  Geist_Mono({ subsets: ['latin', 'latin-ext'], adjustFontFallback: false,
               fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'], variable: '--font-geist-mono' })
  ```

  Layout arithmetic uses 0.600 em = 6.6 px per glyph, checked in the WOFF2 for every glyph in G2. Numerals are
  tabular.
- **G2. SVG glyph whitelist.** Printable ASCII U+0020–U+007E, plus ’ (U+2019), − (U+2212), — (U+2014),
  ↑ (U+2191), ↓ (U+2193), · (U+00B7) and † (U+2020). All are in the `latin` subset except †, which is in
  `latin-ext`. ↑ and ↓ appear only in the off-scale band; † only in notes-band cells. Banned: U+2009 thin space,
  ▲ (U+25B2), ▼ (U+25BC), and any glyph absent from both subsets.
- **G3. Preload.** Both subset files are preloaded on the analysis route, so † never swaps after first paint.
- **G4. Wait for fonts.** The chart SVG paints after `document.fonts.load('11px "Geist Mono"')` resolves or 1,500 ms
  pass. The skeleton has the exact final height in the meantime (skeleton: specified, not yet verified).
- **G5. Baselines.** Every text element has a numeric baseline from the planner (§3.7 text table). Do not use
  `dominant-baseline`. The one em offset allowed is the tick label's fixed 0.32 em (3.52 px at 11 px), because the
  font size is fixed.
- **G6. † appears only as a notes-band cell glyph.** It marks a period in which a partly calculated series was
  calculated, and its key is the footnote line that starts with `†`. It never follows a series name, legend item,
  caption, title or number. A fully calculated series gets a footnote sentence and no symbol. Regex check: no
  `[0-9$%BMKT]\s?†`. The KPI strip is outside chart scope, but the check runs there too: a large † beside a big
  number is the defect the user flagged.

### 3.3 Notes a/b and †: footnote band algorithm (A5)

> **2026-10-25: what the band marks is superseded** by the approved quiet scheme
> (`docs/mpa-improvements/coherence.md` §2.6, D-061): a cell shows only the letters of notes that question the number,
> in the `note` ink; no † glyph, since the footnote lines already name the calculated series; and a gap gets its
> sentence and no letter. The band's geometry below stands. E194 builds it through WP1's `lib/dataNotes.ts` helper.

Nothing note-related is drawn inside a plot rectangle: no hollow markers and no letters. A note attaches to a data
point through **two coordinated places**.

1. **The band.** One 16 px row under the period axis (under the strip in expanded), **always reserved** even when
   empty. It has one cell per period, centred on the period's slot (the same x as the bar or marker above it).
2. **The footnote line.** HTML under the SVG. It says what the note is, and which series and periods it covers.

```
A5  for period i in 0..n−1:
      L = ⋃ over plotted series s of value-note letters(s, period i)
          ∪ (Revenue & growth only) comparison-note letters(top line, period i, basis 'yoy'), where the YoY is a number
      dag = '†' if any PARTLY calculated plotted series has a calculated value at i
            // FULLY calculated series (all margins, FCF, YoY growth) get a footnote sentence, never a glyph
      glyphs = sorted(L) ++ ([dag] if dag)
      glyph k of n: its own <text>, text-anchor middle, at x = x_i + (k − (n−1)/2) × (6.6 + 1.5) px     // spacing only
    ink: review-kind letters → «t.review»; everything else → «t.tick»; no halo
    row label "Notes" at x = 0, left-aligned, «t.tick», only when any cell is non-empty
```

Definitions:

- A value is **calculated** when its `provenance.method` is `'calculated'` (or, without provenance, its legacy
  `derived` flag is set).
- A series is **fully calculated** when it has a non-null value and every non-null value is calculated; **partly
  calculated** when some, but not all, of its non-null values are.
- Every null value carries a note of kind `unavailable` (default reason "not in dataset"), so every missing point has
  a letter. Note letters are assigned in kind order review, unknown, unavailable (a, b, …, z, aa, …).
- ↑ and ↓ never appear in the band (A3b prints off-scale values at the plot edge).

**Measured.**

- Sim S9: cells hold at most 2 glyphs. Counts: `†` 694, `a` 344, `a †` 68.
- With n ≤ 4 glyphs a cell is 3 × 8.1 + 6.6 = 30.9 px wide, inside the 36 px minimum slot.
- REGNPN gets exactly one `a` per period at FY2023–25 in Margins and Cash, where today it stacks up to 6 rings and
  6 letters. Balance gets `b` at FY2016–18.

**Interaction** (specified, not yet verified)

- Band glyphs are `aria-hidden`. Pointer-only overlay buttons (`tabindex=-1`) open the shared note Modal.
- The card keeps **one** keyboard Notes control (today's `DataNotesLink`). Footnote letters are focusable buttons.
- The legend's "Notes a" chip and the "unavailable for FY…" sentence are removed (verified).

**Footnote lines** (HTML, 12 px; light `text.tertiary #636A77`, dark `chart.label.dark #B8BEC7`), one per line, in
this order:

1. Each letter, in letter order: `a  Operating margin and Net margin FY2023–FY2025; Free cash flow FY2024 — <message>`.
   - Only this chart's series appear, by their dataset labels.
   - Consecutive periods compress to runs (`FY2023–FY2025`, `Q3 ’23–Q4 ’24`); other periods are comma-separated.
   - Series that share the same runs are listed together: `A, B and C`.
   - Revenue & growth adds YoY comparison references as `<top line> YoY <runs>`, for example `Revenue YoY FY2024`.
   - The message is the note's reason text.
2. `†  Calculated by EarningsNerd from reported figures in the marked periods (<partly calculated series>).` Only
   when a partly calculated series is plotted.
3. `<fully calculated series> is/are calculated by EarningsNerd from reported figures.` Margins share the suffix:
   `Gross, Operating and Net margin are calculated by EarningsNerd from reported figures.` Revenue & growth always
   lists YoY growth (`YoY growth is calculated by EarningsNerd from reported figures.`).
4. Chart-specific lines:
   - Revenue & growth: `—  YoY growth needs the same period a year earlier; none for <runs>.`, one line for every
     growth period printed "—", structural or unavailable (`none for FY2016`; `none for Q3 ’23–Q4 ’24`).
   - Revenue & growth: `n/m  Not meaningful: the prior-year figure was zero or of the opposite sign (<runs>).`
   - Revenue & growth, when any growth bar is clipped: `Growth bars beyond the axis are broken; their printed value is the true value.`
   - Margins, when any point is off-scale: `↓↑  Values beyond the axis range are printed in the band at the plot edge.`
   - Balance sheet, when long-term debt is absent: `Long-term debt isn’t in this dataset for this window (not shown as $0).`

The card, the expanded view and the export show every line. A "+n more notes" truncation that opens the Modal is
optional for production and is not part of the verified build.

**2026-10-25, D-061:** today's charts already mark a point only where its note questions the number (`noteMarksFigure`,
`features/analysis/lib/dataNotes.ts`). This band takes the rule as the note at the head of §3.3 states it, in the
charts plan's step 6 (E194), before F66. Until then it letters every note, drawn only behind `NEXT_PUBLIC_CHARTS_V2`,
which is off.

### 3.4 Missing, zero, negative, outlier

**State taxonomy (A11)**

- Each point is one of: `value | zero | missing | below | above` (the last two are off-scale, percent panels only).
- Each series is `present | absent`. A series is absent when it has no non-null value in the window.
- Growth is one of:
  - `value`;
  - `structural`: no prior period in the window (the first year, or the first four quarters);
  - `nm`: the backend sentinel string, **or** a prior value that is exactly 0 (the prior is the previous year, or
    the same quarter four periods earlier);
  - `unavailable`: the current or prior top-line value is null, or the YoY was not computed.

| Case (count) | Line panels | Bar panels | Labels / band / legend / strip / tooltip |
|---|---|---|---|
| **Missing** value (top line 18 slots in 9 datasets, sim; LTD 105 points in 22 datasets) | Path breaks. No marker. Neighbours keep their markers; a run of one valued point draws its marker only. | No bar. A `—` in «t.tick», centred on the slot, baseline 3 px above the zero rule. | Band letter (unavailable note). Strip `—`. Tooltip `— Unavailable (a)`. |
| **Zero** (LTD 14 points in 11 datasets; revenue 2) | Normal marker on the zero rule, kept visible by its 1.5 px ring | 2 px stub in series colour, full bar width, above the zero rule; top-line label `$0` | `$0` |
| **Near-zero bar**: 0 < true length < 2 px (equity 11 points in 7 datasets: BYND FY2025 −$997K, PLUG FY2018 −$3.6M, PLUG $85M …) | — | **2 px stub anchored at the zero rule on the value's side** (A13). Equity bars also print the compact value beside the zero rule (A13b). Top-line and growth stubs keep their normal label. | Exact value in the strip and tooltip |
| **Negative** | Below the zero rule. No fill, no hue change. | Bar grows down from 0 | U+2212 |
| **Off-scale** (percent only, A3) | The line runs toward the true value and is cut at the plot clip (plot rect + 1 px top and bottom). No marker for that point. The true value prints in the off-scale band at that edge (A3b). | Growth bar runs to the edge, with a «t.surface» break mark 6 px inside its end; its label prints the true value at the edge | Strip and tooltip show the true value; tooltip adds "(off scale)"; one footnote line per chart (§3.3) |
| **Growth: structural** (162) | — | No bar; `—` on the 0% rule, «t.tick» | Footnote `—  YoY growth needs …` |
| **Growth: n/m** (2, RIVN FY2020–21) | — | No bar; `n/m` on the 0% rule, «t.tick» | Footnote `n/m  Not meaningful …` |
| **Growth: unavailable** (28) | — | No bar; `—` on the 0% rule, «t.tick» | Same `—` footnote line as structural |
| **Absent series** (LTD 15 datasets, FCF 13, gross margin 20/59) | Not drawn | Not drawn | Long-term debt keeps a legend item with a neutral dashed swatch and `— not in dataset`, plus a footnote line; never `$0`. Absent gross margin and FCF are not listed. No strip row. |
| **Whole chart inapplicable** (top line 3/73; margins 14/73) | The card keeps its title, subtitle and 320 px SVG height. Body: one sentence chosen by reason (A12, §3.6), centred. | | |

**A3. Percent outlier rule** (A's rule; margins panel and growth panel only; unchanged)

```
for each series S in the panel:  T_S = 5 · max(median_{v∈S} |v|, 10 pp)
O = { v ∈ S : |v| > T_S }                                   // own-series median
span_all = extent(V ∪ {0});  span_in = extent((V \ O) ∪ {0})
clip O  iff  O ≠ ∅  and  span_all ≥ 3 · span_in
A1 then runs on V \ O; a value outside the resulting domain is 'below' or 'above'
```

The decisions closest to the threshold are ETSY growth (3.01) and SNAP margins (3.28). In both, every clipped
value is printed, so a flip can only change the axis range, never hide a number. Sim S4 reproduces the A counts.

**A3b. Off-scale band** (percent line panels, that is Margins; growth bars use the break mark and their label)

```
for side in {above, below}:
  items = every line point beyond the domain on that side, sorted by slot centre x
  for each item:
      text = F%(v)  (1 dp; 0 dp at |v| ≥ 1,000);   w = 6.6·len(text) + 9             // arrow 6.6 px + 2.4 px gap + value
      left = clamp(x − w/2, 1, W − w − 1)                                             // inside [1, W − 1]
      box  = [left − 4, left + w + 4]                                                 // 4 px padding per side
      row  = the lowest existing row in which box overlaps no box (touching allowed); else a new row
  band height = 14·rows + 4, placed outside the panel's 8 px tick pad; it is taken from the flex height (A6)
  draw: a dashed rule on the clipped plot edge (1 px «t.tick», dash 2 2, from G_L to W − 8)
        per item: '↑' (above) or '↓' (below) at x = left in the series colour, then the value at x = left + 9 in
        «t.value»; both left-aligned, baseline = band top + 10 + 14·row
```

LCID annual margins: domain −600…+100%; one band below the plot holds six items at FY2019–21: Operating `−5,619%`,
`−15,071%`, `−5,645%`; Net `−6,043%`, `−18,093%`, `−9,516%`.

### 3.5 Colour and shape assignment (A8)

- Series colours are `chart-1..k` (teal, honey, cornflower) **in canonical order over the present series**.
  Canonical orders:
  - top line, then growth;
  - gross, operating, net;
  - OCF, FCF, NI;
  - LTD, cash, equity.
- Marker shape follows the same index: circle Ø6 (r 3), square 6×6, triangle 8 wide × 7 tall (apex 4 px above the
  centre, base 3 px below). Every marker has a 1.5 px «t.surface» ring painted under its fill.
- Legend order, colour order, shape order, strip row order and tooltip row order are the same list.
- An absent series claims no palette slot.
- Series tokens may appear only on:
  - marks bound to a data value (`data-series`, `data-period`);
  - the off-scale arrows, bound to their point;
  - legend and strip swatches.
- The break mark on a clipped bar uses «t.surface», never a series token.
- Gain/loss and sage tokens never appear in these four charts. Sign is carried by position against a drawn zero rule
  and by the printed "+" and "−".

### 3.6 Legend, title, caption hierarchy

1. **Card title** (the card's heading, DS heading ink): `Revenue & growth` | `Net interest income & growth` |
   `Premiums earned & growth` | `Margins` | `Cash generation` | `Balance sheet`. A not-applicable top-line card is
   titled `Top line & growth`.
2. **Subtitle** (HTML 12/400; light `text.tertiary #636A77`, dark `chart.label.dark #B8BEC7`).
   - Annual: `FY2016–FY2025 · fiscal years end Dec · USD`.
   - Quarterly: `Q3 ’23–Q2 ’26 · fiscal year ends Sep · USD` (A9).
   - Margins: replace `USD` with `% of revenue`.
   - This replaces the in-SVG "Fiscal year" title.
3. **Legend** (HTML, inline: A10). For each present series in canonical order, one item:
   - a swatch, 16 × 10 px: for a line, a 16 px 2 px stroke with the marker shape centred; for bars, a 10×10 r2 square
     centred in the box;
   - 6 px gap, then the name (12 px; light `text.secondary #374151`, dark `chart.label.dark #B8BEC7`);
   - 6 px gap, then the latest available value (Geist Mono 12; light `text.primary #1A1A17`, dark
     `text.primary.dark #EAECEF`), at the panel's tier (F$ d0, or F%), with ` (FY2024)` or ` (Q1 ’25)` when it is not
     the last period.
   - Names: Margins `Gross`, `Operating`, `Net`; Cash `Operating CF`, `Free cash flow`, `Net income`; Balance
     `Long-term debt`, `Cash`, `Equity`.
   - An absent long-term debt keeps its item in canonical position: a neutral dashed swatch (16 px, 1.5 px «t.tick»,
     dash 3 2), the text `Long-term debt — not in dataset`, no value, no palette slot.
   - Items sit 12 px apart, rows 4 px apart. The legend wraps by whole items; an item never splits.
   - Revenue & growth has no legend: both panels are captioned and every bar is labelled.
   - Never `(left)` or `(right)`, never †, never superscript letters. The "Notes" chip is removed.
   - In the examples (§4.2–§4.4), ● ■ ▲ stand for the line swatch with that marker, ▮ for the bar swatch and ┄ for the
     dashed swatch. Swatches are drawn as SVG shapes, never as text glyphs.
4. **Panel captions** (two-panel charts, in the SVG, Geist Mono 11, «t.tick», left-aligned at x = 0):
   - Revenue & growth: `Revenue` | `Net interest income` | `Premiums earned`, and `YoY growth`.
   - Balance sheet: `Long-term debt and Cash` (or `Cash` when LTD is absent) and `Shareholders’ equity`.
5. **In-SVG text** (Geist Mono 11): ticks, captions, bar labels, A13b labels, off-scale band, strip, notes band.
6. **Footnotes** (§3.3).

**A9. FY-end text** (B's rule, sourced from the latest FY or fiscal-Q4 row):

```
rows = periods with fiscal_period ∈ {FY, Q4} and a period_end, in window order
if rows is empty: omit the "· fiscal year(s) end …" segment                 (XOM/q)
month(p) = month(period_end), minus one month if day ≤ 7                    // 52/53-week years ending in the first days of a month
text = month(last row)
if any adjacent rows differ in month(p): append " · fiscal year end changed in FY<fiscal_year of the later row>"
```

Result: 0 wrong across 72 datasets (sim S11). The period span uses the short period form: `FY2016–FY2025`,
`Q3 ’23–Q2 ’26`.

**A10. Legend layout.** Items in canonical order, laid out inline with 12 px gaps, wrapping by whole items. The
legend has no fixed width; it never pushes the plot.

**A12. Not-applicable copy**

| Chart | Condition | Copy |
|---|---|---|
| Top line | None of revenue, NII or premiums is present (ALL/q, O/a, O/q) | "No top-line figure in this company’s filed data (revenue, net interest income or premiums earned)." |
| Margins | NII present (BAC, JPM, WFC) | "Margins need revenue. {Company} reports net interest income instead; see Net interest income & growth." |
| Margins | Premiums present (ALL/a, MET, PGR) | "Margins need revenue. {Company} reports premiums earned instead; see Premiums earned & growth." |
| Margins | No top line | "Margins need revenue, which is not in this company’s filed data." |
| Cash | None of OCF, FCF or NI is present (never hit: 73/73 render) | "Cash-flow figures aren’t in this company’s filed data." |

### 3.7 Layout bands (A6: every pixel assigned before render)

**Card.** W = container width (502 at a 1280 viewport); H = **320** in every chart and mode.

| Band (px) | Margins / Cash | Revenue & growth | Balance sheet |
|---|---|---|---|
| top pad | 8 | 4 | 4 |
| caption A | — | 14 | 14 |
| off-scale rows above (A3b) | 14·rows + 4, only when a point is above the domain | — | — |
| pad above A | 8 | 14 (bar-label pad) | 8 |
| **panel A** | **flex**: 256 annual / 244 quarterly | **0.6·flex**: 113 / 106 | **0.6·flex**: 124 / 116 |
| pad below A | 8 | 8 | 8 |
| off-scale rows below (A3b) | 14·rows + 4, only when a point is below the domain | — | — |
| gap | — | 10 | 10 |
| caption B | — | 14 | 14 |
| pad above B | — | 14 (bar-label pad) | 8 |
| **panel B** | — | **flex − A**: 75 / 70 | **flex − A**: 82 / 78 |
| pad below B | — | 14 (label pad for negative growth) | 8 |
| x-axis | 20 annual / 32 quarterly (12 px line height) | 20 / 32 | 20 / 32 |
| value strip (expanded only) | 6 + 16 × present series | — | 6 + 16 × present series |
| notes band (always reserved) | 16 | 16 | 16 |
| bottom pad | 4 | 4 | 4 |

- **A6.** `flex = H − (sum of the fixed bands above, strip excluded)`, with a minimum of 60.
  Panel A = round(flex × 0.6), panel B = flex − A; a single panel takes the whole flex.
- Off-scale rows exist only on the Margins panel, and their height comes out of the flex.
- The value strip adds to H, so it never changes the flex.

**Expanded.** W = grid width (1030 at 1280); H = 520 + strip; the gap is 16; all other bands as on the card.

- Single panel: 456 / 444 (less off-scale rows).
- Revenue & growth: flex = 382 / 370, so A = 229 / 222 and B = 153 / 148.
- Balance sheet: flex = 400 / 388, so A = 240 / 233 and B = 160 / 155.
- **Strip:** 6 + 16 × (number of present series), between the x-axis and the band (§3.10).

**Horizontal.**

- `plotW = W − G_L − 8`; `slot = plotW / n`; centre `x_i = G_L + slot·(i + ½)`.
- Bars:
  - top-line and equity bars are `min(44, round(0.64·slot))` wide, corner radius 2;
  - growth bars are `max(4, round(0.6·barW))` wide, square corners, so their narrower width marks them as a ratio
    rather than a level.

**A7. Slot minimum and scroll.**

- The minimum slot is 36 px in both views: `W = max(container width, G_L + 8 + 36·n)`.
- A chart with labelled marks takes the narrowest whole-pixel width, at most `G_L + 8 + 42·n`, at which A4 finds a
  tier for every labelled panel (§0.5), and `W = max(container width, that width)`. A chart whose labels no slot up
  to 42 px holds keeps 36 px.
- When W exceeds the container, the SVG scrolls horizontally inside its card (the existing `useOverflowRegion`
  viewport); the page never scrolls sideways.
- Measured: at 1280 no chart scrolls. In the 390 px phone run, charts scroll inside their cards with 0 sideways page
  scroll (report §9).
- The scrolling SVG contains its own gutter. The verified build has no sticky gutter overlay. If one is added, it is
  `aria-hidden`, carries `data-export="skip"`, and the export serialises only the scrolling SVG.
- When A4 finds no tier for a labelled panel, its labels are dropped and the card shows, under the SVG:
  "Values don’t fit at this width. The metrics table lists them."

**Text placement** (all text Geist Mono 11; every baseline is a planner number):

| Text | x | Baseline y | Ink |
|---|---|---|---|
| Panel caption | 0, left-aligned | caption band top + 11 | «t.tick» |
| Y tick label | G_L − 8, right-aligned | y(t) + 3.5 (0.32 em) | «t.tick» |
| Bar label, v ≥ 0 | slot centre | drawn bar end − 5 | «t.value» |
| Bar label, v < 0 | slot centre | drawn bar end + 12 | «t.value» |
| `—` / `n/m` (missing bar, growth state) | slot centre | y(0) − 3 | «t.tick» |
| A13b label | slot centre | y(0) − 5 (above) or y(0) + 13 (below) | «t.value» |
| Off-scale arrow, value | left, left + 9; left-aligned | off-scale band top + 10 + 14·row | series colour, «t.value» |
| X tick | slot centre | x-axis band top + 13; second line + 12 | «t.tick» |
| Strip row label | 14, left-aligned (marker centred at x = 6, baseline − 4) | strip band top + 15 + 16·row | «t.tick» |
| Strip cell | slot centre | as the row label | «t.value» |
| "Notes" | 0, left-aligned | notes band top + 12 | «t.tick» |
| Band glyph | slot centre + (k − (n−1)/2) × 8.1 | notes band top + 12 | «t.tick» / «t.review» |

Gridlines are 1 px at `round(y(t)) + 0.5`, from G_L to W − 8: «t.grid», and «t.zero» for the zero tick. The
off-scale edge rule sits at the edge + 0.5.

**L1. Text placement.** Every SVG text box is computed by the planner (monospace arithmetic) and lies inside its
band. Negative offsets, `overflow: visible` text and `textLength` are forbidden.

### 3.8 Theme tokens (chart scope; APCA Lc and WCAG on the card surface)

**Light card `#FBFAF6`, dark card `#1F2937`.** Lc values from `$S/apca_table.txt`.

| Token | Use | Light | Lc / WCAG | Dark | Lc / WCAG | Source |
|---|---|---|---|---|---|---|
| `surface` | Plot background, marker rings, break marks, export fill | `#FBFAF6` | — | `#1F2937` | — | DS |
| `grid` | Non-zero gridlines, 1 px | `#DCD9D0` | 16.8 / 1.35 | `#525C6B` | −15.0 / 2.17 | final (today Lc 0 in both themes) |
| `zero` | The zero tick's gridline, every panel, 1 px | `#6B7280` | 70.5 / 4.63 | `#9CA3AF` | −48.6 / 5.78 | DS `chart.ref` |
| `tick` | Tick labels, x labels, captions, band neutral glyphs, `—`, `n/m`, "Notes", strip row labels, off-scale edge rule, absent-series swatch | `#636A77` | 74.1 / 5.21 | **`#B8BEC7`** (new `chart.label.dark`) | −63.6 / 7.85 | C, final hex (today's dark `#9CA3AF` is −48.6) |
| `value` | Bar labels, A13b labels, off-scale values, strip cells | `#374151` | 90.9 / 9.87 | `#EAECEF` | −91.8 / 12.40 | DS text secondary/primary |
| `review` | Review-kind band letters | `#92400E` | 80.9 / 6.79 | **`#FBBF24`** (new) | −70.2 / 8.79 | B, fixed (DS `#F59E0B` is −56.9, below 60) |
| `s1` teal | Series 1 | `#3E8E84` | 63.0 / 3.72 | **`#62B2A6`** | −49.7 / 5.90 | C (today's dark −32.0) |
| `s2` honey | Series 2 | `#B8812F` | 58.0 / 3.23 | **`#D3A55C`** | −54.2 / 6.51 | C (today's dark −37.1) |
| `s3` cornflower | Series 3 | `#5B7CC0` | 65.2 / 3.95 | **`#8CA6E3`** | −50.9 / 6.07 | C (today's dark −29.9) |
| `s4` coral | Series 4 (not used by these charts) | `#CF7159` | 58.2 / 3.26 | **`#E8927C`** | −51.9 / 6.17 | final (today's dark −36.9) |
| `s5` slate-blue | Series 5 (not used) | `#6E7E9C` | 65.1 / 3.92 | **`#97A6C2`** | −50.1 / 5.98 | final (today's dark −30.0) |
| `s6` periwinkle | Series 6 (not used) | `#8B7BC0` | 61.4 / 3.53 | **`#AFA2DE`** | −52.8 / 6.32 | final (today's dark −33.7) |
| `cursor` | Hover/focus column wash (specified, not yet verified) | rgba(62,142,132,.08) | — | rgba(62,142,132,.16) | — | DS `barCursorProps` |
| `tip` | Tooltip surface and border (specified, not yet verified) | DS `chart.tip` | | DS `chart.tip` | | DS |

**Thresholds.**

| Element | Minimum \|Lc\| |
|---|---|
| Data marks (2 px lines, bars, 6 px markers) and the zero rule | 45 |
| Must-read 11–12 px text (ticks, captions, band letters, subtitle, footnotes, legend names) | 60 |
| Printed values (labels, strip, legend values) | 75 |
| Gridlines | 10–25: visible enough to interpolate, quieter than the zero rule |

**HTML text in the chart card** (from `$S/apca_table.txt`):

| Text | Light | Lc | Dark | Lc |
|---|---|---|---|---|
| Subtitle and footnotes | `text.tertiary #636A77` | 74.1 | `chart.label.dark #B8BEC7` | −63.6 |
| Legend names | `text.secondary #374151` | 90.9 | `text.secondary.dark #D1D5DB` | −77.3 |
| Legend values | `text.primary #1A1A17` | 101.3 | `text.primary.dark #EAECEF` | −91.8 |

The dark subtitle, footnotes and legend names use `chart.label.dark` because DS `text.secondary.dark #9CA3AF`
measures Lc −48.6, which is under 60 for 12 px text.
(2026-10-25: the analysis number system raised DS `text.secondary.dark` app-wide to gray-300 `#D1D5DB`, Lc −77.3
on the slate panel and −80.3 on navy, and gray-400 `#9CA3AF` became `text.tertiary.dark`; see
`frontend/DESIGN_SYSTEM.md` §2. The sentence above records the token as this audit measured it. Whether these
dark texts take the DS secondary ink rather than `chart.label.dark` is the migration's call; this spec is
unchanged until it makes it. The same pull request raised DS `text.primary.dark` from `#D7DADC` to `#EAECEF`,
Lc −91.8 on the slate panel and −94.8 on navy. The legend values row above takes it, since the renderer's legend
values are that token (`charts/theme.ts`'s dark `figure`, held to it by `chart-theme.spec.ts`), as is today's chart
tooltip value ink in `Chart.tsx`. §1 row 10 and the `value` row's dark ink, a chart-scope token of its own, keep
`#D7DADC` as this audit measured it, for the migration to decide.)
(E194, 2026-10-25: the migration's call on the dark names. Legend names take `text.secondary.dark` `#D1D5DB`, Lc
−77.3 on the card, as light's take `text.secondary`, so the chart's text steps match the page's (chief design on
#1609); the row above says so. The subtitle and footnotes keep `chart.label.dark`, since DS `text.tertiary.dark`, the
step their light half takes, is still `#9CA3AF`, −48.6.)
(D-063, 2026-10-25: the founder's call on the `value` row. Dark printed values take the figure ink `#EAECEF`, Lc
−91.8 on the card and −88.5 under the column wash, so every figure the chart prints, in the plot and in the legend,
takes one dark ink, as D-060 chose for the table. Chief design first recommended it on #1620, then withdrew it for
the `chart.value` step #1620 shipped; the founder chose the figure ink. Light keeps its step: printed values in
`text.secondary` under the legend values' `text.primary`. Dark could not follow it, since `text.secondary.dark`
measures −74.0 under the wash, below the printed-value floor of 75. The row above says so; §1 row 10 keeps the audit's
measurement.)

**CVD.** Dark series pairs 1–2 / 1–3 / 2–3 measure deutan 49 / 31 / 80 and protan 41 / 35 / 77 ΔE76. Light measures
deutan 56 / 37 / 93 and protan 49 / 40 / 89. The weakest pair, teal–cornflower, occurs only in three-series charts,
where shapes, legend order and printed values back it up.

**All tokens resolve to literal hex/rgba strings before render.** No `var(--…)` reaches an SVG attribute, so
serialisation cannot lose them.

**Token change list** (the gates that must move together):

1. `tailwind.config.js` `chart.*`:
   - add `chart-1-dark`…`chart-6-dark`, `chart.label.dark` (`#B8BEC7`), `chart.grid` (light `#DCD9D0`, dark
     `#525C6B`) and `chart.review.dark` (`#FBBF24`);
   - add `dark:bg-chart-1-dark` to `features/marketing/components/RevenueBars.tsx`, because a `-dark` sibling makes
     `themePairs.spec.ts` require the twin.
2. The `components/ui/Chart.tsx` `ChartTheme` mirror and the `features/analysis/lib/chartExport.ts` mirror, gated by
   `designTokenParity`.
3. `DESIGN.md` and `.impeccable/design.json`, gated by `designSnapshotParity`.
4. DS §1: the chart row "same hexes".
5. DS §10:
   - rewrite the hollow-marker paragraph as the band;
   - change crosshair to column wash for line charts (when it is built);
   - change "dark labels use secondary" to `chart.label.dark`, for SVG text and for the chart card's HTML subtitle,
     legend names and footnotes;
   - in charts, † marks calculated periods in the band only; fully calculated series get a footnote sentence;
   - add the font-loader note.
6. `app/fonts.ts`: G1.
7. Retire or rewrite the tests `trend-charts-annotation`, `trend-charts-legend` (dual-axis and "(right)" cases) and
   `chart-note-layout`. Delete `features/analysis/lib/chartNoteLayout.ts`.

### 3.9 Tooltip and interaction states

**Hit target and cursor** (specified, not yet verified).

- The hit target is the full slot width × full SVG height for each period.
- Hover or keyboard focus paints the column with `cursor` across both panels and the band. This is a DS change
  (owner sign-off 5).
- There is no positional animation.

**Tooltip content** (specified, not yet verified)

- Header: period and date, e.g. `FY2025 · year ended Dec 31, 2025` or `Q2 FY2026 · quarter ended Jun 30, 2026`.
- Rows in legend order, each with:
  - swatch and shape;
  - name;
  - value (tooltip precision);
  - the word `Calculated` if *this* point is calculated (never †);
  - its own note letters: value notes, and, for the growth row, its comparison notes (DS §10 independence);
  - a state text: `— Unavailable (a)`, `(off scale)`, `n/m — not meaningful`, or
    `— no prior-year period in this window`.
- Revenue & growth has two rows, top line and YoY growth.
- The tooltip is clamped to the viewport, uses a live status, and never appears in exports.

**States**

| State | Behaviour |
|---|---|
| `loading` | Skeleton at the exact final height: header, a 2-line legend, and the 320 px SVG with gridline and bar bones. Static under reduced motion. `aria-busy`. *Specified, not yet verified.* |
| `ready` | As specified. Verified. |
| `partial` | Absent series per §3.4. Verified. |
| `single-point` | n_valued = 1: markers or bars only, no path. Verified (XOM/q; isolated points elsewhere). |
| `not-applicable` | A12 copy, centred, at the full 320 px height. Verified (34 cards). |
| `error` | `ChartErrorBoundary` at the same height, with its own copy: "This chart could not be drawn." (or "These charts could not be drawn." around the grid). *Specified, not yet verified.* |
| `expanded` | §3.10. Verified on the hard cases in both themes (report §7). |
| `exporting` | Button busy; the same SVG is serialised. The export is verified; the busy state is specified, not yet verified. |
| `reduced-motion` | No transitions. The verified build has none. |

**Motion.** A content fade of `duration-base` on the first data paint only. No bar growth and no line draw-in,
because they delay readout and complicate export timing. A theme switch swaps tokens only, with no re-layout.

### 3.10 Expanded view

- It is the same component and the same `buildChartModel` with `view = 'expanded'`: W = grid width, the heights from
  §3.7. Ticks are the card's ticks (A1 is view-independent). It is never a CSS scale, so text stays 11 px.
- **Value strip** for Margins, Cash and Balance:
  - one 16 px row per present series, in legend order, between the x-axis and the band;
  - the left of each row shows the series marker at x = 6 and the legend name's first 6 characters at x = 14, in
    «t.tick»;
  - cells are centred on slots, Geist Mono 11 in «t.value», F$ at the panel's d0 or F%, `—` for missing;
  - it is collision-free by construction (one cell per slot per row); the expanded hard-case renders, which include
    the Balance sheet strip, show 0 collisions (report §7);
  - it answers M1 to ±0.05 pp, C1 and B1 at 100%, and B3 for compressed series (PLUG debt, NEE cash).
- Revenue & growth in expanded: A4 re-plans both panels' labels at the expanded width. It has no strip.
- All footnote lines are shown, as on the card.
- **Interaction.**
  - The expand button toggles the view and carries `aria-expanded` (verified).
  - Specified, not yet verified: Esc or the collapse button returns to the card, with focus back on the expand button
    and the change announced; a quarterly viewport scroll resets to the latest period; height animates with
    `duration-base`/`ease-standard`, and not at all under reduced motion.
  - Export from expanded exports the expanded SVG.

### 3.11 Export-image fidelity (C's E-rules)

1. **Same SVG** (verified). The export serialises **the on-screen SVG node** of the current view at its current CSS
   width, after layout, with no re-render. It rasterises at a **fixed 2×**, never `devicePixelRatio`, onto a canvas
   filled with «t.surface» of the active theme, so no pixel is transparent. A scrolled chart exports its full model
   width. Measured: 0.000% of pixels differ from an element screenshot of the on-screen SVG, in both themes; today's
   method differs on 1.39–2.37% (report §9).
2. **Composition**, top to bottom (*specified, not yet verified*; the verified export is the SVG region alone):
   - 24 px pad;
   - company (Inter 600 18);
   - `TICKER · chart title`;
     - as built (#1627, `frontend/DESIGN_SYSTEM.md` §10), the export carries the period on this line in its own form,
       `TICKER · chart title · FY2016–FY2025`, and in this card's short form (`Q3 ’24–Q4 ’25`) when the long one is
       wider than the strip (the image less its 16 px pads) and the short one fits; otherwise the range takes a line
       of its own in the same size and ink, as a bank's subtitle does on a phone; only a line that still does not
       fit is condensed;
   - subtitle;
   - legend: the same inline items, same strings, same item x positions, drawn on the canvas with `measureText` in
     the page's body font stack;
   - the SVG;
   - every footnote line;
   - `Source: SEC filings via EarningsNerd · data as of {date}`;
   - disclaimer;
   - brand footer.
3. **Fonts** (verified).
   - At serialisation time, the computed font family and fill are written literally onto every `text` and `tspan`.
   - A `<style>` block embeds every `@font-face` rule the SVG uses, with `src` rewritten to a
     `data:font/woff2;base64,…` URI: **both** Geist Mono subsets, latin 23.1 kB plus latin-ext 14.7 kB, about 51 kB
     as base64.
   - Each rule keeps its `unicode-range`. Without it the faces shadow one another and † (latin-ext) falls back to the
     platform font in the image.
   - Draw only after the image has loaded. Canvas text in the composition waits for
     `document.fonts.load('600 18px Inter')`.
   - A load failure aborts the export with a message rather than falling back.
4. **Never in the PNG:** hover wash, focus ring, tooltip, scrollbars.
5. **No export-only drawing path.** If the screen is wrong, the export is wrong in the same way, and the checks catch
   both.

### 3.12 SSR (B, with C's D9)

- `buildChartModel` is pure and SSR-safe, because every text width is `chars × 0.6 em`.
- The server renders the SVG at the default card width (502).
- On mount, a ResizeObserver re-runs the model at the measured width. Only x-dependent planning can change: x
  positions, A4 label tiers, A13b drops and A3b row counts. A3b rows can move the Margins plot inside the SVG; they
  never change H.
- H depends on view and mode only (M8), so the card's height never shifts (D9). Measured on the prototype: the full
  SVG is in the server response, 0 hydration warnings, page CLS ≈ 0.0004 (report §7).
- A font load after hydration cannot reflow, because the advance is identical.

### 3.13 Accessibility

- **Keyboard and screen reader** (specified, not yet verified) follow DS §10: one chart-values stop; Left/Right reads
  each period; a live status; the overflow region only while overflowing; Tab leaves; Shift+Tab returns without a
  trap.
- Each period's announcement includes its state text and band notes, e.g. "FY2021, Long-term debt unavailable,
  note b" (specified, not yet verified).
- **Colour is never the only cue:** marker shapes, legend order, panel captions, printed values and the band.
- Contrast meets the thresholds in §3.8 (measured, `$S/apca_table.txt`).
- Reduced motion is respected.
- The metrics table stays the full-data alternative.

---

## 4. Per-chart specs

### 4.0 Data contract and shared config

```ts
type View = 'card' | 'expanded'
type PointState = 'value' | 'zero' | 'missing' | 'below' | 'above'
type GrowthState = 'value' | 'structural' | 'nm' | 'unavailable'
interface ModelPoint { i: number; period: string; value: number | null; state: PointState
  yPlot: number | null                  // = value, or the clip edge when off-scale (A3)
  stub: boolean                         // bar drawn as the 2 px stub (A13)
  growth?: GrowthState                  // growth series only (A11)
  calculated: boolean; letters: string[]
  text?: string; labelY?: number }      // printed bar label (A4 tier) and its planned baseline
interface ModelSeries { concept: string; label: string; index: 0 | 1 | 2   // A8: colour and shape index over PRESENT series
  color: string; shape: 'circle' | 'square' | 'triangle'; mark: 'bar' | 'growth' | 'signedBar' | 'line'
  allCalculated: boolean; partlyCalculated: boolean; points: ModelPoint[]
  latest: { text: string; period: string | null } }                 // legend value
interface OffItem { period: string; series: string; arrow: '↑' | '↓'; text: string; left: number; row: number }
interface ModelPanel { id: 'main' | 'A' | 'B'; caption?: string; top: number; h: number
  cap: number                                                       // A1 interval cap
  domain: [number, number]; step: number; ticks: number[]; tickText: string[]; unit: 'USD' | 'pct'
  clipped: boolean; T: number; series: ModelSeries[]                // T = frozen tolerance (§1.0)
  labelDecimals: number | null                                      // A4 tier; null = labels dropped
  offAbove?: { top: number; rows: number; items: OffItem[] }        // A3b
  offBelow?: { top: number; rows: number; items: OffItem[] }
  nearZero: { period: string; x: number; y: number; text: string }[] }   // A13b
interface ChartModel {
  chart: 'topline' | 'margins' | 'cash' | 'balance'; view: View; theme: 'light' | 'dark'
  state: 'ready' | 'not-applicable'; reason?: string
  W: number; H: number; GL: number; slot: number; barW: number; growthBarW: number; scroll: boolean
  x: number[]                                                                        // slot centres
  rows: { id: string; top: number; h: number }[]                                     // §3.7 bands
  panels: ModelPanel[]
  band: { i: number; glyphs: { ch: string; x: number; ink: 'tick' | 'review' }[] }[]  // A5
  strip?: { series: string; short: string; cells: string[] }[]                       // expanded only
  ticksX: (string | [string, string])[]
  title: string; subtitle: string
  legend: { label: string; swatch: 'line' | 'bar' | 'absent'; color?: string; shape?: string; latest?: string }[]
  footnotes: string[]                                                                // §3.3, in order
  valuesDontFit: boolean                                                             // A4 dropped a panel's labels
}
```

Shared Vega-Lite config, used by every block:

```jsonc
{
  "config": {
    "view": {"stroke": null}, "padding": 0, "autosize": {"type": "none"},   // the planner owns every pixel
    "font": "«m.fontStack»",                                                // CHART_FONT resolved (G1)
    "axis": {"domain": false, "ticks": false, "title": null, "grid": true,
             "gridColor": {"condition": {"test": "datum.value === 0", "value": "«t.zero»"}, "value": "«t.grid»"},   // the zero rule is the 0 tick's gridline
             "gridWidth": 1,
             "labelFont": "«m.fontStack»", "labelFontSize": 11, "labelColor": "«t.tick»",
             "labelPadding": 8, "labelBound": false},
    "axisY": {"orient": "left", "labelAlign": "right", "labelBaseline": "middle"},   // renderer: baseline y(t) + 3.5 px
    "axisX": {"grid": false},
    "text": {"fontSize": 11},
    "legend": {"disable": true},                                             // the legend is HTML (§3.6)
    "line": {"strokeWidth": 2, "strokeJoin": "round", "strokeCap": "round",
             "interpolate": "linear", "invalid": "break-paths-filter-domains"},   // never join across a missing value
    "point": {"filled": true, "size": 28, "strokeWidth": 1.5, "stroke": "«t.surface»"}   // one size in both views
  },
  "params": [ {"name": "A_ticks", "value": "«m.panels.A.ticks»"}, {"name": "A_text", "value": "«m.panels.A.tickText»"},
              {"name": "B_ticks", "value": "«m.panels.B.ticks»"}, {"name": "B_text", "value": "«m.panels.B.tickText»"} ]
}
```

Rules that hold in every block:

- **x** is `{"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5, "axis": null,
  "scale": {"type": "band", "paddingInner": 0, "paddingOuter": 0}}`. Every mark sits on a slot centre.
- **Zero rule:** the zero tick's gridline in «t.zero», 1 px, drawn with the gridlines and below marks. Zero is
  always a tick (A1).
- **No text halos.** Text boxes are planned clear of marks: labels outside their bar ends, and band, strip and
  off-scale text outside the plot.
- **Planned positions.** Fields named `…Y` or `xLeft` are planner pixels in the view's own coordinates and use
  `"scale": null`.
- **y labels:** `labelExpr: "A_text[indexof(A_ticks, datum.value)]"`. Rendered tick strings and positions are the
  model's; a renderer that generates its own interval ticks fails D11.
- **Renderer-only rules** (Vega-Lite cannot express them):
  - the line clip is the plot rect extended 1 px at the top and bottom; markers are drawn unclipped (only in-domain
    points have markers);
  - gridlines at `round(y(t)) + 0.5`;
  - the exact marker geometry of §3.5 (circle r 3, square 6×6, triangle (x, y − 4), (x + 4, y + 3), (x − 4, y + 3));
  - the break mark (§4.1);
  - the `data-*` attributes: `data-panel`, `data-axis-step`, `data-axis-domain` on panel groups; `data-series`,
    `data-period` on marks and off-scale arrows; `data-v`, `data-zero` on bar rects;
  - per-band y offsets.

  vconcat `spacing` is 0. Each band of §3.7 is its own view, with the band's height.

### 4.1 Revenue & growth

**Encodings and Cleveland–McGill ranks** (1984: 1 position on a common scale; 2 position on non-aligned scales;
3 length, direction, angle; 4 area; 5 volume, curvature; 6 shading, colour saturation):

- **Top line as bars from $0.** The bar end is position on a common scale (rank 1). Length from the zero baseline
  (rank 3) is a redundant cue, valid only because the axis starts at 0. A flow total per period has a meaningful
  zero.
- **Growth as diverging bars on its own aligned 0% rule.** The sign is position relative to a drawn reference
  (rank 1). A line would encode the change *of the growth rate* as slope (direction, rank 3), which nobody asked
  for, and drawing it over the bars is a dual axis.
- **Magnitudes are printed at the mark.** A 75 px growth panel gives about 0.5 px per pp on REGN's 150 pp span, so
  position cannot carry R3; text does. A label at the bar end keeps proximity: the number sits on the encoding it
  annotates, where the eye already is, with no lookup to a row or a legend. The bar keeps the rank-1 sign cue, and
  the label keeps the exact value, including a clipped bar's true value.
- **Hue is identity only.**

```jsonc
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "width": "«m.W − m.GL − 8»", "spacing": 0,
  "data": {"name": "rows"},   // one row per period: i, period, top, topState, topStub, topText, topLabelY,
                              //                     g, gState, gPlot, gStub, gOff, gBreakY, gText, gLabelY
  "resolve": {"scale": {"x": "shared", "y": "independent"}},
  "vconcat": [
    {"height": 4, "mark": {"type": "text", "opacity": 0}},                                       // top pad
    {"height": 14, "mark": {"type": "text", "align": "left", "baseline": "alphabetic", "color": "«t.tick»"},
     "encoding": {"x": {"value": "«−m.GL»"}, "y": {"value": 11}, "text": {"value": "«m.panels.A.caption»"}}},   // Revenue | Net interest income | Premiums earned
    {"height": "«14 + m.panels.A.h + 8»", "name": "panelA",                                      // 14 px label pad above, 8 px tick pad below
     "encoding": {"x": {"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5,
                        "axis": null, "scale": {"type": "band", "paddingInner": 0, "paddingOuter": 0}}},
     "layer": [
       {"transform": [{"filter": "datum.topState === 'value' && !datum.topStub"}],
        "mark": {"type": "bar", "width": "«m.barW»", "color": "«m.series[0].color»", "cornerRadius": 2},
        "encoding": {"y": {"field": "top", "type": "quantitative",
                           "scale": {"domain": "«m.panels.A.domain»", "nice": false, "zero": true, "range": ["«14 + m.panels.A.h»", 14]},
                           "axis": {"values": {"expr": "A_ticks"}, "labelExpr": "A_text[indexof(A_ticks, datum.value)]"}},
                     "y2": {"datum": 0}}},
       // zero, or 0 < true length < 2 px: a 2 px stub anchored ON the zero rule, above it (the top line is never negative) (A13)
       {"transform": [{"filter": "datum.topState === 'zero' || datum.topStub"}],
        "mark": {"type": "rect", "width": "«m.barW»", "height": 2, "color": "«m.series[0].color»", "cornerRadius": 2},
        "encoding": {"y": {"datum": 0, "type": "quantitative"}, "yOffset": {"value": -1}}},
       // value labels at the A4 tier; baseline = drawn bar end − 5 (planner); no halo
       {"transform": [{"filter": "datum.topText !== null"}],
        "mark": {"type": "text", "align": "center", "baseline": "alphabetic", "color": "«t.value»"},
        "encoding": {"y": {"field": "topLabelY", "type": "quantitative", "scale": null}, "text": {"field": "topText"}}},
       // missing: an em dash 3 px above the zero rule; never an empty slot
       {"transform": [{"filter": "datum.topState === 'missing'"}],
        "mark": {"type": "text", "text": "—", "baseline": "alphabetic", "dy": -3, "color": "«t.tick»"},
        "encoding": {"y": {"datum": 0, "type": "quantitative"}}}
     ]},
    {"height": "«m.gap»", "mark": {"type": "text", "opacity": 0}},                               // 10 card / 16 expanded
    {"height": 14, "mark": {"type": "text", "align": "left", "baseline": "alphabetic", "color": "«t.tick»"},
     "encoding": {"x": {"value": "«−m.GL»"}, "y": {"value": 11}, "text": {"value": "YoY growth"}}},
    {"height": "«14 + m.panels.B.h + 14»", "name": "panelB",                                     // 14 px label pads above and below
     "encoding": {"x": {"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5, "axis": null}},
     "layer": [
       {"transform": [{"filter": "datum.gState === 'value' && !datum.gStub"}],
        "mark": {"type": "bar", "width": "«m.growthBarW»", "color": "«m.series[1].color»", "clip": true},
        "encoding": {"y": {"field": "gPlot", "type": "quantitative",            // gPlot = g clamped to the domain (A3)
                           "scale": {"domain": "«m.panels.B.domain»", "nice": false, "zero": true, "range": ["«14 + m.panels.B.h»", 14]},
                           "axis": {"values": {"expr": "B_ticks"}, "labelExpr": "B_text[indexof(B_ticks, datum.value)]"}},
                     "y2": {"datum": 0}}},
       // growth of exactly 0, or true length < 2 px: a 2 px stub anchored ON the 0% rule, on the value's side (A13)
       {"transform": [{"filter": "datum.gState === 'value' && datum.gStub"}],
        "mark": {"type": "rect", "width": "«m.growthBarW»", "height": 2, "color": "«m.series[1].color»"},
        "encoding": {"y": {"datum": 0, "type": "quantitative"}, "yOffset": {"expr": "datum.g < 0 ? 1 : -1"}}},
       // clipped bar: break mark in «t.surface» starting 6 px inside the clipped end (renderer path from the model)
       {"transform": [{"filter": "datum.gOff !== 0"}],
        "mark": {"type": "point", "shape": "«m.breakPath»", "filled": false, "stroke": "«t.surface»", "strokeWidth": 1.5},
        "encoding": {"y": {"field": "gBreakY", "type": "quantitative", "scale": null}}},
       // signed labels at the A4 tier: above the end for g ≥ 0, below for g < 0; a clipped bar prints its TRUE value
       {"transform": [{"filter": "datum.gText !== null"}],
        "mark": {"type": "text", "align": "center", "baseline": "alphabetic", "color": "«t.value»"},
        "encoding": {"y": {"field": "gLabelY", "type": "quantitative", "scale": null}, "text": {"field": "gText"}}},
       // structural or unavailable → "—"; n/m → "n/m"; 3 px above the 0% rule, «t.tick»
       {"transform": [{"filter": "datum.gState !== 'value'"}],
        "mark": {"type": "text", "align": "center", "baseline": "alphabetic", "dy": -3, "color": "«t.tick»"},
        "encoding": {"y": {"datum": 0, "type": "quantitative"},
                     "text": {"condition": {"test": "datum.gState === 'nm'", "value": "n/m"}, "value": "—"}}}
     ]},
    {"height": "«m.xAxisH»", "name": "xTicks",                                // 20 annual / 32 quarterly
     "mark": {"type": "text", "baseline": "alphabetic", "lineHeight": 12, "color": "«t.tick»"},
     "encoding": {"x": {"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5, "axis": null},
                  "y": {"value": 13}, "text": {"field": "tick"}}},           // ["Q2","’26"] renders on two lines
    {"height": 16, "name": "notesBand",                                       // A5
     "layer": [
       {"data": {"name": "bandGlyphs"},                                       // one row per glyph: x (SVG px − m.GL), ch, ink
        "mark": {"type": "text", "align": "center", "baseline": "alphabetic"},
        "encoding": {"x": {"field": "x", "type": "quantitative", "scale": null}, "y": {"value": 12}, "text": {"field": "ch"},
                     "color": {"field": "ink", "type": "nominal", "scale": {"domain": ["tick", "review"], "range": ["«t.tick»", "«t.review»"]}}}},
       {"data": {"values": "«m.bandNonEmpty ? [{}] : []»"},
        "mark": {"type": "text", "align": "left", "baseline": "alphabetic", "text": "Notes", "color": "«t.tick»"},
        "encoding": {"x": {"value": "«−m.GL»"}, "y": {"value": 12}}}          // SVG x = 0
     ]},
    {"height": 4, "mark": {"type": "text", "opacity": 0}}
  ]
}
```

**Break mark** (renderer path). Two 1.5 px «t.surface» strokes across the bar, each from x − w/2 − 1 to
x + w/2 + 1: one from y_b + 2 up to y_b − 1, one from y_b + 5 up to y_b + 2. y_b is the bar top + 6 for a bar clipped
at the top, and the bar bottom − 9 for a bar clipped at the bottom.

**Tooltip** (specified, not yet verified): two rows, top line (4 s.f.) and YoY growth (1 dp, or its state text),
each with its own letters.

**A4. Bar-label tier** (one tier per panel; the top-line panel and the growth panel each run it)

```
tiers = USD panel: [d0, d0 − 1, …, 0]       d0 = decimals giving 3 s.f. on the panel's largest |v| (F$)
        growth panel: [1, 0]
for d in tiers:
    for every valued point:
        text = F$(v, d) with the own-unit fallback, or F±(v, d)             // |g| ≥ 1,000 → 0 dp in either tier
        end  = y(clamp(v, domain));  w = 6.6 · len(text)
        box  = [x − w/2, x + w/2] × (v ≥ 0 ? [end − 15, end − 3] : [end + 3, end + 15])
    if every box lies inside [0, W] horizontally
       and every pair of boxes is ≥ 2 px apart in x or ≥ 2 px apart in y:  use d for the whole panel; stop
if no tier passes: no labels in this panel, and the card shows
    "Values don’t fit at this width. The metrics table lists them."
renderer: label baseline = drawn bar end − 5 (v ≥ 0) or drawn bar end + 12 (v < 0); for a stub, the stub's far end
```

Vertically, labels sit in the 14 px label pads (above panel A; above and below panel B), so they cannot leave the
SVG. Measured: 0 text collisions in 566 rendered cards; on the card the growth tier is 1 dp in 33/35 annual and 11/35
quarterly panels (gallery).

### 4.2 Margins

**Encodings.** Lines with a marker at every valued point, on one common scale. Level and order are position
(rank 1). Expansion and compression are slope (direction, rank 3), backed by marker positions (rank 1). Markers make
the 32 isolated points in 17 datasets visible (C's count). Linear interpolation only. An off-scale value keeps its
line's direction (the segment runs toward it and is cut at the edge) and its number is printed at that edge.

```jsonc
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "width": "«m.W − m.GL − 8»", "spacing": 0,
  "data": {"name": "long"},                       // one row per (series, period): i, period, series, index, v, state
  "vconcat": [
    {"height": 8, "mark": {"type": "text", "opacity": 0}},                                       // top pad
    {"height": "«m.panels.main.offAbove ? 14 * m.panels.main.offAbove.rows + 4 : 0»", "name": "offAbove",   // A3b
     "data": {"name": "offAboveItems"},                                       // period, index, arrow '↑', text, xLeft (= left − m.GL), baseline (10 + 14·row)
     "layer": [
       {"mark": {"type": "text", "align": "left", "baseline": "alphabetic"},
        "encoding": {"x": {"field": "xLeft", "type": "quantitative", "scale": null},
                     "y": {"field": "baseline", "type": "quantitative", "scale": null}, "text": {"field": "arrow"},
                     "color": {"field": "index", "type": "nominal", "scale": {"domain": [0, 1, 2], "range": "«m.seriesColors»"}}}},
       {"mark": {"type": "text", "align": "left", "baseline": "alphabetic", "dx": 9, "color": "«t.value»"},
        "encoding": {"x": {"field": "xLeft", "type": "quantitative", "scale": null},
                     "y": {"field": "baseline", "type": "quantitative", "scale": null}, "text": {"field": "text"}}}
     ]},
    {"height": "«8 + m.panels.main.h + 8»", "name": "plot",                                      // 8 px tick pads
     "encoding": {"x": {"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5, "axis": null,
                        "scale": {"type": "band", "paddingInner": 0, "paddingOuter": 0}},
                  "color": {"field": "index", "type": "nominal", "scale": {"domain": [0, 1, 2], "range": "«m.seriesColors»"}}},
     "layer": [
       // A3b: dashed «t.tick» rule on each clipped edge, over that edge's gridline
       {"data": {"values": "«m.panels.main.offEdges»"},                       // [{edge: domain[1]}] and/or [{edge: domain[0]}]
        "mark": {"type": "rule", "strokeWidth": 1, "strokeDash": [2, 2]},
        "encoding": {"y": {"field": "edge", "type": "quantitative"}, "color": {"value": "«t.tick»"}}},
       // true values; off-scale segments run toward the true value and are cut by the clip (+1 px)
       {"mark": {"type": "line", "clip": true},
        "encoding": {"y": {"field": "v", "type": "quantitative",
                           "scale": {"domain": "«m.panels.main.domain»", "nice": false, "zero": true, "range": ["«8 + m.panels.main.h»", 8]},
                           "axis": {"values": {"expr": "A_ticks"}, "labelExpr": "A_text[indexof(A_ticks, datum.value)]"}},
                     "detail": {"field": "series"}}},
       // markers on valued and zero points only: an off-scale point ('below'/'above') has no marker
       {"transform": [{"filter": "datum.state === 'value' || datum.state === 'zero'"}],
        "mark": {"type": "point"},
        "encoding": {"y": {"field": "v", "type": "quantitative"},
                     "shape": {"field": "index", "type": "nominal", "scale": {"domain": [0, 1, 2], "range": ["circle", "square", "triangle-up"]}}}}
     ]},
    {"height": "«m.panels.main.offBelow ? 14 * m.panels.main.offBelow.rows + 4 : 0»", "name": "offBelow"
     /* as offAbove, with offBelowItems and arrow '↓' */},
    {"height": "«m.xAxisH»", "name": "xTicks" /* as §4.1 */},
    {"height": "«m.view === 'expanded' ? 6 + 16 * m.strip.length : 0»", "name": "valueStrip",   // §3.10
     "layer": [
       {"data": {"name": "stripCells"},                                       // series, index, i, period, text, baseline (15 + 16·row)
        "mark": {"type": "text", "align": "center", "baseline": "alphabetic", "color": "«t.value»"},
        "encoding": {"x": {"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5, "axis": null},
                     "y": {"field": "baseline", "type": "quantitative", "scale": null}, "text": {"field": "text"}}},
       {"data": {"name": "stripRows"},                                        // index, short (6 chars), baseline
        "layer": [
          {"mark": {"type": "point"},                                         // row marker centred at SVG x = 6, baseline − 4
           "encoding": {"x": {"value": "«6 − m.GL»"}, "y": {"field": "markerY", "type": "quantitative", "scale": null},
                        "color": {"field": "index", "type": "nominal", "scale": {"domain": [0, 1, 2], "range": "«m.seriesColors»"}},
                        "shape": {"field": "index", "type": "nominal", "scale": {"domain": [0, 1, 2], "range": ["circle", "square", "triangle-up"]}}}},
          {"mark": {"type": "text", "align": "left", "baseline": "alphabetic", "color": "«t.tick»"},
           "encoding": {"x": {"value": "«14 − m.GL»"}, "y": {"field": "baseline", "type": "quantitative", "scale": null}, "text": {"field": "short"}}}
        ]}
     ]},
    {"height": 16, "name": "notesBand" /* as §4.1; never carries ↓/↑ */},
    {"height": 4, "mark": {"type": "text", "opacity": 0}}
  ]
}
```

- **Legend, REGN annual** (REGN has no gross-margin series, so it is not listed):
  `● Operating 24.9%  ■ Net 31.4%`. In-order colours: operating teal (circle), net honey (square).
  Footnote: `Operating and Net margin are calculated by EarningsNerd from reported figures.`
- **LCID annual legend:** `● Gross 22.8% (FY2020)  ■ Operating −258.7%  ▲ Net −199.3%`.
- **Off-scale, LCID annual:**
  - axis −600…+100% in every view;
  - an off-scale band below the plot with six items at FY2019–21 (§3.4, A3b);
  - footnote `↓↑  Values beyond the axis range are printed in the band at the plot edge.`;
  - the notes band carries no arrow.

### 4.3 Cash generation

The structure is identical to §4.2 (folded `operating_cash_flow`, `free_cash_flow`, `net_income`; `unit: 'USD'`;
F$ strip at the panel's d0), without the off-scale bands. The differences:

```jsonc
{ "vconcat": [ {"height": 8}, {"name": "plot", "height": "«8 + m.panels.main.h + 8»", "layer": [
    {"mark": {"type": "line", "clip": true},
     "encoding": {"y": {"field": "v", "type": "quantitative",
                        "scale": {"domain": "«m.panels.main.domain»", "nice": false, "zero": true, "range": ["«8 + m.panels.main.h»", 8]},   // A1 over all three series, cap 8; NEVER clipped
                        "axis": {"values": {"expr": "A_ticks"}, "labelExpr": "A_text[indexof(A_ticks, datum.value)]"}},
                  "detail": {"field": "series"}}},
    {"transform": [{"filter": "datum.state === 'value' || datum.state === 'zero'"}],
     "mark": {"type": "point"},
     "encoding": {"y": {"field": "v", "type": "quantitative"},
                  "shape": {"field": "index", "type": "nominal", "scale": {"domain": [0, 1, 2], "range": ["circle", "square", "triangle-up"]}}}} ] },
  {"name": "xTicks"}, {"name": "valueStrip"}, {"name": "notesBand"}, {"height": 4} ] }
```

- **Encoding rationale.** C1 becomes "which of two markers in this column is higher" on one common scale (rank 1).
  The dual axis it replaces contradicted the true order in 29% of pairs.
- **Legend, REGN:** `● Operating CF $4.98B  ■ Free cash flow $4.08B  ▲ Net income $4.50B`.
  Footnote: `Free cash flow is calculated by EarningsNerd from reported figures.`
- **Banks, MET and NEE** (FCF absent in 13 datasets): FCF is not listed, and NI takes chart-2 honey. JPM annual:
  `● Operating CF −$148B  ■ Net income $57B`.

### 4.4 Balance sheet

**Encodings.**

- Panel A puts debt and cash on a common scale (rank 1), so B1 is a direct order judgement.
- Panel B places equity on its own aligned, zero-anchored scale. Bars from the zero rule make the sign
  pre-attentive. Bar end is rank 1 within the panel. Comparing it across panels is rank 2 and explicitly not a
  task.
- The different mark type (bars against lines) and the panel captions mark panel B as a different measure.
- **When position fails, text carries the reading.** Below 2 px a bar reads only as "about zero"; it cannot show sign
  or size. A13b prints the value beside the stub, at the mark, so BYND −$997K and PLUG −$3.6M are read, not guessed.

```jsonc
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "width": "«m.W − m.GL − 8»", "spacing": 0,
  "resolve": {"scale": {"x": "shared", "y": "independent"}},
  "vconcat": [
    {"height": 4, "mark": {"type": "text", "opacity": 0}},
    {"height": 14, "mark": {"type": "text", "align": "left", "baseline": "alphabetic", "color": "«t.tick»"},
     "encoding": {"x": {"value": "«−m.GL»"}, "y": {"value": 11}, "text": {"value": "«m.panels.A.caption»"}}},   // Long-term debt and Cash | Cash
    {"height": "«8 + m.panels.A.h + 8»", "name": "panelA", "data": {"name": "longA"},
     "encoding": {"x": {"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5, "axis": null},
                  "color": {"field": "index", "type": "nominal", "scale": {"domain": [0, 1, 2], "range": "«m.seriesColors»"}}},
     "layer": [
       {"mark": {"type": "line", "clip": true},
        "encoding": {"y": {"field": "v", "type": "quantitative",
                           "scale": {"domain": "«m.panels.A.domain»", "nice": false, "zero": true, "range": ["«8 + m.panels.A.h»", 8]},
                           "axis": {"values": {"expr": "A_ticks"}, "labelExpr": "A_text[indexof(A_ticks, datum.value)]"}},
                     "detail": {"field": "series"}}},
       // LTD = 0 (14 points): an ordinary marker ON the zero rule; missing LTD: no marker, path break, band letter
       {"transform": [{"filter": "datum.state === 'value' || datum.state === 'zero'"}],
        "mark": {"type": "point"},
        "encoding": {"y": {"field": "v", "type": "quantitative"}, "shape": {"field": "index", "type": "nominal",
                     "scale": {"domain": [0, 1, 2], "range": ["circle", "square", "triangle-up"]}}}}
     ]},
    {"height": "«m.gap»", "mark": {"type": "text", "opacity": 0}},                               // 10 card / 16 expanded
    {"height": 14, "mark": {"type": "text", "align": "left", "baseline": "alphabetic", "color": "«t.tick»"},
     "encoding": {"x": {"value": "«−m.GL»"}, "y": {"value": 11}, "text": {"value": "Shareholders’ equity"}}},
    {"height": "«8 + m.panels.B.h + 8»", "name": "panelB", "data": {"name": "equity"},           // i, period, v, state, stub, nzText, nzY
     "encoding": {"x": {"field": "period", "type": "ordinal", "sort": {"field": "i"}, "bandPosition": 0.5, "axis": null}},
     "layer": [
       {"transform": [{"filter": "datum.state === 'value' && !datum.stub"}],
        "mark": {"type": "bar", "width": "«m.barW»", "color": "«m.panels.B.series[0].color»", "cornerRadius": 2},
        "encoding": {"y": {"field": "v", "type": "quantitative",
                           "scale": {"domain": "«m.panels.B.domain»", "nice": false, "zero": true, "range": ["«8 + m.panels.B.h»", 8]},
                           "axis": {"values": {"expr": "B_ticks"}, "labelExpr": "B_text[indexof(B_ticks, datum.value)]"}},
                     "y2": {"datum": 0}}},
       // A13: zero, or 0 < true length < 2 px → 2 px stub anchored ON the zero rule, on the value's side (BYND FY2025 −$997K: 2 px DOWN)
       {"transform": [{"filter": "datum.state === 'zero' || datum.stub"}],
        "mark": {"type": "rect", "width": "«m.barW»", "height": 2, "color": "«m.panels.B.series[0].color»", "cornerRadius": 2},
        "encoding": {"y": {"datum": 0, "type": "quantitative"}, "yOffset": {"expr": "datum.v < 0 ? 1 : -1"}}},
       // A13b: a non-zero stub prints its compact value beside the zero rule (planner gives the text and baseline, or drops it)
       {"transform": [{"filter": "datum.nzText !== null"}],
        "mark": {"type": "text", "align": "center", "baseline": "alphabetic", "color": "«t.value»"},
        "encoding": {"y": {"field": "nzY", "type": "quantitative", "scale": null}, "text": {"field": "nzText"}}},
       {"transform": [{"filter": "datum.state === 'missing'"}],
        "mark": {"type": "text", "text": "—", "baseline": "alphabetic", "dy": -3, "color": "«t.tick»"},
        "encoding": {"y": {"datum": 0, "type": "quantitative"}}}
     ]},
    {"height": "«m.xAxisH»", "name": "xTicks" /* as §4.1 */},
    {"height": "«m.view === 'expanded' ? 6 + 16 * m.strip.length : 0»", "name": "valueStrip" /* as §4.2: debt, cash, equity rows */},
    {"height": 16, "name": "notesBand" /* as §4.1 */},
    {"height": 4, "mark": {"type": "text", "opacity": 0}}
  ]
}
```

**A13 and A13b. Minimum bar length and near-zero labels**

```
A13   every bar (top line, growth, equity), with y0 = y(0):
        h   = max(2, |y(clamp(v)) − y0|)
        top = v ≥ 0 ? y0 − h : y0                    // anchored AT the zero rule, on the value's side; never straddles it
        a stub is distinct from '—', which means missing
A13b  equity bars with v ≠ 0 and |y(v) − y0| < 2:
        text = compact$(v)                            // 2 s.f., own unit: −$3.6M, $85M, $997K
        side = above if y0 − panelTop ≥ 14, else below   // one side per panel
        baseline = y0 − 5 (above) or y0 + 13 (below); centred on the slot
        drop the label if 6.6·len(text) > slot − 2,
             or if its left edge is less than 2 px from the previous printed label's right edge
        a dropped value stays in the strip and the tooltip
```

A13b fires on 11 points in 7 datasets. An exact zero draws the plain stub with no A13b label; its `$0` is in the
strip.

- **Legend, REGN:** `● Long-term debt $1.99B  ■ Cash $3.12B  ▮ Equity $31.3B`.
- **Absent LTD** (ISRG, DECK, JPM …): `┄ Long-term debt — not in dataset  ● Cash $3.37B  ▮ Equity $17.8B` (ISRG
  annual: cash takes chart-1 teal, equity chart-2 honey). Footnote:
  `Long-term debt isn’t in this dataset for this window (not shown as $0).`
- **MNST/a:** `Long-term debt $0.37B (FY2024)`. **PLUG/a:** `Long-term debt $3.90M (FY2023)`. **BYND/a:** `Equity −$997K`.
- **PLUG annual equity:** A1b domain −$0.2B…$6B; the sub-2 px bars print `−$3.6M` (FY2018), `$85M` and so on above
  the zero rule.

### 4.5 Algorithms Vega-Lite cannot express (run inside `buildChartModel`, in this order)

| Id | Algorithm | Where |
|---|---|---|
| A11 | Point, series and growth state classification | §3.4 |
| A12 | Chart applicability and the not-applicable reason | §3.6 |
| A8 | Colour and shape index over present series | §3.5 |
| A3 | Percent outlier clip (margins, growth): sets `yPlot` and the `below`/`above` states | §3.4 |
| A1 / A1b | Domain, step and ticks per panel from in-range values and the panel's fixed interval cap; small-crossing room | §3.1 |
| A2 | Unit and decimals per axis; tick text; left gutter G_L | §3.1 |
| A7 | Width, slot and scroll (minimum slot 36 px; a labelled chart up to 42 px) | §3.7 |
| A3b | Off-scale band: items, rows and positions at each clipped edge | §3.4 |
| A6 | Layout bands: panel tops and heights from view, mode, chart and off-scale rows | §3.7 |
| A4 | Bar-label tier per panel (top line: d0 down to 0; growth: 1, 0), tested in 2-D | §4.1 |
| A13 / A13b | 2 px minimum bar anchored at the zero rule on the value's side; near-zero equity labels | §4.4 |
| A5 | Band glyph assembly, per-glyph x and ink | §3.3 |
| A9 | FY-end text | §3.6 |
| A10 | Inline legend: items in canonical order, wrapping by whole items | §3.6 |
| — | Tolerance T per panel (§1.0); frozen tolerance file (M20) | §1.0 |
| — | Clip +1 px, gridline +0.5 px, break mark, marker geometry, `data-*` attributes | §4.0, §4.1 |

---

## 5. What it prevents

### 5.1 The user's screenshot defects

| Defect (evidence) | Rule that prevents it | Check |
|---|---|---|
| **"Fiscal year" axis title clipped**: the descender is cut, so it reads "Fiscal vear" (`$S/test_current/REGN_annual_light_balance-sheet.png`; 556/556 charts; label box y = 213 + 14 > SVG height 224) | There is no axis title in the SVG. Its meaning moves to the HTML subtitle with the real FY-end month (A9). L1: every SVG text box is planned inside a band of known height; no offset text. | D1, M8 |
| **Coloured right-axis spine and "Equity" or "Net income" head tag that read as a data bar**: a honey vertical bar at the right edge reads as a FY2025 bar (REGN balance and cash); the tag collides with the top tick in 298/298 dual-axis charts | D1: no right axis, no axis domain lines, no tick marks, no tags. Series colours may appear only on data-bound marks, off-scale arrows and swatches (§3.5). All tick labels sit in the left gutter. | D4, D5, M10 |
| **Stacked "a" markers on the lines**: hollow rings and letters above and below lines that touch at FY2023 (`$S/gallery_regnpn/REGNPN_annual_light_margins.png`, `…cash-generation.png`) | §3.3: no note glyph inside any plot rect. One union cell per period, so REGNPN gets one `a` per period. Footnote lines name the series and periods. `chartNoteLayout.ts` is deleted. | D3, M7 |
| **A large "†" beside a big KPI number**, flagged as confusing and too similar to a dollar figure | G6: † appears only as a notes-band cell glyph, at periods where a partly calculated series was calculated. A fully calculated series gets a plain footnote sentence and no symbol. No † follows a name, legend item, caption or number; the regex also runs on the KPI strip. | M12 |

### 5.2 Measured defects in the brief

| Brief defect | Rule | Check |
|---|---|---|
| Dual axes misorder 29% / 28% of pairs; REGN FY2025 FCF drawn above NI; 165 + 154 false crossings | D1, D4, D5 | M10 (0 false orderings) |
| 0% growth floats mid-plot while $0 is the floor | D2: own panel with a drawn 0% rule | M2 |
| Non-uniform ticks with dataMax appended (352/598); mixed M/B (182); "$0.00" (870); nonsense ticks "$995.0M, −$5.0M" | A1, A1b, A2 | M1–M3 |
| "−19,500.0%" (73 px) in a 56 px gutter loses its minus; "3,000.0%" in a 48 px band | A2 gutter; A3 clips LCID and RIVN | M5, D1 |
| LCID margins flattened by −18,093%; RIVN growth by +2,915% | A3, with exact values at the plot edge (A3b), on the growth bar labels and in the strip | M11, M7 |
| Missing debt drawn like a rise from $0; missing revenue as a blank slot (PLUG FY2020) | §3.4: missing = path break or `—` plus a band letter; zero = marker on the zero rule or a 2 px stub | M7, M13 |
| Missing YoY (first period / first 4 quarters) blank or read as 0 | A11 plus a printed `—` or `n/m` on the 0% rule; footnote lines | M18, readout Q0 |
| Insurers lose the top-line chart; the grid reflows | Top-line chain, 70/73; fixed-height not-applicable card | M17 |
| Gridlines invisible (Lc 0 in both themes); dark labels Lc −48.6; dark series Lc −30…−37 | §3.8 tokens (grid 16.8 / −15.0; dark tick and dark HTML chart text −63.6; dark series −49.7…−54.2) | D6 |
| Export draws a fallback font (`$S/font_compare.png`) | G1 loader fix; E-rule 3 embeds both subsets with their `unicode-range` | E5, D8 |
| "Unavailable for FY…" sentence and "Notes a" chip disconnected from the points | Band cells in the same column as the point; footnote lines | M7 |
| Isolated points invisible (32 in 17 datasets) | A marker on every valued point | D7 |
| Sub-2 px stubs drawn on the wrong side of zero (found by the blind readout: REGN FY2025 growth +1.0% drawn below 0%; PLUG $85M and $70M equity stubs straddled zero) | A13: stubs anchored at the zero rule on the value's side | M21, D14 |

### 5.3 Defects the judges found in the proposals, and the fix in this spec

| Judge finding (proposal) | Status here |
|---|---|
| A: growth nmax = 3 leaves 9 panels < 55% filled (NVDA/a, KO/q, LOVE/a, NEE/a) | **Fixed differently.** Growth cap 4 intervals with nmin 2 (A1); fill measured in the report §9. |
| A: "−$1,000M" ticks (BYND equity, 6 panels) | **Fixed.** Unit from max\|tick\| (A2); BYND equity reads `−$1.0B … $0.5B`. |
| A: export loses † and U+2009 (latin subset only) | **Fixed.** Both subsets embedded with their `unicode-range` and preloaded; U+2009 banned (G2, G3, E-rule 3). |
| A: off-scale value text can run past the SVG | **Fixed.** Off-scale values print in a planned band at the plot edge, each item clamped inside [1, W − 1] (A3b); growth labels must pass A4's [0, W] test. |
| A: LOVE "fiscal years end Feb" | **Fixed.** A9 rollback: LOVE Jan, CPRT Jul, SBUX Sep. |
| A: ordinal exemption ≥ 2τ leaves REGN FY2025 out of scope; 29% of FCF–NI pairs out | **Fixed.** Scored where gap > T; REGN in scope; the out-of-scope count is measured in the report §9. |
| A: colour slots skip silently (DS conflict) | **Fixed.** In order over present series (A8), which is DS-compliant. |
| A: 0.15·step on 21 px gridlines is below the 4 px human floor | **Fixed.** T includes the 4 px floor. |
| A: RIVN FY2020–21 growth labelled structural; no n/m state | **Fixed.** A11 zero-base → `n/m`. |
| A: "290× (LCID)" | **Corrected** to 340×. |
| A: card +96 px and bar labels reverse an owner decision | **Flagged** as owner sign-offs 1 and 4. |
| A: near-zero equity bars invisible (BYND −$997K = 0.06 px) | **Fixed.** A13 2 px stub anchored at zero, plus the A13b printed value (11 points, 7 datasets). |
| A: "3 s.f. in 35/35" overstated with a panel unit (LCID "<$0.01B", RIVN "$0.06B") | **Fixed.** One tier per panel in the panel's unit (A4), with the own-unit fallback for any value under 2 s.f. (LCID `$4.59M`). |
| A: union band loses value-vs-YoY attribution | **Mitigated by decision.** Footnote lines list value and YoY comparison references separately (`Revenue YoY FY2024`); tooltip rows per DS §10 (specified, not yet verified). |
| A: REGN margins legend example lists a gross margin REGN does not have; ◆ shape contradicts s1 = circle | **Fixed.** §4.2 example; shapes by index (circle, square, triangle). |
| A: crosshair → column wash done silently | **Flagged** as owner sign-off 5 and listed in the DS §10 change list; specified, not yet verified. |
| B: clip rule hides real and latest values (PLUG FY2024–25, BYND q, SNAP FY2016/18, RIVN FY2022); 19 knife-edge decisions; self-contradiction on PLUG/a | **Rule not adopted** (A3 used). |
| B: export is a 1200 px layout that never equals the screen | **Rule not adopted** (§3.11). |
| B: structural and missing growth drawn blank | **Fixed.** `—` / `n/m` printed on the 0% rule. |
| B: growth direction exempt for 71/562 values | **Fixed.** The sign is printed on every valued growth bar's label. |
| B: coarse ticks; 124/417 panels with gridlines < 20 px | **Changed.** View-independent ticks need fixed caps, so gridlines are ≥ h/cap apart: ≥ 17 px, the smallest being the quarterly card growth panel (70 px / 4). T's 4 px floor covers the tighter grids. |
| B: table strings (hyphen-minus, "$0.00") inside the chart | **Fixed.** One chart formatter; numeric agreement check M15. |
| B: dark series at Lc −45.1…−45.6 | **Fixed.** C's dark series, −49.7…−54.2. |
| B: ▲▼ in the export subset; Geist Mono lacks them | **Fixed.** G2 bans them; ↑↓ are in latin. |
| B: "bar length rank 1–2" | **Corrected.** Length is rank 3; bar end is position (rank 1). |
| B: FY caption wrong in 34/37 quarterly datasets | **Fixed.** A9 reads the latest FY or Q4 row. |
| B: not-applicable copy hard-codes banks | **Fixed.** A12, reason-specific. |
| B: dark review ink `#F59E0B` at Lc −56.9 | **Fixed.** `#FBBF24`, Lc −70.2. |
| B: ±1 pp margins met in 27/59 even expanded | **Fixed.** Strip, 59/59. |
| C: PLUG/q clip on a knife edge (ratio 1.001); RIVN FY2022 hidden | **Rule not adopted** (A3: PLUG/q and RIVN FY2022 on scale). |
| C: colours move between companies | **Accepted trade-off** (§0.2), owner option 6. |
| C: band height 0–45 px; cards misalign by up to 57 px | **Fixed.** Fixed 16 px union band. |
| C: ±0.25·step tolerance passes today's charts; REGN FY2025 exempt | **Fixed.** T formula and frozen T. |
| C: FY suffix dropped for 52/53-week filers | **Fixed.** A9. |
| C: dark grid `#374151` at Lc 0 | **Fixed.** `#525C6B`, Lc −15.0. |
| C: YoY row slack 0.3 px; 0.61 em fallback overflows | **No longer applies.** There is no YoY row (§0.4 #1). Layout always computes at 0.600 em; growth labels keep ≥ 2 px in 2-D (A4); D8 fails loudly if the advance differs. |
| C: growth text only; RIVN zero base mis-footnoted | **Fixed.** Bars kept and labelled, plus n/m. |
| C: no server-rendered chart | **Fixed.** §3.12. |
| C: G1 bans `var(--font-geist-mono)` (DS §12.3) | **Fixed.** var kept first; fallback fixed in `app/fonts.ts`. |
| C: YoY loss ink `#FDA4AF` outside the palette; tone policy | **Fixed.** Neutral «t.value» ink for every label; sign by glyph and bar direction. |
| C: `themePairs` claim wrong | **Fixed.** Token change list names `designTokenParity` and `designSnapshotParity`, and the RevenueBars twin. |
| C: A8 sticky gutter conflicts with E-rule 2 | **Fixed.** The scrolling SVG has its own gutter; the verified build has no overlay, and any overlay is skipped in export. |
| C: keeps the "Notes" chip it lists as a defect | **Fixed.** Chip removed. |

---

## 6. Machine-checkable acceptance checklist (gallery failure checklist)

Run scope:

- **Model checks:** 73 datasets × 4 charts × {card, expanded} × {light, dark}.
- **DOM and export checks:** the gallery (73 datasets plus REGNPN), both modes and both themes, card and expanded,
  at 1280×900, DPR 2; plus the 390 px phone subset for M6 and D9. The repository's gallery runs at DPR 1 under full
  font hinting instead, the harder case for D1 and D8 (§0.5).
- **Gallery failure count** = the number of (image, check) pairs that fail. A spec-conformant build scores 0.

What the verified prototype ran (report §9), all at 0 failures: D1, D2, D3, the coloured-spine part of D4, M8's card
height, D14, M1, M2, M3, M4's cap, M5, A4 tier resolution, M7's off-scale printing, M10, M17's sentence, console
errors, and sideways page scroll at 390 px. The other checks are specified for the production build.

| Id | Level | Check (one line) | Prevents |
|---|---|---|---|
| M1 | model | Every axis: \|tick[k+1] − tick[k] − step\| < 1e−9·step | non-uniform ticks |
| M2 | model | 0 ∈ ticks, and the domain covers every in-range value in every panel | floating 0%, clipped data |
| M3 | model | One unit and one d per axis; no `$0.00`; zero label is exactly `$0`/`0%`; no M/B mix; no $ tick with ≥ 4 integer digits | mixed units, "$1,000M" |
| M4 | model | Tick intervals ≤ the panel's cap; gridline spacing ≥ h/(cap + 0.1) (≥ 17 px) in every panel and view | crowded ticks |
| M5 | model | G_L ≥ max tick px + 8 and ≥ 36 | clipped tick labels |
| M6 | model | slot ≥ 36 px (a labelled chart: the narrowest width up to 42 px a period with an A4 tier); if the container is narrower, `scroll = true` and W is that width | text collisions, dropped values |
| M7 | model | Every null plotted value has a band letter; every off-scale line point has an A3b item with its true value; every clipped growth bar has a break mark and its true value as its label; band letters = footnote letters = data-note letters that touch plotted values; no ↑/↓ in the band | silent gaps, orphan notes, hidden values |
| M8 | model | H identical for W ∈ {342, 502, 1030}; H = 320 on the card; ticks and tick text identical for card and expanded | CLS, grid misalignment, export ≠ screen |
| M9 | model | Colours = chart-1..k in order over present series; shapes circle, square, triangle by the same index; an absent series takes no slot; no gain, loss or brand token in any mark | colour misuse |
| M10 | model | For every same-panel series pair and period, the drawn y order equals the true order (0 false orderings) | dual-axis misordering |
| M11 | model | Clipping only on margins and growth panels; the clipped set equals the A3 output; no $ panel clipped | hidden dollars |
| M12 | model | Every SVG string ⊆ G2; † only as a notes-band glyph (and as the key of its footnote line); no † in any legend item, caption, label or title; no `[0-9$%BMKT]\s?†` anywhere (SVG, legend, footnotes, KPI strip) | missing glyphs, † on names and numbers |
| M13 | model | Bars and markers at slot centres; bars anchored at y(0); true length < 2 px → 2 px stub on the value's side; missing → no mark; every non-zero equity stub has an A13b label or a recorded drop | missing drawn as 0, invisible bars |
| M14 | model | Footnote strings byte-identical across card, expanded, light and dark | drift between views |
| M15 | model | Every printed chart value, rounded to the metrics-table precision, equals the table cell's number (minus code point ignored) | chart and table disagree |
| M16 | model | FY-end text per A9: CPRT Jul, LOVE Jan, SBUX Sep, NVDA Jan, DECK Mar, MSFT Jun, AAPL/q Sep, XOM/q omitted | wrong year-end |
| M17 | model | Applicability and reason per A12: 70 top-line charts; margins NII ×6, premiums ×5, none ×3; every not-applicable card has its sentence | vanishing panels, wrong copy |
| M18 | model | Growth states per A11: 562 value, 162 structural, 28 unavailable, 2 n/m (RIVN FY2020–21); every valued growth bar has a signed label (unless A4 dropped the panel's labels); every non-value prints `—` or `n/m` on the 0% rule | blank or false growth |
| M19 | model | The legend wraps by whole items; no item splits | legend misreading |
| M20 | model | `tolerances.json` holds T for every (dataset, chart, panel, view) and equals the formula | step-relative scoring loopholes |
| M21 | model | Every bar rect lies on its value's side of the zero rule: y + h ≤ y0 for v ≥ 0; y ≥ y0 for v < 0 | stubs drawn across or below zero |
| D1 | DOM | Every `<text>` `getBBox()` lies inside the SVG viewBox, inset 1 px (ascent and descent included) | "Fiscal year" clipping |
| D2 | DOM | No two `<text>` bboxes intersect | label collisions |
| D3 | DOM | No note glyph (band letters, †) and no ↑/↓ inside any plot rect; text inside a plot rect is limited to bar labels, A13b labels and the `—`/`n/m` state glyphs on the zero rule | stacked "a" markers |
| D4 | DOM | Every element with a series-colour fill or stroke has `data-series` and `data-period` (marks, off-scale arrows), or is a legend or strip swatch; count of others = 0 | coloured right-axis bar |
| D5 | DOM | Every y tick label's right edge < G_L; no text right of the plot except the right pad; no axis domain path, tick line or tag element exists | second axis, spine, tag |
| D6 | DOM | Computed colours meet the §3.8 APCA thresholds against «t.surface» in both themes, including the card's HTML subtitle, legend and footnotes | low contrast |
| D7 | DOM | Marker count = valued and zero in-domain points on line series; isolated points visible | invisible points |
| D8 | DOM | For every `<text>`, `getComputedTextLength()` = 0.6 × 11 × chars ± 0.5 px | fallback font |
| D9 | DOM | Card heights identical before and after hydration and across each grid row; no sideways page scroll at 390 px | layout shift |
| D10 | DOM | Under reduced motion, `document.getAnimations().length === 0` | motion |
| D11 | DOM | Rendered tick strings and positions = model `ticks`/`tickText`; `textLength` unset | renderer-chosen ticks |
| D12 | DOM | Every panel `<g>` has `data-panel`, `data-axis-step` and `data-axis-domain` equal to the model | unscorable images |
| D13 | DOM | One chart-values keyboard stop; Left/Right announces period, values, state and notes; Esc collapses expanded and returns focus (specified, not yet verified) | a11y regressions |
| D14 | DOM | Every bar `<rect>` carries `data-v` and `data-zero`; y + height ≤ data-zero when data-v ≥ 0, and y ≥ data-zero when data-v < 0 | stubs drawn across or below zero |
| E1 | export | Export SVG region against an element screenshot of the on-screen SVG at DPR 2: ≤ 0.1% of pixels differ (largest channel difference > 10%) | export ≠ screen |
| E2 | export | Export legend and footnote strings = `model.legend` and `model.footnotes` (composition; specified, not yet verified) | text drift |
| E3 | export | PNG width = W·2 for the SVG export, or (W + 48)·2 with the composition; every pixel opaque; no hover, focus, tooltip or scrollbar | stray UI in PNG |
| E4 | export | D1–D5 re-run on the serialised node before rasterising | export-only defects |
| E5 | export | Both Geist Mono subsets present as data URIs with their `unicode-range`; D8 holds for the serialised SVG in an `<img>`; † drawn from the embedded face | fallback glyphs |
| E6 | export | Legend item x positions equal the on-screen positions ± 1 px (composition; specified, not yet verified) | legend re-wrap |
| R1 | readout | Tier P: exact transcription of every printed string read (100%) | — |
| R2 | readout | Tier V: ≥ 90% within frozen T per chart and view; report median and p90 \|err\|/step | — |
| R3 | readout | Tier O: 100% where the true gap > T, including REGN FY2025 FCF < NI on the card and growth sign in every valued period | — |
| R4 | readout | Tier S: 100% of null and zero slots named correctly; no number for a missing slot | — |
| R5 | readout | Margins M1 within ±1 pp in expanded for 59/59 datasets | user's ±1 pp |
| G1 | gallery (visual) | No chart in the gallery shows an axis title, a right axis, an in-plot note letter or ring, a † beside a name or number, or a blank growth slot | user defects |
