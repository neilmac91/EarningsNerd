# Evidence row ("Figures with their receipts."): UX resolution plan

2026-10-22 · Claude Code session, from the founder's annotated screenshot · **Plan only: no product code has changed.**

**Scope.** The landing page's second row (`#evidence`): [`EvidenceSection`](../frontend/features/marketing/components/EvidenceSection.tsx),
the shared [`FinancialMetricsTable`](../frontend/features/summaries/components/FinancialMetricsTable.tsx) it renders (also the filing
page's Financial Highlights, through [`SummaryBlocks`](../frontend/features/summaries/components/SummaryBlocks.tsx)),
[`TraceToSourceDemo`](../frontend/features/marketing/components/TraceToSourceDemo.tsx), [`CatchCard`](../frontend/features/marketing/components/CatchCard.tsx),
the static data in [`landing-samples.ts`](../frontend/features/marketing/lib/landing-samples.ts), the chip and panel in
[`SourceTrace`](../frontend/features/filings/components/SourceTrace.tsx) and [`MetricSourceLink`](../frontend/features/filings/components/MetricSourceLink.tsx),
and the server logic that sets the figure labels, `build_metric_source` in
[`provenance_service.py`](../backend/app/services/provenance_service.py). A fix that reaches the product is marked as such.

**Evidence tags.** **[O]** observed in the render, the code or SEC data, with the method named; **[I]** inferred from observations;
**[A]** assumption to test; **[Q]** needs evidence or a founder decision.

**Not available to this investigation.** Observations of real users (the beta protocol in
[`support-and-review.md`](readiness-2026-09-21/beta/support-and-review.md) holds placeholders only), screen readers on real
devices, browsers other than Chromium, and a qualified financial reviewer. Everything that depends on them is marked pending in §4.

---

## 1. Diagnosis

### 1.1 Audience, task and decision

- **Who** [O, docs]: "The serious individual investor who already reads 10-Ks and wants the tedium removed"; secondary,
  "prosumers and analysts who need defensible, citable facts" ([01-interview.md §1](../docs/brand/01-interview.md)). The landing
  page qualifies visitors, with "See a live example" as its primary action (A6).
- **[A1]** Most of those readers know a 10-K but not the words "XBRL" or "EDGAR": they read the document, not its tagged data.
  The annotations say so; no user evidence in the repository confirms or refutes it.
- **Task in this section** [I]: decide whether the summary's numbers can be trusted, and learn how to check one.
- **What the section must make clear**: what each label promises and what it does not; which year each figure belongs to;
  which numbers are filed, which are calculated and which are interpretation; where a figure sits in the filing.
- **Decision it supports**: open the live example and rely on the summary with calibrated trust. The brand promise is "I can
  check it" ([03-strategy.md](../docs/brand/03-strategy.md), S4), not "trust us".

### 1.2 The three annotations

| # | Annotation | Observed | Inferred cause | Still unknown |
|---|---|---|---|---|
| 1 | Pink boxes on "SEC XBRL", "XBRL" and "SEC EDGAR": unfamiliar terms | [O render and accessibility tree] In `#evidence`: "SEC XBRL" 4 times (lead, two table chips, the catch card's chip), "XBRL" twice more (lead, table footer), "SEC EDGAR" twice (demo instruction, panel link), "Cited" 3 times, "Verified in filing" twice. Their only definitions are the lead paragraph, above the table, and hover or focus popovers. [O docs] "SEC XBRL" is prescribed by [`voice-and-style.md`](../docs/voice-and-style.md) rule 2. | The vocabulary was chosen to be exact for experts and is defined once, away from where the reader meets it. "SEC XBRL" also reads as if the SEC produced or checked the figure; the company tags its own filing and the SEC publishes it [I]. | How many target readers know the terms ([A1]; test T8). |
| 2 | "Column alignment could be better in tables", boxing Change | [O Playwright, 1440px] Header and value right edges agree (Current 710.2px, Prior 819.5px, Change 913.9px), so edge alignment is not the fault. These are: (a) 24px between the right-aligned change and the left-aligned takeaway, so "CHANGE INVESTOR TAKEAWAY" and "+6.4% Up 6.4%…" read as one run; (b) the direction glyphs are ragged by 8.4px (one mono character), because each sits left of a number of different width; (c) "Current period" and "Prior period" wrap to two lines and "Change" does not, all centred vertically; (d) body cells are centred vertically, so each figure sits 10–18px below its metric name, between the name and its chip; (e) both XBRL chips wrap to two lines in the 185px Metric column at 1440, 1100 and 800px; (f) the years are outside the card, in an 11px line (`text-data-xs`, "FY2025 vs FY2024"). | The table is the product's shared component, built for the filing page, where the period labels are generic; the landing passes no years and the chip labels are long. | Whether readers scan by row or down the Change column (observe in T1–T2). |
| 3 | "The number you remember": nobody remembers last year's figures; the closing sentence makes no sense | [O] The card repeats the Revenue row's two figures and fact. $391.0B is Apple's correct FY2024 total net sales: SEC companyfacts and the FY2025 10-K's comparative column both carry 391,035 (USD millions), and Apple has filed no 10-K/A. The card strikes it through as "From memory" while the table above shows the same figure, unstruck, as "Prior period". The strike-through is CSS on a `dd`: the accessibility tree reads "From memory $391.0B FY2024 In the filing $416.2B FY2025", with no sign that the first is meant as wrong. The chip names the fact "Total net sales"; the table calls it "Revenue". From 768px the card is mostly empty below its content. | [O docs] The card was the "activation moment": "a confident wrong number beside the verified one" ([01-interview.md §1](../docs/brand/01-interview.md), council verdict #4). Naming a chatbot was ruled out (A4) and inventing a wrong number was rejected ([D-012](../docs/brand/decisions-log.md)), so the card kept the strike-through but lost its wrong number. What is left asks readers to recall a figure most never knew, and marks a correct filed figure as wrong. | Nothing that changes the fix. |

### 1.3 Findings beyond the annotations

**D. The figure label promises more than the check does** [O code and probe]. `build_metric_source` reads only the row's
`current_period`; the prior period and the change are never compared. `_value_appears_in_text` turns the XBRL value into candidate
strings and tests whether any is a substring of the displayed text, without reading the displayed scale. Run verbatim against
416,161,000,000, it labels "$416.2B" (right), "$416.2M" (1,000 times too small), "$416.9B" (wrong tenths) and "$4,416.2B" (a stray
digit) as matched, and "$41.6B" and "$391.0B" as not. The chip sits under the metric name, so it reads as covering the whole
row [I]; its panel says "Matched against the SEC-filed XBRL value". The model writes the table's current figures, and I found no
other check of their scale [I]: [`figure_trace.py`](../backend/app/services/ai/figure_trace.py) polices prose and excludes tables;
`attach_normalized_facts` ([`schemas/summary.py`](../backend/app/schemas/summary.py)) fills a missing prior period from XBRL but
leaves the written current figure as it is; the renderer fills the table from XBRL only when the model left it empty. The
landing's own rows are correct (§4.1); the gap is in what the lead promises about every summary. [Q] Whether a later step catches
a scale error, and how many stored summaries carry a matched row whose scale disagrees (a read-only database count; not run).

**E. "Cited" means two things** [O code]. A mapped dollar figure that was checked and did not match (`source_checkable` true,
`source_verified` false) gets the same "Cited" chip as a per-share figure that is never checked. Only the filing page's tally
separates them ([`verificationTally.ts`](../frontend/features/summaries/lib/verificationTally.ts)). A mismatch is the most useful
thing a label could say, and it reads as a neutral citation.

**F. The Trace demo's chip covers words it did not check** [O]. The claim reads "Services net sales rose 13.5% to $109.2B on
advertising, the App Store and cloud services", followed by "Verified in filing". The quoted passage contains neither 13.5% nor
$109.2B. Both figures are right (109,158 vs 96,169 USD millions, +13.506%), but Services is a dimensioned fact
(`srt:ProductOrServiceAxis` = `us-gaap:ServiceMember`) that the product never checks, and the filing prints "14 %". The panel's
status line falls back to "Verified against the original SEC filing", because the demo passes no note; the product's own
takeaway chip says the narrower "The passage cited for this takeaway was found in the filing text." The instruction "Hover or tap
the chip to see…" does not match the demo: the panel is open on load, hovering changes nothing, and a click closes it (Playwright:
`aria-expanded` true, still true after hover, false after click). [DESIGN.md](../DESIGN.md), "Dialogs and evidence": a source match
"must not imply that every claim in an answer was verified".

**G. Interpretations have no visible support** [O]. No takeaway carries an evidence chip on the landing (the sample rows have no
`commentary_evidence`), and `landing-samples.ts` calls them editorial while the page presents them as the product's output.
Checked against the filing:

- "Up 6.4% on the prior year; Services grew fastest." True. Services +13.5% (the filing prints 14 %), Mac +12.4% (12 %),
  iPad +5.0%, iPhone +4.2%, Wearables, Home and Accessories −3.6%. The first clause repeats the Change column.
- "Grew three times as fast as revenue; the provision for income taxes fell." The arithmetic holds (19.5% ÷ 6.4% = 3.03; the
  provision fell from $29,749M to $20,719M). It leaves out the cause the filing gives: the effective tax rate fell to 15.6% from
  24.1% "due to a $10.7 billion year-over-year decrease in the provision for income taxes related to the State Aid Decision"
  (Item 7, Provision for Income Taxes), while pre-tax income grew 7.5%. A reader could take a tax effect for an operating
  improvement [I]; a qualified reviewer should decide the wording.
- "Buybacks lifted EPS above net income growth." Consistent with the filing: diluted weighted-average shares fell 2.6%
  (15,408,095K to 15,004,697K), and "During 2025, the Company repurchased 402 million shares of its common stock for $89.3 billion."
  (Note 10). "Buybacks" is the inference; the share count is the evidence.

**H. No filing identity** [O]. Nothing in `#evidence` names Apple, the form or the filing date; the only period text is
"FY2025 vs FY2024". Apple's fiscal year ends in late September, so "FY2025" alone does not tell a reader which months. The voice
guide's Claims rule: a sample figure on a sales surface "carries its filing identity".

**I. Receipts open the top of the document** [O]. Every chip opens `aapl-20250927.htm` at its top, a 1.5 MB document. Total net
sales appears as 416,161 (USD millions) on page 29, in the Consolidated Statements of Operations. The first "Total net sales" in the
document is a geographic table in Item 7, and the run "Total net sales 416,161 391,035" occurs three times, so a naive text-fragment
link would land on the wrong table.

**J. Calculated changes differ from what the filing prints** [O]. The Change column shows one-decimal changes computed from the two
figures (+6.4%, +19.5%, +22.7%). Where the filing prints a change it rounds to whole percent ("6 %" for total net sales). Nothing
says the column is calculated, so a reader who checks finds a different number [I].

**K. Accessibility beyond the automated pass** [O]. The metric name is a `td`, not a row header (DataTable already supports
`rowHeader`). Column headers say "Current Period" and "Prior Period"; the years are only in a paragraph outside the table. The
strike-through's meaning is visual only. The table chips open a new tab without saying so; the catch chip does say so. Automated
results were clean (§4.1).

**L. The sample is about to age** [O and I]. Apple filed its FY2025 10-K on 2025-10-31 and its FY2024 10-K on 2024-11-01; its
FY2026 10-K is therefore likely around 2026-10-30, about a week from this plan. Once it is filed, the landing's "current" year is the
prior one.

### 1.4 Limits of the application versus limits of the data

| The application (ours to fix) | The financial data (ours to state, not fix) |
|---|---|
| The figure check reads only the current period and ignores scale (D). | XBRL tags are applied by the company; the SEC publishes them without checking them. |
| Only mapped dollar concepts of at least $1M are checkable; per-share figures, ratios, margins and segment lines never are. | SEC companyfacts omits dimensioned facts: Services and other segment lines must be read from the filing's inline XBRL ([D-021](../docs/brand/decisions-log.md)). |
| One "Cited" label covers "not checkable" and "did not match" (E). | Companies choose their own line labels and tags: Apple's "Total net sales" is `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`; "Revenue" is our label. |
| Links open the document, not the line (I). | The statements report in millions and round printed changes to whole percent (J). |
| Quote matching ignores case, spacing and quote styles and needs at least 24 characters (`normalize_for_match`), so "exact characters" would overstate it; "word for word" does not. | Fiscal years are not calendar years: Apple's ends on the last Saturday of September. FY2025 and FY2024 are 52 weeks each; FY2023 was 53. |
| The landing's takeaways are editorial and unsupported (G); the sample is static and dated (L). | A later filing can restate a comparative; none has for these periods. Diluted EPS uses weighted-average shares, which move with buybacks and with issuance. |

---

## 2. Prioritized resolution table

P0: the page must not mislead. P1: readers must understand it without coaching. P2: robustness and polish.
Effort for one developer including tests: XS ≤ 1 hour, S ≤ half a day, M 1–2 days, L more.

| ID | Pri | Issue | Evidence | Recommendation | Component | Dependencies | Effort | Acceptance criteria |
|---|---|---|---|---|---|---|---|---|
| R1 | P0 | Catch card marks a correct filed figure as wrong; its premise asks for recall | §1.2 #3 | Interim: remove the strike-through and the sentence "That is the whole point", or hide the card. Final: replace it with the receipt card, "Follow one figure to the filing" (§3.5). Supersede D-012 in the decisions log. | `CatchCard.tsx` (retire), new `FigureReceipt.tsx`, `EvidenceSection.tsx`, `landing-samples.ts`, `tests/e2e/catch-card-reflow.spec.ts` (rewrite its geometry checks for the new card), `docs/brand/08-applications.md` | Interim: none. Final: R3 (chip wording), R10 (link target) | Interim XS; final M | No figure in `#evidence` carries strike-through or "wrong" styling (gate R13a); in testing, at most 1 of 8 participants says a figure looks wrong (T6) and at least 6 of 8 locate the line in the filing (T5) |
| R2 | P0 | Demo chip and panel imply checked figures; the instruction is wrong | F | Claim only what the quote supports; panel status names the check; instruction matches behaviour; link to the passage (§3.6) | `TraceToSourceDemo.tsx`, `SAMPLE_TRACE`, `tests/unit/trace-to-source-demo.spec.tsx` | Final chip text from R3; ships first with today's labels | XS–S | Every figure in the claim appears in the quoted passage (gate R13b); hover leaves the panel as it is and a click toggles it, as the instruction says (Playwright); panel says what was found; at least 6 of 8 answer T7 correctly |
| R3 | P0 | Labels and the lead overstate the figure check and lean on jargon | 1.2 #1, D | One label system shared by product and landing (§3.2); drop "SEC" from the figure label and the concept prefix ("Revenue ·") from the chip; replace the lead paragraph with the legend (§3.1); keep "XBRL" in a closed "How we check" disclosure and in panel detail | `MetricSourceLink.tsx`, `SourceTrace.tsx` (default labels, notes, link label), `EvidenceSection.tsx`; tests: 16 files assert "Verified in filing", 5 "SEC XBRL", 6 the EDGAR link, 4 "Cited"; `voice-and-style.md` rule 2 and its Do table; `DESIGN.md` and `DESIGN_SYSTEM.md` chip recipes (design-docs-maintenance skill) | Q1 (app-wide or landing-only); R4 before any copy that says "after rounding" | M (mostly test updates) | One module maps each server state to one label (unit test enumerates every state); no "XBRL", "EDGAR" or "Cited" in the primary copy of `#evidence`; at least 6 of 8 explain "Matches filing" and its limit (T3); no unprompted term questions (T8) |
| R4 | P0, product | The match accepts a wrong scale and ignores the prior period | D | Compare values, not strings: parse the displayed figure with its scale (reuse `parse_display_number` and the scale map in `metric_delta_service`), accept it when it is within half a unit of its last shown digit of the XBRL value (the rule `figure_trace._grounded` already uses), and run the same check on `prior_period` against the prior XBRL value; set `source_verified` only when every shown period matches | `backend/app/services/provenance_service.py` and its unit tests | None. Review as high: trust-critical labels ([AGENTS.md §5](../AGENTS.md): unsure means high) | M | Unit cases: "$416.2B", "$416.16B", "$416,161M" match; "$416.2M", "$416.9B", "$4,416.2B" do not; a wrong prior period clears the label; one mutation proof ([AGENTS.md §4](../AGENTS.md)) |
| R5 | P1, product | Checked-and-unmatched reads like a citation | E | Three figure states: "Matches filing", "Linked, not checked", "Doesn't match filing" (warning ink, as DESIGN.md's Calculation Provenance Rule reserves warning ink for unresolved source concerns). Pass `source_checkable` through to the chip | `MetricSourceLink.tsx`, `FinancialMetricsTable.tsx` (`FinancialMetric` type), the tally copy | Q3 (label or withhold a mismatch); R4 | S–M | Each server state renders its own label (unit test); chips and the tally always agree |
| R6 | P1 | Table: years missing, crowded Change column, misaligned rows, no row headers | 1.2 #2, K | Layout specification in §3.3 | `FinancialMetricsTable.tsx` (optional `periods` prop, `rowHeader`, cell alignment, change slot, takeaway inset), `DataTable.tsx` (opt-in bottom-aligned headers); tests `FinancialMetricsCards.spec.tsx`, `tests/e2e/metrics-stacked-cards.spec.ts` | Product period labels need period data (`period_end_date` exists on the filing); until then the default stays "Current period" / "Prior period". Rule 11 done-gate: both themes on the preview | M | At 1024px and up (Playwright): change-to-takeaway gap at least 40px; glyph left edges equal within 0.5px; header labels share a bottom edge within 1px; each figure's top within 2px of its metric name's; no header label (the year) or chip wraps, the date line under each year being a second line by design. Row headers in the accessibility tree. At least 7 of 8 name the first column's period (T1) |
| R7 | P1 | No filing identity | H | Identity line above the table (§3.1), replacing "FY2025 vs FY2024" | `EvidenceSection.tsx`, `SAMPLE_FILING` (add period end and filed date) | None | XS | `#evidence` names company, ticker, form, fiscal year end and filed date |
| R8 | P1 | Takeaways are interpretation without support; the tax one leaves out the cause | G | Either take the pipeline's own takeaways for this filing (a snapshot, as the Multi-Period demo is) with their evidence, or use the reviewed wording in §3.4 with verbatim passages; label editorial text as such if it stays | `landing-samples.ts` (`commentary`, `commentary_evidence`), `tests/unit/landingSamplesVerified.spec.ts` (extend: each takeaway's passage is verbatim in the filing) | Q2; a qualified financial reviewer | S plus review | Each takeaway shows a chip whose passage or fact supports it; reviewer checklist signed (§4.4) |
| R9 | P1 | "SEC EDGAR" link labels | 1.2 #1 | "Open the filing on SEC.gov" and, for a passage, "Open the passage on SEC.gov", each with a visually hidden "(opens in a new tab)". Leave the legal pages and disclaimers as they are | `SourceTracePanelBody` in `SourceTrace.tsx`; optionally "Original on SEC EDGAR" in `FilingIdentity.tsx` and `FilingWorkspace.tsx` in the same sweep | Q1 | XS–S | No "EDGAR" in the primary copy of `#evidence`; every link's name states its destination and the new tab |
| R10 | P2 | A receipt cannot reach the fact | I | Spike two targets: (a) a text fragment with context: the run "Services 109,158 96,169" occurs once in this filing's text, so `#:~:text=Services-,109%2C158,-96%2C169` is a candidate, but whether a fragment's context may cross table cells is unverified; (b) the SEC's Inline XBRL viewer (`https://www.sec.gov/ix?doc=/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm`), and whether it can open on one fact. Fallback: name the statement and page in the card | `SAMPLE_RECEIPT` URL; later, figure fragments in `provenance_service` | None | S (spike) | From the receipt card, the target line is in view after the click in Chrome, Safari and Firefox, or the card names the statement and page |
| R11 | P2 | Phone cards' figure groups do not line up across cards | O, 390px capture | Three equal tracks while they fit, wrapping as today under enlarged text (a rem-based container query) | `FinancialMetricsTable.tsx` (cards) | R6 period labels | S | At 390px and default text the group left edges align within 1px across cards; `tests/e2e/reflow-200.spec.ts` still passes |
| R12 | P2 | Sample freshness | L | "Filed" date in the identity line; when the FY2026 10-K lands, rerun the reconciliation (Appendix) and act on Q4 | `landing-samples.ts`, `docs/brand/00-audit.md` §4, `landingSamplesVerified.spec.ts` | Q4 | S per refresh | The identity line shows the filing; the reconciliation passes on the sample in use |
| R13 | P2 | Rule 12: each "never again" gets a gate | all | (a) a unit test forbidding `line-through` in `features/marketing`; (b) a test that every figure in `SAMPLE_TRACE.claim` appears in its excerpt; (c) the label-mapping test (R3, R5); (d) the wrong-scale matcher tests (R4) | as listed | Ship each with its fix | inside R1–R5 | Each gate has one mutation proof |

---

## 3. Copy and layout specification

Voice: [`voice-and-style.md`](../docs/voice-and-style.md). Sentence case, no em-dashes, middots for compact labels, scope stated
once per surface, no "each figure" or "every figure" without its scope (`brandCopyRules.spec.ts`).

### 3.1 Label column, identity line and legend

| Element | Today | Proposed |
|---|---|---|
| Number, title | 02 · "Figures with their receipts." | Unchanged |
| Label column line | "Each row in the highlights carries a label." | "Each label says what we checked, and each link opens the filing." |
| Lead paragraph | "A row reads SEC XBRL when its value matched the company's XBRL fact, and Cited when it points to the filing without that match. A quote reads Verified in filing only when its words were found there." | Replaced by the legend below |
| Period line | "FY2025 vs FY2024", right-aligned above the card | Identity line, left-aligned above the card, data face: "Sample filing · Apple Inc. (AAPL) · 10-K · fiscal year ended Sep 27, 2025 · filed Oct 31, 2025" |

**Legend**, an `h3` "What the labels mean" over a `dl`. Each term is the chip itself, inert (no link), so the reader learns
the shape with the word.

| Term (chip) | Definition |
|---|---|
| `{ }` Matches filing | "Both years' figures match the numbers Apple reported in the filing's data, after rounding." Until R4 ships: "This year's figure matches the number Apple reported in the filing's data." |
| `↗` Linked, not checked | "We link to where the figure is reported but don't check it. We don't check per-share figures, ratios or segment results." |
| `❝` Quote found in filing | "The quoted words appear in the filing, word for word." |

**Disclosure** under the legend, closed by default, summary "How we check":
"Companies file their financial statements with machine-readable tags on the figures, a format called XBRL. We compare the
figures we can check with Apple's tagged values for the same line and year. Rounding is allowed; a different scale or digit is
not. Quotes are matched word for word, ignoring capital letters, spacing and quote styles. The investor takeaways are
interpretation, so each carries the label of the passage it rests on."

The second sentence's rounding clause depends on R4, and the last sentence on R8.

### 3.2 One label system for product and landing

| Server state | Chip | Glyph | Accessible name | Panel status line | Panel detail |
|---|---|---|---|---|---|
| Figure matched: `source_verified` (after R4: every shown period) | Matches filing | braces (reserved for an XBRL fact) | "Source: Matches filing" | "Matches the figure Apple reported in this filing." | "As filed: $416,161 million · Total net sales · year ended Sep 27, 2025" (the product needs the value, label and period in the payload; the landing is static) |
| Figure not checkable: `source_checkable` not true | Linked, not checked | arrow out | "Source: Linked, not checked" | "We link to where this figure is reported. We don't check per-share figures, ratios or segment results." | Statement name |
| Figure checked, not matched (R5) | Doesn't match filing | warning circle, warning ink | "Source: Doesn't match filing" | "Our figure differs from the number Apple reported. Check the filing before relying on it." | "As filed: …" |
| Passage located: evidence `verified`, a risk's `source_verified` | Quote found in filing | quotes | "Source: Quote found in filing" | "Found in the filing, word for word." | Section, then the passage in the filing's face |
| Passage not located | Section linked | arrow out | "Source: Section linked" | "We link to the section. We couldn't find these words in it." | Section |

Every panel ends with "Open the filing on SEC.gov", or "Open the passage on SEC.gov" when the link carries a text fragment,
followed by a visually hidden "(opens in a new tab)". The "Source: …" accessible-name pattern stays, so the keyboard and focus
tests keep their shape and change only their strings.

### 3.3 Financial highlights table

Shared component. The landing passes the years; the filing page keeps today's labels until its period data is wired.

- **Columns.** Metric · FY2025 · FY2024 · Change† · Investor takeaway. Under each year, a second header line in normal case:
  "to Sep 27, 2025", "to Sep 28, 2024". New optional prop: `periods?: { current: { label, detail? }, prior: { label, detail? } }`.
- **Row headers.** The Metric column renders `th scope="row"` (`rowHeader: true`), so a screen reader announces
  "Revenue, FY2025, $416.2B".
- **Vertical alignment.** Header cells bottom-aligned, so one-line and two-line labels share the rule. Body cells top-aligned,
  with the metric name and the figures on the same 20px line (`text-sm leading-5`), so each figure sits on its name's line; the
  chip goes below the name.
- **Change cell.** The glyph sits left of a number box whose minimum width is the column's longest change string in `ch`
  (exact in the mono face), right-aligned, so the glyphs form a column and the numbers keep a shared right edge. The sign and
  glyph carry direction without colour (unchanged).
- **Space before prose.** The Investor takeaway column takes `pl-8`, so 44px separates the last number from the first word.
- **Header text.** "Change" plus a dagger hidden from assistive tech, and a visually hidden ", calculated" in its place.
- **Precision and units.** Dollar amounts of a billion or more at one decimal with "B" ($416.2B); per-share at two decimals
  ($7.46); changes at one decimal with a sign (+6.4%). No decimal alignment across rows: each row is a different metric and unit.
  The exact filed value lives in the chip's panel (§3.2).
- **Wrapping.** Numbers never wrap (unchanged). Chips stay on one line at 1024px and up, which the shorter labels allow. Takeaways wrap.
- **Footer** (replaces "Diluted EPS reads Cited: per-share figures are not matched to XBRL."): "Amounts in US dollars; B = billions.
  † Calculated from the two figures, to one decimal. Apple's filing rounds changes to whole percentages."
- **Caption** (visually hidden, landing): "Apple Inc. financial highlights for fiscal 2025 and fiscal 2024: figures, change and
  investor takeaway".
- **Phone cards** (below 768px). Labels "FY2025", "FY2024", "Change†"; the three groups on equal tracks while they fit,
  wrapping as today under enlarged text (R11).

### 3.4 Investor takeaways, for financial review

If Q2 keeps the takeaways editorial, these are the proposed lines; if the pipeline supplies them, these are the review criteria.
Each is pending a qualified reviewer.

| Row | Proposed takeaway | Support | Label |
|---|---|---|---|
| Revenue | "Services grew fastest of Apple's five categories, up 13.5%; iPhone, the largest, rose 4.2%." | Item 7, "Products and Services Performance" table: Services 109,158 vs 96,169; iPhone 209,586 vs 201,183 (USD millions). Changes calculated | Linked, not checked (segment lines are never checked) |
| Net income | "Outgrew revenue because the tax rate fell to 15.6% from 24.1%, which Apple's filing links mainly to the State Aid Decision. Pre-tax income rose 7.5%." | "…due to a $10.7 billion year-over-year decrease in the provision for income taxes related to the State Aid Decision…" (Item 7, Provision for Income Taxes); effective tax rate 15.6% vs 24.1% as filed; pre-tax income 132,729 vs 123,485 | Quote found in filing |
| Diluted EPS | "Rose faster than net income because diluted shares fell 2.6%; Apple bought back 402 million shares in fiscal 2025." | "During 2025, the Company repurchased 402 million shares of its common stock for $89.3 billion." (Note 10, Shareholders' Equity); diluted weighted-average shares 15,004,697K vs 15,408,095K | Quote found in filing |

"Mainly" rests on arithmetic: net income grew 13.1 points faster than revenue, and 12.0 of those points came after pre-tax income
(which grew 7.5%); the filing ties a $10.7 billion decrease to the State Aid Decision, more than the net $9.0 billion fall.

### 3.5 Replacing "The number you remember"

**Option A, recommended: "Follow one figure to the filing".** Purpose: turn the section's promise into a procedure the reader
can repeat, by showing one figure at each step from our table to the filing.

| Element | Copy |
|---|---|
| Title | Follow one figure to the filing |
| Lead | Revenue in the table above, traced to the line Apple filed. |
| Step 1 label · figure · note | In the highlights · $416.2B · Revenue, FY2025, rounded to billions |
| Step 2 | In Apple's 10-K · $416,161 million · Total net sales · Consolidated Statements of Operations · page 29 |
| Step 3 | In the filing's data · 416,161,000,000 USD · Year ended Sep 27, 2025 |
| Disclosure (closed) | Show the tag: us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax |
| Result | `{ }` Matches filing · Same number, rounded to billions. |
| Link | Open the statement on SEC.gov (visually hidden: "(opens in a new tab)") |

Layout: an ordered list; each step a label over a note, with its figure right-aligned to one edge in the data face; under
enlarged text the figure wraps below its label on its own width, keeping the reflow guarantees of
`catch-card-reflow.spec.ts`. No strike-through, no "wrong" colour. Three steps fill the card's height in the two-column row.

What it adds beyond the table: the figure as the filing prints it, in the filing's units; the company's own line name ("Total
net sales") beside ours ("Revenue"); the statement, the page and the period end; the tag, for readers who want it; and a working
route to the line. The table shows rounded numbers and a link to a 1.5 MB document. The card shows what "Matches filing" means
by doing it once.

**Option B: "What the labels don't cover".** Purpose: calibrate trust by stating the limits in one place. Copy: title "What the
labels don't cover"; body "Labels check figures and quotes, not conclusions. Per-share figures, ratios and segment results are
linked, not checked. The investor takeaways are interpretation; each carries the label of the passage it rests on." It is honest
and short, but it repeats the legend (the voice guide asks for scope once per surface) and gives the reader nothing to do. Its one
new sentence, on takeaways, is already in the legend's disclosure (§3.1).

The "memory" framing is dropped rather than reworded. It needs a wrong number to work, and a correct filed number cannot be
made wrong. The stale-answer point belongs to a comparison with a chatbot, which A4 rules out.

### 3.6 Trace to Source demo

| Element | Today | Proposed |
|---|---|---|
| Title | Trace to Source | Unchanged (the product's name for the feature) |
| Instruction | "Hover or tap the chip to see the section, the passage in the filing's own words, and a link into SEC EDGAR." | "The label opens the passage behind a sentence, in the filing's own words." |
| Claim | "Services net sales rose 13.5% to $109.2B on advertising, the App Store and cloud services." | "Apple says Services growth came from advertising, the App Store and cloud services." |
| Chip | Verified in filing | Quote found in filing |
| Panel header | Item 7 · Management's Discussion and Analysis | Item 7 · Products and Services Performance |
| Passage | (verbatim) | Unchanged |
| Status line | Verified against the original SEC filing | Found in the filing, word for word. |
| Link | Open in SEC EDGAR → document top | Open the passage on SEC.gov → `…aapl-20250927.htm#:~:text=Services%20net%20sales%20increased%20during%202025%20compared%20to%202024` |

The figures leave the demo; they belong to the table, where their own labels apply. `landingSamplesVerified.spec.ts` strips the
hash before comparing URLs, so the fragment passes it unchanged.

### 3.7 Removed

The label column's line and the lead paragraph (replaced by §3.1); "Periods compared: FY2025 vs FY2024" (identity line and
headers); the table footer's EPS sentence (the legend states the scope once); the demo's instruction, claim and status line; the
catch card.

---

## 4. Validation plan

### 4.1 Completed in this investigation

| Check | Method | Result |
|---|---|---|
| Figures, periods, units | SEC companyfacts API (fetched 2026-10-22), filtered to accession 0000320193-25-000079 and full-year durations; Python `Decimal`, half-up rounding | All six figures reconcile: 416,161 and 391,035; 112,010 and 93,736 (USD millions); 7.46 and 6.08 (USD per share). FY2025 runs 2024-09-29 to 2025-09-27, FY2024 2023-10-01 to 2024-09-28, 52 weeks each. Changes +6.426%, +19.495%, +22.697% round to the displayed +6.4%, +19.5%, +22.7% |
| Services figure and dimension | The filing's inline XBRL, contexts with `srt:ProductOrServiceAxis` = `us-gaap:ServiceMember` | 109,158 and 96,169 (scale 6, decimals −6, USD); +13.506%, displayed 13.5%; the filing prints 14 % |
| Filing version | SEC submissions index for CIK 320193 | 10-K filed 2025-10-31; no 10-K/A for FY2025 or FY2024 |
| Quotes and takeaway claims | Text of `aapl-20250927.htm` | The Services sentence appears once, in Item 7 under "Products and Services Performance"; the tax and repurchase sentences in §3.4 are verbatim; the claims check as in finding G |
| Figure-check logic | `build_metric_source` and `_value_appears_in_text` run verbatim, extracted with `ast` | Wrong-scale strings match; `prior_period` is never read |
| Layout | Production build, `next start` with no backend (as CI runs it), the container's Chromium; 1440, 1100, 800, 390 and 320px, 390px at 200% text, light and dark | Measurements in §1.2 #2; no horizontal scroll anywhere; catch amounts stack at 200% as designed |
| Automated accessibility | axe-core 4.10.3 on `#evidence` | 0 violations, 0 incomplete at 1440px light and dark and 390px light |
| Keyboard (Chromium, fine pointer) | Tab from a sentinel placed before the section | 6 stops, each with the brand focus ring; table-chip popovers open on focus; Tab then leaves for the next row |
| Demo behaviour | Hover, then click, the demo chip | Hover leaves the panel open; a click closes it |
| Accessibility tree | Playwright `ariaSnapshot` | Metric names are cells, not row headers; the strike-through is not exposed |

### 4.2 Success criteria, fixed before testing

Comprehension (§4.3), eight participants per round, run on today's design first as the baseline and then on the revision:

| ID | Task, asked without coaching | Pass | Target |
|---|---|---|---|
| T1 | "What period is the first column of numbers?" | Names fiscal 2025 and that it ended in September 2025 | ≥ 7 of 8 |
| T2 | "How much did net income change? Did Apple print that number?" | 19.5%, and that it is calculated | ≥ 6 of 8 |
| T3 | "What does the label on Revenue tell you? What doesn't it tell you?" | The figure was compared with the filing; the takeaway was not checked | ≥ 6 of 8 |
| T4 | "Which figure was not checked, and why might that be?" | Diluted EPS; per-share figures are not checked | ≥ 7 of 8 |
| T5 | "Show me where Apple's filing reports revenue." | Reaches the income statement line, or page 29, within 2 minutes | ≥ 6 of 8; median ease 5 or more of 7 |
| T6 | "Does anything here suggest one of Apple's figures is wrong?" | Says no | ≤ 1 of 8 says yes |
| T7 | "In the Trace to Source card, what exactly was found in the filing?" | The quoted words, not a figure | ≥ 6 of 8 |
| T8 | Through the session | Unprompted questions about a term in the primary copy (XBRL, EDGAR, Cited) | 0, each logged verbatim |

Accessibility: axe reports 0 violations at 1440 and 390px in both themes; the screen-reader checks in §4.4 pass; the keyboard
order follows the reading order; no horizontal scroll at 320 and 390px under 200% text (`reflow-200.spec.ts`).

Data: every displayed figure is within half a unit of its last shown digit of the filed value; every change recomputes at one
decimal; every quote is verbatim (the product's verifier); a qualified reviewer signs each takeaway.

Labels: the mapping test passes for every server state; the matcher's wrong-scale cases fail to match.

Decision rule: ship when every P0 criterion passes, T6 is at most 1 of 8, and T3 and T5 reach 6 of 8. Otherwise revise the copy
and run a second round.

### 4.3 Comprehension test protocol

- **Participants.** Eight per round: individual investors who hold single stocks and opened a 10-K, 10-Q or annual report in the
  last 12 months. Aim for five who do not know the term XBRL and three who do, screened by asking them to define it.
- **Format.** 30-minute moderated remote sessions, thinking aloud, on the Vercel preview at the participant's own screen size;
  two participants on phones. The moderator reads the tasks as written and does not explain terms; when asked, they say "What
  would you guess?" and log the question for T8.
- **Order.** Free look at the section for 60 seconds, then T1 to T7 in order; a one-line ease rating after T5.
- **Records.** Follow the beta protocol: consent first, verbatim answers kept in the private store, never a synthesized
  response. Score pass or fail against §4.2 before reading the round's totals.
- **Baseline.** Run round 0 on the current design (a preview of today's `main`) without holding back the interim fix (R1, R2):
  a preview of the earlier commit is enough.

### 4.4 Still required

| Check | Who | When |
|---|---|---|
| Comprehension rounds 0, 1 and, if needed, 2 | Founder, or a moderator the founder chooses | Round 0 now; round 1 after R6 to R8 reach a preview |
| Screen readers: VoiceOver with Safari on macOS and iOS, NVDA with Firefox and Chrome, TalkBack with Chrome. The table reads "Revenue, FY2025, $416.2B"; each chip's name says its state; the legend and receipt card read in order | Agent with a device, or the founder | After R3 and R6 |
| Touch: the chip's sheet opens, closes and returns focus on iOS and Android | Same | After R3 |
| Text fragments and the Inline XBRL viewer in Chrome, Safari and Firefox | Agent | R10 spike |
| Financial review of the takeaways (§3.4) and of the receipt card | A qualified reviewer (CPA or CFA level) | Before R8 ships |
| How many stored summaries carry a matched row with a scale mismatch (D) | Agent, read-only query | Before R4, to size the exposure |
| Done-gates after each PR: the frontend full gate, the touched e2e specs, both themes on the preview with the legacy-colour grep ([CLAUDE.md rule 11](../CLAUDE.md)) | Agent | Each PR |

---

## 5. Implementation order

1. **Founder decisions Q1 to Q4**, in one message.
2. **Interim fix**, today, frontend, routine tier: remove the strike-through and "That is the whole point" (or hide the catch card);
   fix the demo's instruction, claim and status line with today's labels (R1 interim, R2). This removes the two misleading
   signals without waiting for anything else.
3. **R4**, backend, reviewed as high: the matcher checks values with their scale, and both periods.
4. **R3, R5 and R9 together**: the shared label system, the voice guide, the design docs and a decisions-log entry
   superseding the "SEC XBRL" rule and D-012.
5. **Landing rebuild**: R7, the legend, R6, the receipt card (R1 final), R8; then R11.
6. **R10 spike**, folded into the receipt card's link.
7. **Comprehension round 1** on the preview; revise; round 2 if a target is missed.
8. **R12** when Apple files its FY2026 10-K.

Steps 3 and 5 can run in parallel; step 4 must not ship "after rounding" in its copy before step 3 has merged.

---

## 6. Open questions

- **Q1. Vocabulary scope.** Replace "SEC XBRL", "Cited" and "Verified in filing" across the product (recommended: the landing
  renders the product's components, so a landing-only change would describe labels the product does not show), or on the
  landing only? Either reverses the voice guide's "SEC XBRL" rule.
- **Q2. Takeaways.** Should the landing's takeaways be the AI's real output for this filing (a pipeline snapshot, with its
  evidence), or stay editorial with a label saying so?
- **Q3. A checked figure that does not match.** Show it labelled "Doesn't match filing", or withhold it?
- **Q4. Sample year.** When Apple files its FY2026 10-K, likely around 2026-10-30, move the sample to it, or keep FY2025 with
  its filed date shown?

---

## Appendix: reproducing the checks

- **SEC data**, with a declared User-Agent: `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json` (filter each concept's
  `USD` or `USD/shares` rows to `accn` 0000320193-25-000079 and durations over 300 days),
  `https://data.sec.gov/submissions/CIK0000320193.json` (form, filed and report dates), and the document
  `https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm` (verbatim sentences; Services in
  `ix:nonFraction` facts whose context carries the `ServiceMember` dimension). Concepts used: `RevenueFromContractWithCustomerExcludingAssessedTax`,
  `NetIncomeLoss`, `EarningsPerShareDiluted`, `IncomeTaxExpenseBenefit`,
  `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest`,
  `EffectiveIncomeTaxRateContinuingOperations`, `WeightedAverageNumberOfDilutedSharesOutstanding`.
- **Matcher probe.** Call `build_metric_source({"metric": "Revenue", "current_period": s, "prior_period": "$1.0B"}, filing,
  {"revenue": {"current": {"value": 416161000000}}}, None)` for each string in finding D and read `source_verified`.
- **Render.** From `frontend/`: `npm ci`, then `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 WAITLIST_MODE=false npm run build`
  and `npx next start`. Seed `localStorage` with `theme` and `cookie_consent` before load; set 200% text with the CDP call
  `Page.setFontSizes({ standard: 32, fixed: 26 })`, as `reflow-200.spec.ts` does. Measure painted text with DOM Ranges inside
  `#evidence`, and run axe on `#evidence`.
