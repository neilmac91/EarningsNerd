# Notation variant test (report §2.8 and §2.9)

The founder reviewed the ring design (report §2 as first written, captured in
[`screens/variants/ring-light-full.png`](../screens/variants/ring-light-full.png)) and found the
circled letter with "needs a source check" dramatic, distrust-inducing and distracting. Competitors
mark nothing. This test asked whether a quieter design, or none at all, keeps readers' trust
calibrated to the data. Alongside it, one read-only agent checked what in the repository a
quieter design would contradict.

## Method

**Data state.** The local REGN reproduction (report §1.4), with one addition. REGN's FY2018 and
FY2019 revenue rows were marked `needs_review` with the reason `source_conflict`. That is a
stand-in for the restatement note WP5 proposes (report §1.6). The note does not exist yet, so in
production these two cells read clean today:

```sql
update financial_fact set provenance = '{"version":1,"method":"reported","validation":"needs_review",
  "reasons":["source_conflict"],"formula":null,"inputs":[],"calculation_version":"quarterly-v2",
  "filed_at":"2021-02-08"}'::json, reconciled = false
where is_latest and fiscal_period = 'FY' and concept = 'revenue' and fiscal_year in (2018, 2019);
```

The rebuilt dataset then held three notes: "a" review `source_conflict` (2 figures, 3 YoY
comparisons), "b" review `legacy_calculation` (11 figures, 16 comparisons) and "c" unavailable
`not_in_dataset` (3 figures). There were 200 figures, of which 184 passed and 50 were calculated.

**Four designs, one data state.** The three variants came from the same build, switched by
`NEXT_PUBLIC_NOTATION_VARIANT` (prototype only: [`prototype/notation-quiet.diff`](../prototype/notation-quiet.diff)).
The ring design came from [`prototype/notation-prototype.diff`](../prototype/notation-prototype.diff).

| Label | Design | What it shows |
|---|---|---|
| P | current | Production today: † after every calculated figure; letters in warning ink for review notes; the Data notes strip under the KPI cards |
| Q | ring | The first proposal: ringed review letters; "needs a source check" on the KPI period line; the key in the strip |
| R | quiet | No † on figures, with one sentence above the table naming the calculated metrics. A small neutral letter only where a note questions the number (here: revenue FY2018–FY2019 and the growth built on it). Data notes become one line of fine print under the table. Legacy-calculation and gap notes stay in the fine print and the evidence dialog, unmarked |
| S | no marks | As R, but no figure carries a letter and there are no data notes. The evidence dialog still states every note |

**Captures.** Each design was captured full-page at 1440px in the light theme and cut into three
tiles of 1500px height. Labels P–S say nothing about the design. The full pages are in
[`screens/variants/`](../screens/variants/).

**Evaluators.** Eight fresh model instances, one per design and persona. Each opened only its three
tiles. Two personas took part:
- retail: "a self-directed retail investor who pays for this research tool and checks a company
  before buying its shares";
- pro: "a professional equity analyst at a small fund who uses paid data terminals daily and is
  sceptical of any figure that is not sourced".

Each instance was told to base trust on the page alone and to declare any outside knowledge. It
returned a fixed schema, which included:
- trust in the page, in FY2025 free cash flow ($4.1B, a correct legacy calculation) and in FY2018
  revenue ($5.1B, the restated figure);
- whether the page itself told it the revenue was in question, quoting the evidence;
- visual cleanliness;
- whether the product feels trustworthy;
- the one change it would make.

The prompt and schema are in the workflow script, quoted in [methods](../methods.md#notation-variant-test).

**The leak and the re-test.** After the first run, the quiet and no-marks builds turned out to still
show letters on the narrative's citation chips ("[8]ᵇ … [13]ᵇ"). `NarrativePane` builds its own
notes model, and the variant filter missed it. Three evaluators named the unexplained "b". The
filter was extended to `NarrativePane`, and R and S were re-run with identical prompts as R2 and
S2. The first-run R and S verdicts are kept below but superseded.

## Results

Scores run 1–5. "Flagged from the page" means the instance said the page itself, not its own
knowledge or cross-checking, told it FY2018 revenue was in question.

| Design | Persona | Overall trust | FCF FY2025 | Revenue FY2018 | Revenue flagged from the page | Used outside knowledge | Clean | Trustworthy |
|---|---|---:|---:|---:|---|---|---:|---:|
| P current | retail | 3 | 3 | 2 | yes | no | 3 | 3 |
| P current | pro | 3 | 4 | 2 | yes | yes | 3 | 3 |
| Q ring | retail | 3 | 3 | 2 | yes | no | 3 | 3 |
| Q ring | pro | 3 | 3 | 2 | yes | yes | 3 | 4 |
| R quiet (leak) | retail | 3 | 4 | 2 | yes | no | 4 | 4 |
| R quiet (leak) | pro | 3 | 4 | 2 | yes | yes | 4 | 4 |
| S no marks (leak) | retail | 3 | 4 | 3 | no | yes | 4 | 4 |
| S no marks (leak) | pro | 3 | 4 | 2 | no | yes | 4 | 4 |
| R2 quiet | retail | 3 | 4 | 2 | yes | yes | 4 | 4 |
| R2 quiet | pro | 3 | 4 | 2 | yes | no | 4 | 4 |
| S2 no marks | retail | 3 | 4 | 2 | no | yes | 4 | 4 |
| S2 no marks | pro | 3 | 4 | 2 | no | yes | 4 | 4 |

### What it shows

1. **Taking the marks off correct figures costs no trust.**
   - FCF trust: 3 and 4 for the current page, 3 and 3 for the ring, and 4 and 4 for both quiet and
     no-marks.
   - Cleanliness and "feels trustworthy" go from 3 to 4 when the routine marks leave.
   - Overall trust is 3 in all twelve verdicts, so the marks never bought trust.
2. **Removing every mark hides the one real problem.** Both no-marks evaluators (S2) wrote that
   nothing on the page flags FY2018 revenue. They doubted it only by cross-checking rows (revenue
   −12.4% beside operating income +21.9%) and from memory. Both quiet evaluators (R2) found it
   from the page. A reader who doesn't cross-check rows would take the false −12.4% at face value.
3. **Every design's readers asked for the same thing:** mark only the doubtful figure, quietly, and
   say there what is wrong.
   - Current, retail: "Mark only the figures that are actually doubtful, such as FY2018 revenue, with a single quiet neutral marker whose tap or hover says in plain words what is off and links the filing. Drop the orange '13 figures need review' count l…"
   - Ring, pro: "Don't remove the flags, and don't push them all into the fine print. The FY2018 revenue flag is the most useful thing on the page, and if I later found an unflagged wrong number, I'd stop trusting the whole product. Instead, swap the generic 'needs a source check' for one short line on each flag say…"
   - No marks, retail: "Remove the unexplained superscript 'b' from routine calculated figures. The Sources list already says 'Calculated figure', and the table note already says which rows are derived, so a single line of fine print is enough. Use an inline mark only for the rare fi…"
   - No marks (fixed), pro: "Add a visible per-cell data-quality marker with a legend for any figure that fails a cross-period consistency check, uses a different revenue concept than adjacent years, or comes from a restated or amended filing. Example: a small flag on FY2018 revenue readi…"
4. **What the quiet design still lacks.** It concerns the questioned figure itself, so it belongs to WP5.
   - R2 retail: "The note is worded like a routine housekeeping footnote rather than a warning, so I noticed it mainly because the numbers around it don't fit together."
   - Both R2 evaluators asked for the as-filed value, the restating filing and its date at the figure
     (hover, tap or the evidence dialog). They also wanted growth across the restatement shown as not
     comparable rather than as −12.4%.
   - R2 retail pointed out that FY2018's margins are computed from the restated revenue but carry
     no letter.
5. **The remaining complaints are not about notation.** They are raw machine precision in the source
   list, percentages on negative bases, the dual-axis cash chart, the "Red flags" heading, and
   "FY2025 CAGR" read as a one-year figure. All are already in report §4.1 and §7.

The full verdicts, every field, are in [notation-variant-test.json](notation-variant-test.json).

## The rules check (one agent, read-only, over the whole repository)

> **Verdict.** Most of the quiet scheme can ship as a design change. No ADR touches it. No D-0xx founder decision requires the dagger, warning ink or the strip under the KPI cards: the Calculation Provenance Rule and the † came from #1191's design work, not a founder decision. The founder's 2026-10-10 analysis decisions (letters as the note mark, the period vocabulary, the glyph budget, "Unavailable" / "No figures need review") all stay compatible. No marketing, pricing, legal or brand promise depends on a visible per-figure mark. The PR must still update a lot together: DESIGN.md's rule with the .impeccable/design.json sidecar (designSnapshotParity), the Data note mark, Analysis table, Data notes strip and §10 entries in frontend/DESIGN_SYSTEM.md, the reconciliation lesson, the superseded parts of the redesign doc, this branch's own coherence.md and prototype, the in-product copy that names the † (NarrativePane:121, DataNotes:103), the landing demo and teaser layout, and the unit, e2e and backend export tests that pin daggers, legacy and unavailable letters and the strip's place. One item needs the founder's explicit word first. Item 2 removes the on-figure letter from figures whose stored validation is needs_review (legacy_calculation), from unavailable values and from figures with no validation record. The redesign records this as the founder's "never hide a note", and a P0 review enforced it for exactly this case. The founder's message leans this way, so a one-line confirmation recorded as a decision (narrowing the rule to "every note stays in the dialog and the data notes; only notes that question the number keep a mark") is enough. Keep this presentation-only: the note kind and totals stay as they are, legacy figures are never shown as validated, and the fine print never says "No figures need review" while a legacy note exists. Reclassifying legacy_calculation in the backend would change what counts as needs_review, a separate founder call that also breaks the strict note-kind decoder for tabs already open. The rest is design scope: decide whether the Q4 column-header and period-picker daggers stay, and handle the letters stored in saved snapshots, where a legacy note can keep "a" while the only visible letter is "b".

Public promises that depend on visible marks:

- No marketing, pricing, legal or brand page promises a visible per-figure mark. That covers the ProDepth analysis pitch (frontend/features/marketing/components/ProDepth.tsx:110), the plan lines in frontend/lib/planLimits.ts:96-103, /terms, /privacy, /security and docs/brand/*.md (whose "each checkable figure" promises are about filing summaries).
- frontend/features/analysis/components/NarrativePane.tsx:121 (in-product, also rendered in the teaser's sample): "Sources identify filed figures or calculated figures (marked †)." This promises the dagger and must change.
- frontend/features/analysis/components/DataNotes.tsx:103 (in-product legend): "Letters identify data notes; † marks a calculated figure, not an error." This must change.
- frontend/features/analysis/components/NarrativePane.tsx:127 (teaser and landing sample note): "...source warnings shown for review." It holds if questioning notes keep a letter; reword if no warning styling remains.
- frontend/app/analysis/page.tsx:8 (meta description): "source-linked figures, transparent calculations". The evidence dialog and the one sentence satisfy it without a visible mark.
- The landing demo and the teaser carry the sample's scope label "sample data (one saved run)" inside the Data notes strip (frontend/DESIGN_SYSTEM.md:660; D-046). Moving the strip below the table must keep that scope visible.

| Severity | Kind | Where | Words | What to do |
|---|---|---|---|---|
| blocker-needs-founder | founder-decision | `tasks/analysis-redesign-2026-10/astra-prompt.md:74` | "Never mark a legacy record validated from the frontend, never hide a note, never show the word "verified"." | This constraint is attributed to the founder in tasks/analysis-redesign-2026-10/review-2026-10-10.md:36 ("the letter of a figure that needs review, which the founder's \"never hide a note\" forbids"). Item 2 takes the on-figure letter off figures whose stored validation is needs_review (reason legacy_calculation), off unavailable values and off figures with no validation record. Today that is the exact case the P0 review called a violation. Get the founder's explicit words that "never hide a note" now means "every note stays in the evidence dialog and the data notes, and only a note that questions the number keeps a mark beside it". Record that as a new decision row in docs/brand/decisions-log.md (or the redesign doc §9) and point both astra-prompt.md and review-2026-10-10.md at it. The other two clauses still hold. The fine print and the dialog must keep counting legacy figures as needing review, and must never print "No figures need review" while a legacy note exists. |
| must-update-in-same-pr | design-rule | `DESIGN.md:498` | "Multi-period analysis uses a neutral † for calculated figures and lettered data notes grouped by their underlying reasons. ... Only unresolved source concerns use warning ink; missing validation makes no passed-check claim. An unavailable table value is — with its note letter ... The table’s Notes chip names letters present in visible cells in report order, including unavailable values and annual window comparisons. Legends explain n/m, fiscal quarters and the Q4 flow-figure dagger ... Charts keep bars filled and mark affected observations with hollow points or note letters." | Rewrite the Calculation Provenance Rule: no † on figures, with one sentence above the table naming the calculated metrics. A neutral superscript letter appears only for notes that question the number, never in warning ink. Unavailable values show — with no letter. The Notes chip names only marked letters. Charts mark only questioning notes. Data notes become one line of fine print below the table. Keep "A calculation describes a figure’s origin, not a failed check" and the evidence-dialog clauses. The rule was written by #1191 and is not a founder decision. Follow the design-docs-maintenance skill. |
| must-update-in-same-pr | test-gate | `.impeccable/design.json:602` | ""body": "A calculation describes a figure’s origin, not a failed check. Multi-period analysis uses a neutral † for calculated figures and lettered data notes grouped by their underlying reasons." | Refresh the sidecar's copy of the rule with the same words as DESIGN.md. frontend/tests/unit/designSnapshotParity.spec.ts:311-314 checks every named "The ... Rule" body in DESIGN.md against design.json, so editing only DESIGN.md fails CI. |
| must-update-in-same-pr | design-rule | `frontend/DESIGN_SYSTEM.md:492` | "Data note mark   <DataNoteMark> (analysis) — neutral † for a calculated origin, then a superscript letter for its grouped data note. ... Warning ink belongs only to unresolved review concerns; unavailable values and missing validation use secondary ink." | Rewrite the recipe. No dagger. One neutral letter, only for a note that questions the number. No mark for legacy_calculation-only, unavailable or unknown notes. Keep the accessible-name rules (the name still states the note, and "calculated" if you keep it in the name) and "Letters are snapshot-local" (line 499). Saved snapshots store their letters (data_notes.py _finish orders review notes first), so a legacy note can keep "a" while the only visible letter is "b". Either accept that or reletter only the marked notes in the web, the PDF and the PNG together. |
| must-update-in-same-pr | design-rule | `frontend/DESIGN_SYSTEM.md:645` | "Data notes strip <DataNotes> — hairlines above and below a native details disclosure on the page ground, below the KPIs. The title uses primary ink; counts use the data face, with review counts in warning ink and every count beside its relevant note letters." | Move the recipe below the metrics table as one fine-print line in neutral ink, with no warning ink. Keep the native <details> so the Notes chips can still open it and focus a note (the e2e spec relies on this), keep "No figures need review" (founder decision 9), and keep the sample's "sample data (one saved run)" (lines 659-661). The fine print must clear 4.5:1 for tests/e2e/text-floors.spec.ts. Use 12px running copy, not text-data-xs, or add an entry to dataXsAllowlist.spec.ts, whose caps are equalities. |
| must-update-in-same-pr | design-rule | `frontend/DESIGN_SYSTEM.md:564` | "The table's Notes chip lists only letters present in its visible cells, including unavailable values and annual window comparisons, in report note order. ... Only a period-derived Q4 receives a column dagger; ordinary arithmetic ratios do not create one. The legend explains n/m and the fiscal-quarter basis. A Q4 header dagger applies to flow figures calculated from annual totals less nine months" | Drop "including unavailable values" from the chip rule. Settle the scope question "no dagger anywhere on the page" leaves open: the Q4 column-header † (MetricsTable.tsx:68, legend :211) and the period picker's "Q4 2023 †" option and "† Fourth-quarter flows…" line (PeriodPicker.tsx:131,161) are not figures. Either keep them and say so in the one sentence, or turn them into words. The redesign doc (:915-916) requires the picker to keep calculated-Q4 availability in its options either way. |
| must-update-in-same-pr | design-rule | `frontend/DESIGN_SYSTEM.md:2083` | "Multi-period analysis uses neutral `† calculated` marks and lettered data notes ... Warning ink identifies an unresolved concern, never routine arithmetic. ... Unavailable table values use — with a note letter and read “Unavailable” in the evidence view ... Affected chart points use hollow series-colour markers with a 2px stroke and 11px note letters" | Update §10. Hollow points and letters apply only to notes that question the number, not to legacy_calculation-only notes or gaps (a gap stays a broken line). There is no warning ink. Unavailable values read — with no letter. PNG notes follow the same rule. Keep the halo, keyboard and tooltip mechanics, and keep "Do not remove inherited concerns from growth" for questioning notes. |
| must-update-in-same-pr | lesson | `lessons/arch-reconciliation-follows-values-and-growth.md:20` | "same letters, reason identities and counts across the report and exports; keep a mark at each affected figure." | Lessons outrank docs (AGENTS.md §2). Lines 15-16 also say "Frontend metric/KPI/trend/narrative regression cases pin the corresponding visible warnings; mutations removing these paths must fail those tests." Once the founder confirms the first item, amend the rule to: a mark at each figure whose note questions the number; every note, legacy included, in the dialog, the data notes and the exports. Keep the gates that pin questioning marks. CLAUDE.md also asks for a lesson after any user correction, and "is your proposal overkill" is one. |
| must-update-in-same-pr | design-rule | `docs/design/analysis-data-notes-redesign-2026-10.md:912` | "A single page-level banner for exceptions was rejected: it would say that something is wrong without saying where. The letter beside each affected figure keeps material exceptions apparent at the point of use at a cost of two characters." | The quiet scheme keeps this reasoning for questioning notes and drops it for the rest. Add a dated supersession note: §1 items 2–3 (:31-34, "`†` for calculated and a letter in warning ink", "One **Data notes strip** under the headline cards"), §4.2 (:303-305), §4.3 position (:326, "Position: under the KPI strip … so it is the legend for everything below") and the §4.10 vocabulary table (:576, `26.1%†ᵃ`, `—ᵇ`) are replaced. The §9 decisions stay in force: 1 (letters), 3, 6 (glyph budget) and 9 ("Unavailable" / "No figures need review") are all compatible. |
| must-update-in-same-pr | other | `docs/mpa-improvements/coherence.md:230` | "**One key beside every mark.** No surface shows a mark whose meaning is only in a collapsed disclosure." | This branch's own report recommends the scheme the founder just called overkill. It calls for a ringed review letter (:33, "a review letter is ringed, so it never depends on colour alone"), "needs a source check" in warning ink on the KPI period line (:314), warning-ink fonts in the workbook (:320) and a key beside every mark. Fine print below the table puts a KPI letter's key far from it. Rewrite §0.3, §2.1–2.5, the WP1 row of §6 and the prototype (docs/mpa-improvements/prototype/notation-prototype.diff) for the quiet scheme. Record why §3.4's comprehension evidence (the reader had to guess what "a" meant) is still covered: the figure's accessible name, the dialog and the one sentence. |
| must-update-in-same-pr | test-gate | `frontend/tests/e2e/analysis-layout.spec.ts:116` | "await expect(source.locator('span').filter({ hasText: /^†$/ })).toHaveCount(expected.daggers)" | Update the browser gate and its fixture (frontend/tests/e2e/fixtures/analysisLayoutApi.ts:117-195). Dagger counts are pinned at lines 120 and 362, EXPECTED_KPI_VALUES.daggers and EXPECTED_TABLE_VALUE_DAGGERS = { all: 101 … }. The legacy state's review letters (EXPECTED_KPI_LETTERS.legacy, EXPECTED_TABLE_CELL_NOTES.legacy, EXPECTED_TABLE_REVIEWS.legacy, EXPECTED_TABLE_COMPARISON_REVIEWS.legacy) come from legacy_calculation and become zero marks. The unavailable marks (:356, unavailableLetter) go. The chip name at :385 must drop the unavailable letter. The summary text at :457-472 changes with the fine-print copy. The chip-to-note focus at :507-510 needs the disclosure kept. Keep the discrepancy state's letters as the proof that questioning notes stay marked. |
| must-update-in-same-pr | test-gate | `frontend/tests/unit/metrics-table.spec.tsx:73` | "it('renders values, deltas, the derived dagger, and — for missing points', () => { ... expect(screen.getByText('† calculated')).toBeInTheDocument() ... expect(screen.getAllByRole('button', { name: /unavailable.*data note/ }).length).toBeGreaterThan(0)" | Replace the "† calculated" chip assertion with the sentence above the table, and decide whether an unavailable value's accessible name still says "data note". Lines 355-367 pin the Q4 header † and its legend; change them only if the header dagger goes. Also update frontend/tests/unit/analysis-table-format.spec.ts:41-43 (tableTokenBudget(true, 'a') is 7): features/analysis/lib/tableFormat.ts:19-20 subtracts a glyph for the dagger, so dropping it frees a glyph under founder decision 6. |
| must-update-in-same-pr | test-gate | `frontend/tests/unit/narrative-pane.spec.tsx:271` | "expect(chip.querySelector('[data-note-kind="review"]')).toHaveTextContent('a')" | This case (from :261) is a legacy_calculation citation, so under item 2 its chip loses the letter. Assert there is no mark, while the source entry and #analysis-data-note-a still say "Its inputs need review." Lines 286-296 (the source list's review and unknown marks) and 316 also change. Keep the chips for questioning notes (e.g. source_conflict) asserted. |
| must-update-in-same-pr | test-gate | `frontend/tests/unit/trend-charts-annotation.spec.tsx:127` | "revenue.points[1].yoy_provenance = { ...passed, method: 'calculated', validation: 'needs_review', reasons: ['legacy_calculation'] }" | These chart cases (:127, :149, :166, with chips "Review data notes a, b" at :158 and :228) build their letters from legacy_calculation and gaps. Switch them to a questioning reason, or assert no hollow point or letter for legacy. Do the same in frontend/tests/unit/chart-export.spec.ts:67-98: the PNG "Note a" for a legacy YoY, and its unavailable line, which stays as a sentence. |
| must-update-in-same-pr | test-gate | `frontend/tests/unit/analysis-source-quality.spec.tsx:196` | "expect(screen.getByText('† calculated')).not.toHaveClass('bg-warning-light/10')" | The "† calculated" element goes. Re-pin the summary text at :71-82, :188, :245-249 and :357 to the fine-print line (keeping "No figures need review · N checked"). Lines :253-286 test the legacy_calculation dialog. Keep those: the dialog still names the note. |
| must-update-in-same-pr | test-gate | `backend/tests/unit/test_export_service.py:648` | "assert "$1,500 †" in html" | Item 5 removes the PDF dagger (export_service.py:349-350 appends " †"; the footnote at :465 reads "Letters refer to Data notes. † Calculated figure;"). Re-pin :648 and :675. Line :677 pins '—<sup class="data-note"><a href="#analysis-data-note-b">b</a></sup>' on an unavailable value, which goes. The count line "calculated †" in analysis_export_metadata.py:113 and its assertion at :813 change too. The workbook already shows notes only in comments (test_excel_export.py:218), so it needs little. |
| must-update-in-same-pr | test-gate | `backend/tests/unit/test_export_voice.py:188` | ""Data notes", "Metrics by period", "Narrative sources", "Sources & methods", "About this document"," | The PDF prints Data notes as an h2 before the grid. If the export moves it below the table as fine print with no h2, update this heading-order pin and test_export_service.py:761 (`html.count("<h2>Data notes</h2>") == 1`). Touching backend/app also triggers the paid eval-baseline run on each push (reserve first, D-056) and the whole frontend unit suite before pushing (CLAUDE.md). |
| must-update-in-same-pr | public-promise | `frontend/features/analysis/components/NarrativePane.tsx:121` | "'Sources identify filed figures or calculated figures (marked †).'" | This in-product copy also renders in the teaser's sample, and it promises a † that will no longer appear. Reword, e.g. "Sources identify filed and calculated figures." Apply lessons/brand-a-promise-names-what-the-code-enforces.md and grep for other copies. |
| must-update-in-same-pr | public-promise | `frontend/features/analysis/components/DataNotes.tsx:103` | "Letters identify data notes; † marks a calculated figure, not an error." | Rewrite the legend for the quiet scheme ("A letter marks a figure a note questions; select any figure for its source and calculation."). The "N calculated †" count clause at :97 also loses its dagger. Under lessons/brand-a-colour-rule-recolours-a-value-and-never-deletes-it.md, dropping a count from the strip must be named as a copy decision in the PR's What, with its reason. |
| must-update-in-same-pr | public-promise | `frontend/features/marketing/components/AnalysisDemo.tsx:45` | "<DataNotes dataset={SAMPLE_ANALYSIS_DATASET} sample />" | The landing's demo (and AnalysisTeaser.tsx:41) puts the strip right after KpiStrip, as AnalysisPageClient.tsx:448 does. Move it below MetricsTable in all three so the landing shows the product as it is. The strip carries the sample's scope label "sample data (one saved run)" (DESIGN_SYSTEM.md:660, D-046/E93), which docs/brand/09-stress-test.md:43 (T11) counts on, so keep it visible in the fine print. |
| note | founder-decision | `docs/design/analysis-data-notes-redesign-2026-10.md:896` | "Changing what counts as `needs_review` or `unavailable`." | This sits in the brief's out-of-scope list, beside "Any frontend override that marks a legacy record validated, hides a note, or shows \"verified\"" (line 895). Implement item 2 as presentation only. Keep the note's kind as review, keep the totals unchanged, and decide which notes get an on-figure mark from their reason codes in one shared helper used by the web and the exports. Reclassifying legacy_calculation in backend/app/services/trend_analysis/data_notes.py, with a new kind or a validation other than needs_review, would change what counts as needs_review. That is a separate founder call. It would also fail the strict kind check in frontend/features/analysis/lib/dataNotesContract.ts:59 for browser tabs already open. |
| note | founder-decision | `docs/design/analysis-data-notes-redesign-2026-10.md:931` | "1. Letters (a, b, c) as the note mark, or one warning glyph for all notes. Recommended: letters." | No conflict. The quiet scheme keeps letters as the note mark and only narrows which notes show one. Decisions 6 (glyph budget, :965) and 9 ("Unavailable" / "No figures need review", :973) also survive. Name them in the PR body as untouched. |
| note | public-promise | `frontend/app/analysis/page.tsx:8` | "with source-linked figures, transparent calculations and AI-assisted commentary." | The meta description still holds without a visible dagger: every figure opens its method, inputs and checks in SourceValue, and the sentence above the table names the calculated metrics. No change needed. |
| note | public-promise | `frontend/features/analysis/components/NarrativePane.tsx:127` | "Run an analysis to see cited figures checked against the company’s filed data and source warnings shown for review." | This shows on the teaser and the landing's sample. It stays true if questioning notes keep their letter and the fine print lists them. With warning ink gone everywhere, consider "source concerns noted for review" so the copy does not promise a warning style the page no longer draws (narrative-pane.spec.tsx:415 pins the sentence). |
| note | design-rule | `frontend/DESIGN_SYSTEM.md:1351` | "`changeNote` marks Change with a dagger the footer explains" | The filing page's Financial Highlights keeps "Change†" (FinancialMetricsTable.tsx:222; tasks/evidence-row-ux-plan-2026-10-22.md:230-236), so † stays the product's sign for "calculated" there. The analysis change is not a contradiction. Say in the PR that the two surfaces now differ on purpose, or plan the filing page's own review. |
| note | lesson | `lessons/brand-an-evidence-label-names-only-its-check.md:59` | "A meaning that rides on styling alone must also reach a screen reader." | The quiet letter carries meaning by letter, not colour, so this holds as long as the figure's accessible name keeps "data note x" (DataNoteMark announce path) and the sentence above the table is real text. Keep "calculated" in each figure's accessible name, or state the scope in the sentence, so screen-reader users keep what the dagger used to say. |
| note | other | `docs/brand/00-audit.md:55` | "the Multi-Period demo opens with "Data notes · illustrative sample · 18 figures have no validation record · 18 comparisons have no validation record"" | Supports the quiet scheme: the audit scored the demo's leading data-notes line as "the disclaimer forgot to be a product" (T11). After the PR, retake the landing capture referenced in docs/brand/09-stress-test.md:43 if T11 is rescored. No gate depends on it. |
