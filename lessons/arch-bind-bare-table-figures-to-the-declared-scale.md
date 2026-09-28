# Bind a bare dollar figure copied from a scaled table to the table's declared scale

Date: 2026-09-27 · Area: AI pipeline / source units

**Context:** Candidate r's retained WMT 10-K output (run 1) rendered the maturities schedule as
"2027: $3,542; … Total: $38,166" from a table headed "(Amounts in millions)". The values were
source-exact; only the unit was lost, so every value-based check passed: `figure_trace` polices
dollar figures that carry a b/m/t scale word and deliberately ignores unit-less ones, and the
evals' numeric scorers match values across scale. A matching digit string in the source never
establishes the unit a sentence asserts.

**Rule:** a number's value and its unit are separate claims, and neither a matching digit string
nor a matching label establishes either. A deterministic unit repair may touch a model-authored bare
dollar figure only inside a finite, named proposition whose every part the filing's own source owns:
today the one supported proposition is the complete long-term-debt maturity sequence ("[Annual]
maturities of long-term debt … as follows: 2027: $3,542; …; Thereafter: $N; Total: $N"), bound to
the filing's tagged schedule concepts and total (`debt_concepts.DEBT_MATURITY_SEQUENCE`) on the DEI
issuer's own consolidated report-date instant (CIK, period kind, date, no dimension member, all
normalized from the context itself) — measure by concept, basis by the sum identity, period and
entity by context identity, unit and scale by the fact's own attributes, row by label, order by
position. Anything else abstains, byte-identical
and with a reason: another subject or qualifier, a reordered, partial or already-scaled sequence,
trailing text, a missing, conflicting, non-USD, scale-0 or other-period fact, a mismatched amount,
row or year, a schedule that does not sum, no source document, or a literal reading supported by
standardized XBRL. Banners, flattened excerpt lines, table geometry, header typography,
whole-document digit scans and label-only binding are never read: six review rounds showed each
such mechanism moving the counterexample instead of removing it. A second proposition is a second
named grammar with its own source binding and gate, never a loosening of this one. Never rescale the
digits, never touch verbatim evidence, and record every abstention so an untouched figure is visible
in the audit rather than silently accepted.

**Evidence:** `app/services/ai/source_units.py::restore_table_cell_units` (the finite maturity
proposition owner, applied on final and preview over the same source document, reusing the
statement seam's `_text`, DEI `source_report_period` and the hand-audited
`debt_concepts.DEBT_MATURITY_SEQUENCE`; audit at `raw_summary["table_cell_unit_audit"]`, counter
`table_cell_units`);
`app/services/ai/figure_trace.py::policed_prose_slots` (one allowlist shared with the dollar gate);
gate `tests/unit/test_table_cell_units.py` over the retained WMT debt tables, contexts and DEI
period (`tests/fixtures/table_units/`): the retained bullet restored 7/7; every other subject,
qualifier, order, partial or scaled sequence, and every missing, conflicting, mismatched, non-USD,
scale-0, other-period or non-summing source untouched; banners, labels and the flattened excerpt
own nothing. Offline
replay over the 70 retained candidate-r outputs changed exactly one slot
(`tasks/review-evidence/financial-claim-scope-2026-09-27/`).
