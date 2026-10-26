# Read a filing's facts at its company and accession, never by `filing_id`: it names the writer, not the filing

Date: 2026-10-26   Area: arch

**Context**: the filing page's annual chart (`GET /api/filings/{id}/fundamentals`) read
`financial_fact` rows with `filing_id == id`. The fact identity (company, concept, period end,
fiscal period, unit, accession) holds the accession, and both fact writers skip an identity already
stored. A companyfacts sync stores each period's winner under the accession of the filing that
reported it last, with no filing owner, so when a sync ran before a filing's own facts were written
the per-filing writer stored nothing for those cells: the newest 10-K got no rows at all (its chart
was empty) and an older one lost its oldest year and older balance. WP5b's own-report rows (a
year's value from its own report, kept beside a restated winner) hold an older report's own-year
cell the same way. Reproduced through both real writers in
`backend/tests/unit/test_filing_fundamentals_by_accession.py`.

**Rule**: select one filing's facts with `company_id == filing.company_id` and
`accession == filing.accession_number`, current or not. Treat `filing_id` as ownership only (which
writer stored a row: `is_(None)` / `isnot(None)`), never as a key to a filing's figures. A row
another writer stored under the filing's accession is that filing's figure when it is a reported
item, or a calculation whose every recorded operand carries the same accession
(`fact_provenance.operands_within_accession`): a companyfacts calculation takes its first operand's
accession, so its other operand may be a later filing's. Keep another company's rows out (a combined
report shares one accession), keep each line in one currency, and show such a row under the year the
filing's own rows count to its period end: writer generations name a year differently.

**Evidence**: `backend/app/services/facts/filing_scope.py::annual_filing_rows`, read by
`facts/fundamentals.get_filing_fundamentals`; the Copilot already scoped by accession
(`copilot_tools._scope`). Partly gated by `backend/tests/unit/test_filing_facts_read_by_accession.py`,
which counts every mention of `FinancialFact.filing_id` through the model in `backend/app`,
`backend/scripts`, `backend/evals` and `backend/main.py` against a reviewed list; a comparison of a
loaded row's `filing_id` or a copied state's key, and a name built at run time, are review-checked.
