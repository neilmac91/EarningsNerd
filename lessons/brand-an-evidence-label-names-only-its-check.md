# Give an evidence label plain words for exactly what its check covers, put it on what was checked, and never mark a filed figure wrong

Date: 2026-10-22   Area: frontend, brand, backend provenance

**Context**: The founder's annotated review of the landing page's evidence row
(`tasks/evidence-row-ux-plan-2026-10-22.md`) found the labels unreadable ("SEC XBRL", "Cited",
"SEC EDGAR") and the catch card absurd. Tracing them showed worse than jargon. "SEC XBRL" read as
if the SEC had checked the figure, and the check behind it matched a substring of the current
period only: "$416.2M" and "$416.9B" passed for Apple's $416,161M, the prior period was never read,
and "Services net sales" was compared with total revenue. The Trace demo put "Verified in filing"
after "13.5% to $109.2B", figures its quoted passage did not contain. Every takeaway passage
inherited the table's "Item 8. Financial Statements", though its sentence sat in Item 7. The catch
card struck through $391.0B, Apple's correct FY2024 figure, which the table above showed unstruck,
and a screen reader never heard the strike.

**Rule**:
- Write a label as plain words for what was checked ("Matches filing", "Linked, not checked",
  "Calculated from filing", "Quote found in filing", "Section linked", "Quote not found"), from the one vocabulary module
  (`frontend/features/filings/lib/evidenceLabels.ts`); an acronym appears only as a technical detail
  behind a plain word, and a link names SEC.gov, not EDGAR (`tests/unit/evidenceVocabulary.spec.ts`
  fails a retired label and a link that names EDGAR).
- A label names what its link opens and a search that ran. A passage the server could not find reads
  "Section linked" only when it names a section; with none, the link opens the filing, so it reads "Quote
  not found" (`passageLabel`; `tests/unit/SourceTraceLabels.spec.tsx`). With no filing text to search, no
  passage is cited at all (`test_cites_no_passage_without_filing_text_to_search`).
- Before a label says "matched", read its check: which concept it maps (whole labels only, each label
  the model is given mapped or listed with its reason: `TestLabelsTheModelIsGiven`), which periods it
  compares, whether it reads the scale and the currency. The label covers every figure its row shows
  and nothing more: a row whose shown prior has no comparable filed prior is not checked, and a
  balance-sheet prior is read against the filing's own earlier dates, since a 10-Q compares its quarter
  end with the fiscal year end. The check's tests carry the wrong-scale, wrong-digit, wrong-concept and
  wrong-period cases (`TestFigureCheck` in `backend/tests/unit/test_provenance_service.py`).
- Replace a figure only with the filed line its label names. A concept's extraction candidates differ
  in scope (cash with restricted cash, debt noncurrent or with current maturities, equity or net income
  with noncontrolling interests, "Revenues" beside net sales), so a figure that differs from a fact of
  another scope, or of a tag the extractor did not record, may be another line's, never a wrong one: the
  row is left unchecked (`_EXACT_SCOPE_TAGS`; `test_a_*_figure_is_replaced_only_by_the_line_its_label_names`).
- Take a label's kind (a figure or a quote) only from a field the server sets and a model cannot write. A
  Copilot passage's section label is the model's own words and may start "XBRL ·", so "Matches filing"
  follows the fact payload the server sends (`fact`, admitted in `copilot-api.ts` parseCompletion), never
  the label, and a figure the server computed (`value_kind`, admitted as `calculated`) reads "Calculated from
  filing": the filing does not state a growth rate it rounds to 6% (`tests/unit/copilotStream.spec.ts`,
  `tests/unit/CopilotMessage.spec.tsx`).
- Put a label on what was checked: never after a sentence whose figures its passage does not contain
  (`tests/unit/trace-to-source-demo.spec.tsx`), and never under a section name the passage did not
  come from (`_excerpt_section_ref`; `test_a_takeaway_passage_never_borrows_the_tables_section`).
- Never strike through, grey out or label as wrong a figure the filing states; a sample figure is filed
  or calculated (`tests/unit/marketingNoStrikethrough.spec.ts`, which reads every module the landing
  route reaches and every stylesheet they import). A meaning that rides on styling alone must also
  reach a screen reader.

**Evidence**: the founder's review and answers of 2026-10-22 (`docs/brand/decisions-log.md` D-058);
the probe and reconciliation in the plan's §4.1; commit 3bee6a5 (the check and the filed-value swap);
the expert review of #1530 on 2026-10-23, which found a $12B debt total that included current
maturities replaced by a $10B noncurrent fact and marked as matching.
