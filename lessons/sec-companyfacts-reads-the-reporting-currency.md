# Read each companyfacts concept in its reporting currency; a USD list beside it is a convenience translation

Date: 2026-10-16   Area: sec (financial facts)

**Context**: The companyfacts ingest read only `units["USD"]` (and `USD/shares`) for every concept.
A US-GAAP filer that reports in CNY (the Alibaba shape) also tags each 20-F's own year again as a
USD convenience translation, so the stored "USD history" was one figure per year, each at that
year's exchange rate. Multi-Period Analysis showed FY2023 revenue growth of -6.0% where the filing
reported +1.8%, and the peer panel ranked the filer against USD filers, because its rows were
labelled USD. The per-filing path already picked the native currency with `_reporting_currency`;
the full-history path had a second, hard-coded answer. Fixing the read alone was not enough:
`is_latest` is kept per unit, so the new CNY rows left the old USD rows current for the same
periods. Counting period-ends over the whole history was not enough either. A filer that switched
from CNY to USD still has more CNY period-ends, so its history was read in CNY, and the newest USD
year sat in a series labelled CNY.

**Rule**: Pick a companyfacts concept's unit list with the per-filing rule
(`edgar/instance/core.py::_reporting_currency`, reached through `facts/currency.py::series_unit`),
never a hard-coded "USD". Only a currency present at the latest period-end competes; that is the
full history's analogue of the filing's own period. Carry the picked unit on every row and every
calculation built from it, and treat "additive" as "a currency amount" (`is_amount_unit`), not as
"USD". When a writer stores a native-currency row where a USD row is current at the same concept,
period end and fiscal period, it demotes that USD row itself (`demote_convenience_rows`) and never
deletes it. The reverse direction is a known gap: a later pick of USD over current native rows
leaves both current. Fixing it needs the per-filing pick that a currency switcher would need.

**Evidence**: `backend/app/services/facts/currency.py`;
`backend/app/services/facts/companyfacts.py::_collect_companyfacts_concepts`;
`backend/app/services/facts/quarterly.py`; `backend/app/services/facts/derive.py`;
`backend/app/services/facts/ingest.py::_persist_companyfacts_payload`;
`backend/tests/unit/test_companyfacts_ingest.py` (`TestNativeReportingCurrency`,
`TestNativeReportingCurrencySync`); the peer panel's currency guard in
`backend/app/services/peers_service.py`.
