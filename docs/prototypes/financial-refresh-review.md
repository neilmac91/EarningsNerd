# Financial refresh review prototype

Default-off research prototype at `/labs/financial-refresh-review`. It demonstrates a decision workflow for updating a small financial worksheet. It has no navigation entry and requests no indexing.

## Run locally

Use the repository's pinned Node 22 version and existing locked frontend dependencies. From `frontend/`:

```bash
WAITLIST_MODE=false NEXT_PUBLIC_ENABLE_FINANCIAL_REFRESH_REVIEW=true npm run dev
```

Open `http://localhost:3000/labs/financial-refresh-review`. These are process-local settings; do not edit production configuration. Existing waitlist middleware otherwise redirects the lab before its route flag runs. Unset the new flag, or set it to `false`, to verify a 404 with local `WAITLIST_MODE=false`. Public flags are build-time values for `next build`/`next start`; restart or rebuild after changing them.

```bash
npx vitest run tests/unit/financial-refresh-review.spec.ts tests/unit/financial-refresh-review-ui.spec.tsx tests/unit/financial-refresh-review-route.spec.tsx
```

The browser spec checks the default-off route in the normal CI build. Run its enabled flow against a local enabled server with `NEXT_PUBLIC_ENABLE_FINANCIAL_REFRESH_REVIEW=true` in the Playwright process as well. Standard frontend lint, typecheck, full unit suite and build remain the repository gates.

## Real behavior and sample boundaries

The comparison, eligibility, decision, reset, CSV and JSON receipt code is real and deterministic. **All financial figures, company names and source IDs are fictional fixtures.** No SEC ingestion, backend API, database, live refresh, historical-vintage quality, payment entitlement or notification delivery is exercised. There are no new dependencies or secrets.

The six rows demonstrate a changed same-period comparative, a newer source with an unchanged value, a new period, a missing value, a currency mismatch and a valid zero. Accepting a source-only change is explicitly not a numerical revision. A revised comparative is not automatically a formal restatement. New periods require explicit scope selection and append alongside the baseline. Changing scope clears decisions. An unresolved/blocked row and a consciously kept baseline both preserve old values but have different receipt states.

The algorithm supports exact safe-integer sample amounts only. It performs no unit/scale/currency conversion, date parsing, general taxonomy matching, formulas or arbitrary workbook import. Inputs are code-owned, valid ISO-calendar fixture dates. A production adapter must validate external data once at ingress. It must preserve selected-accession identity, period type/range, units, dimensions and evidence; it cannot substitute latest companyfacts for missing historical data.

State is in React memory and resets on reload. Every export is explicitly marked fictional. CSV includes current values, period, unit, context, source and decision; JSON retains both the baseline and candidate plus comparison reasons. Formula/control-leading text is escaped for spreadsheet safety. No external SEC links are fabricated for sample records. Reset does not mutate the frozen baseline.

## Before production

Reuse the existing `facts_service.py:get_filing_fundamentals` and lineage owners for a bounded selected-filing adapter. Prove vintage availability and source correctness on actual filing pairs before claiming an as-filed service. Extend exact numeric support using the existing backend numeric contract; do not relax the prototype's integer restriction and silently round values. Add ownership/entitlement checks and persisted definitions/immutable receipts only in a separately reviewed backend change. Use the existing Excel export service for a same-shaped workbook whose values and provenance match the accepted snapshot. No production migration is included here.

Validate public-filing research demand with beta users before adding an Excel add-in, arbitrary model matching, forecasts or segment recasts. The separate research report describes competitor overlap, pricing hypotheses and validation gates. This route reuses the existing design system; it changes no shared visual convention or token.
