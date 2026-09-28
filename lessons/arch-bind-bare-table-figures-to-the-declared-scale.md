# Bind a bare dollar figure copied from a scaled table to the table's declared scale

Date: 2026-09-27 · Area: AI pipeline / source units

**Context:** Candidate r's retained WMT 10-K output (run 1) rendered the maturities schedule as
"2027: $3,542; … Total: $38,166" from a table headed "(Amounts in millions)". The values were
source-exact; only the unit was lost, so every value-based check passed: `figure_trace` polices
dollar figures that carry a b/m/t scale word and deliberately ignores unit-less ones, and the
evals' numeric scorers match values across scale. A matching digit string in the source never
establishes the unit a sentence asserts.

**Rule:** a number's value and its unit are separate claims. When a model-authored bare dollar
figure ("$3,542") is a number the filing's own source document declares a scale for, the visible
text must carry that scale — and the declaration must be structural, never inferred from flattened
text: an inline-XBRL fact's own `scale`/unit attributes, or a `<td>` holding exactly that amount in
a `<table>` that declares its scale in its own cells (or in the one node immediately before it),
on a row and column not excluded from it. Flattened excerpt lines carry no table boundary, so a
list item, a short sentence or an adjacent unbannered table can never "inherit" a banner from
them; every occurrence of the digits in the document must be owned the same way, and the owner
abstains on any prose occurrence, a fact that declares the bare reading (`scale="0"`), disagreeing
scales, per-share/count/percent rows, columns or units, a table with no declaration of its own, a
generation with no source document, or a literal reading supported by standardized XBRL. Never
rescale the digits, never touch verbatim evidence, and record every abstention so an untouched
figure is visible in the audit rather than silently accepted. Heuristics over flattened text
(word counts, heading runs, capitalisation) were tried across three review rounds and each moved
the counterexample instead of removing it.

**Evidence:** `app/services/ai/source_units.py::restore_table_cell_units` (declared-scale owner,
applied on final and preview over the same source document, reusing the statement-source seam's
HTML cell helpers; audit at `raw_summary["table_cell_unit_audit"]`, counter `table_cell_units`);
`app/services/ai/figure_trace.py::policed_prose_slots` (one allowlist shared with the dollar gate);
gate `tests/unit/test_table_cell_units.py` over the retained WMT debt tables
(`tests/fixtures/table_units/`): restored 7/7; COST prose, BYND scale-0 fact, list items, adjacent
tables, per-share rows, share columns, mixed-scale, percent, non-dollar and XBRL-literal cases
untouched; the flattened excerpt owns nothing. Offline
replay over the 70 retained candidate-r outputs changed exactly one slot
(`tasks/review-evidence/financial-claim-scope-2026-09-27/`).
