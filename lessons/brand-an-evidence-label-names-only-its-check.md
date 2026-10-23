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
  "Quote found in filing", "Section linked"), from the one vocabulary module
  (`frontend/features/filings/lib/evidenceLabels.ts`); an acronym appears only as a technical detail
  behind a plain word.
- Before a label says "matched", read its check: which concept it maps (whole labels only), which
  periods it compares, whether it reads the scale. The label covers those and nothing more, and the
  check's tests carry the wrong-scale, wrong-digit and wrong-concept cases (`TestFigureCheck` in
  `backend/tests/unit/test_provenance_service.py`).
- Take a label's kind (a figure or a quote) only from a field the server sets and a model cannot write. A
  Copilot passage's section label is the model's own words and may start "XBRL ·", so "Matches filing"
  follows the fact payload the server sends (`fact`, admitted in `copilot-api.ts` parseCompletion), never
  the label (`tests/unit/copilotStream.spec.ts`, `tests/unit/CopilotMessage.spec.tsx`).
- Put a label on what was checked: never after a sentence whose figures its passage does not contain
  (`tests/unit/trace-to-source-demo.spec.tsx`), and never under a section name the passage did not
  come from (`_excerpt_section_ref`; `test_a_takeaway_passage_never_borrows_the_tables_section`).
- Never strike through, grey out or label as wrong a figure the filing states; a sample figure is filed
  or calculated (`tests/unit/marketingNoStrikethrough.spec.ts`). A meaning that rides on styling
  alone must also reach a screen reader.

**Evidence**: the founder's review and answers of 2026-10-22 (`docs/brand/decisions-log.md` D-058);
the probe and reconciliation in the plan's §4.1; commit 3bee6a5 (the check and the filed-value swap).
