# Format XBRL figures with the payload's reporting currency, never a default dollar sign

Date: 2026-10-09   Area: frontend (change report) / dashboard feed payload

**Context**: PR #1133 rebuilt the What Changed card as a Metric · Prior · Current · Change table and
formatted the raw `current` / `prior` XBRL amounts with `fmtCurrency(value)`, whose currency defaults
to USD. The change-report payload carried no currency, and the XBRL extractor keeps a foreign private
issuer's figures in its own reporting currency, so a DKK filer's 309B would have read "$309B" (the
same mislabel `xbrl_narrative.py` guards against in prose). `main` had only ever rendered the
currency-neutral `display` percentage, so the defect was new to the PR. A read-only PR sweep and two
independent review lenses confirmed it.

**Rule**: a surface that renders a raw XBRL amount takes its currency from the payload — the
report-level `reporting_currency` or a fact's `unit` through `currencyFromUnit` — and passes it to
`fmtCurrency`. When the payload names none, show a bare scaled figure (`fmtScale`: "394.3B") rather
than falling back to "$". A payload that starts exposing raw amounts carries the currency alongside
them in the same change (an additive field), and the component's spec pins a non-USD case and the
no-currency case.

**Evidence**: `frontend/features/filings/components/WhatChanged.tsx` (`figure`, `reportCurrency`),
`backend/app/services/dashboard_feed_service.py` (`compute_what_changed` → `currency`),
`frontend/tests/unit/what-changed.spec.tsx` (DKK and no-currency cases),
`backend/tests/unit/test_dashboard_feed.py::test_reporting_currency_rides_on_the_metrics`;
precedents `FundamentalsTrendChart.tsx` / `PeerComparisonPanel.tsx` (`currencyFromUnit`).
Open, pre-existing: `FinancialMetricsTable.tsx` still formats with the USD default — apply this rule
on its next touch.
