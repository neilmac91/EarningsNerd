# Bind a bare dollar figure copied from a scaled table to the table's declared scale

Date: 2026-09-27 · Area: AI pipeline / source units

**Context:** Candidate r's retained WMT 10-K output (run 1) rendered the maturities schedule as
"2027: $3,542; … Total: $38,166" from a table headed "(Amounts in millions)". The values were
source-exact; only the unit was lost, so every value-based check passed: `figure_trace` polices
dollar figures that carry a b/m/t scale word and deliberately ignores unit-less ones, and the
evals' numeric scorers match values across scale. A matching digit string in the source never
establishes the unit a sentence asserts.

**Rule:** a number's value and its unit are separate claims, and a matching digit string never
establishes either. A model-authored bare dollar figure ("2027: $3,542") may carry a scale word
only when the filing's own source document owns THAT proposition: the label the authored text pairs
with the figure is the leftmost cell of the table row of an inline-XBRL fact with exactly those
digits, whose unit is USD alone, whose `scale` attribute declares the multiplier, and whose context
ends on the filing's DEI report period. That is a row/period/amount mapping between the authored
claim and one source cell. Anything short of it abstains, byte-identical and with a reason: no
label beside the figure, no tagged fact, no row with that label, a per-share or foreign unit, a
fact that declares the bare reading (`scale="0"`), another period, disagreeing scales, no source
document, or a literal reading supported by standardized XBRL. Banners, flattened excerpt lines,
table geometry, header typography and whole-document digit scans are never read: five review
rounds showed each such heuristic moving the counterexample instead of removing it. Never rescale
the digits, never touch verbatim evidence, and record every abstention so an untouched figure is
visible in the audit rather than silently accepted.

**Evidence:** `app/services/ai/source_units.py::restore_table_cell_units` (proposition-bound owner,
applied on final and preview over the same source document, reusing the statement seam's `_text`
and DEI `source_report_period`; audit at `raw_summary["table_cell_unit_audit"]`, counter
`table_cell_units`);
`app/services/ai/figure_trace.py::policed_prose_slots` (one allowlist shared with the dollar gate);
gate `tests/unit/test_table_cell_units.py` over the retained WMT debt tables, contexts and DEI
period (`tests/fixtures/table_units/`): restored 7/7; unlabelled statements, unmatched rows,
per-share units, scale-0 facts, other periods, mixed scales, prose facts, later in-table
declarations and unknown banner exceptions untouched; banners and the flattened excerpt own nothing. Offline
replay over the 70 retained candidate-r outputs changed exactly one slot
(`tasks/review-evidence/financial-claim-scope-2026-09-27/`).
