# Label an XBRL amount with the filer's reporting currency, never with a default dollar sign

Date: 2026-10-09   Area: frontend (with a backend payload field)

**Context**: The 2026-10 critique's change report added Prior and Current columns, formatted with
`fmtCurrency(value)`, whose currency defaults to USD. The change report's metric items are raw XBRL
amounts in the filer's own reporting currency, and FPI filings (20-F, 40-F, 6-K) are on in
production, so a yen filer's revenue would have read "$37.2T → $45.1T" and its EPS "$179.47". The
old chips showed only the server's percentage, which has no currency, so the bug arrived with the
new columns. An isolated review caught it before merge.

**Rule**: A component that formats a raw XBRL amount takes the currency from the payload that
carries the amount (the change report's `reporting_currency`, validated to an ISO 4217 code on the
backend from the stored XBRL) and passes it to `fmtCurrency({ currency })`. When the payload has no
currency, show the amount without one (`fmtScale`), never as dollars. A percentage or a
server-formatted display string needs no currency; an absolute amount always does.

**Evidence**: `frontend/features/filings/components/WhatChanged.tsx` `figure()`;
`backend/app/services/change_report_service.py` `_reporting_currency`;
`frontend/tests/unit/what-changed.spec.tsx` ("amounts in the filer's own currency": ¥ for JPY, no
symbol when unknown) and `backend/tests/unit/test_change_report_service.py`
(`test_reporting_currency_*`). The backend's own guard for summaries is
`app/services/ai/markdown_render.py` ("must never mislabel a non-USD filer as dollars").
