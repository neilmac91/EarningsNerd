# Carry reconciliation quality through values, growth, citations and exports

Date: 2026-09-05   Area: arch

**Context**: WS-7 review found that analysis charts/grids, narrative sources and Excel could
display flagged facts without their reconciliation warning. A growth number can also depend
on an unreconciled earlier value even when its latest value is clean. A verified citation proves
the source match; it does not independently reconcile the underlying financial figure.

**Rule**: Compute growth-quality flags from the same inputs used for the calculation in the
backend. Preserve the point/derived-quality fields through every consumer, including citations,
chart exports and workbooks. Show quality independently of citation traceability.

**Evidence**: PR #697; backend `tests/unit/test_data_completeness.py` pins earlier-input growth,
citations, exported cell comments and PDF value/source warnings. Frontend metric/KPI/trend/narrative regression cases pin
the corresponding visible warnings; mutations removing these paths must fail those tests.

**Additional evidence (2026-10-11, analysis data notes)**: Repeated warnings made the same concern
look like many unrelated errors and widened metric columns. Group explanations once and carry the
same letters, reason identities and counts across the report and exports; keep a mark at each
figure whose note questions the number, and every note in the evidence dialog, the data notes and the
exports (D-061, 2026-10-25: a record-only `legacy_calculation` note, a gap and a missing check record mark
nothing; `frontend/tests/unit/dataNoteMarking.spec.tsx` holds the rule to the shared fixture's
`marked_letters`). Shared `backend/tests/fixtures/analysis_data_notes.json` cases are exercised by
Python and TypeScript. `test_analysis_data_notes.py`, `data-notes.spec.ts` and export tests pin the
shared groups and numeric-cell preservation. `analysis-presentation-api.spec.ts` rejects supplied
metadata that omits concerns or belongs to another snapshot before the stream becomes terminal;
an absent legacy field alone permits the older presentation fallback.

**Deployment compatibility (2026-10-11)**: Adding structured evidence does not update an
already-open browser tab. Keep the code-owned operand tail in its existing wire grammar until
those clients no longer depend on it; compact the reading prose and structured operand values
separately. Format the PDF's presentation copy without rewriting stored evidence. The shared
`analysis_legacy_evidence.json` fixture is pinned by the backend producer and consumed by the
unchanged frontend evidence parser in `narrative-pane.spec.tsx`; restoring whole-observation
formatting must fail this gate.

**Export count evidence (2026-10-11)**: A comparison can lack validation even when all selected
figures passed their checks. The shared `totals.unknown` counts figures only; PDF and workbook
summaries separately count unknown comparison memberships instead of implying that this total
covers both populations. `test_comparison_only_unknown_status_is_counted_in_pdf_and_workbook`
uses the shared annual-window fixture to check both rendered exports and preserve the source
dataset and totals unchanged.
