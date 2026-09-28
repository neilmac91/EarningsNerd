# Bind a bare dollar figure copied from a scaled table to the table's declared scale

Date: 2026-09-27 · Area: AI pipeline / source units

**Context:** Candidate r's retained WMT 10-K output (run 1) rendered the maturities schedule as
"2027: $3,542; … Total: $38,166" from a table headed "(Amounts in millions)". The values were
source-exact; only the unit was lost, so every value-based check passed: `figure_trace` polices
dollar figures that carry a b/m/t scale word and deliberately ignores unit-less ones, and the
evals' numeric scorers match values across scale. A matching digit string in the source never
establishes the unit a sentence asserts.

**Rule:** a number's value and its unit are separate claims. When a model-authored bare dollar
figure ("$3,542") matches a whole source table cell, the visible text must carry the scale that
table declares, and the owner that restores it must abstain whenever the source itself is
ambiguous: the issuer's own prose writes the figure bare (COST-style section conventions), the
digits occur under different banners, the row is excluded from the scale (per-share, counts), the
banner is not in dollars, the cell cannot be bound to its banner through the table's own block
(header block, rows, capitalised statement headings, labels directly above their values — never a
heading count), or a literal reading is supported by standardized XBRL. Never rescale the
digits, never touch verbatim evidence, and record every abstention so an untouched figure is
visible in the audit rather than silently accepted.

**Evidence:** `app/services/ai/source_units.py::restore_table_cell_units` (declared-scale owner,
applied on final and preview through the same supplied excerpt; audit at
`raw_summary["table_cell_unit_audit"]`, counter `table_cell_units`);
`app/services/ai/figure_trace.py::policed_prose_slots` (one allowlist shared with the dollar gate);
gate `tests/unit/test_table_cell_units.py` (retained WMT lines restored 7/7; BA/COST prose,
mixed-scale, percent, share-count, non-dollar-banner and XBRL-literal cases untouched). Offline
replay over the 70 retained candidate-r outputs changed exactly one slot
(`tasks/review-evidence/financial-claim-scope-2026-09-27/`).
