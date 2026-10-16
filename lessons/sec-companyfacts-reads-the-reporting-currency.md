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
year sat in a series labelled CNY. Anchoring at the latest period-end instead failed the other way:
one stray foreign fact dated after every USD period took a domestic filer's whole series, and a
filer that switched from USD to CNY was read in CNY while its older USD years stayed current. The
question is not which currency is newest or widest but whether the USD list is a translation.

**Rule**: Read a companyfacts concept's foreign unit list only when its USD list is that list's
convenience translation: every USD period-end is also a foreign period-end
(`facts/currency.py::series_unit`). Among such lists, pick with the per-filing rule
(`edgar/instance/core.py::_reporting_currency`); never hard-code "USD", and never let one later or
wider list win on its own. Any other shape keeps the USD list, because a native read would leave
USD rows without a native twin current beside it. Carry the picked unit on every row and every
calculation built from it, and treat "additive" as "a currency amount" (`is_amount_unit`), not as
"USD". When a writer stores a native-currency row where a USD row is current at the same concept,
period end and fiscal period, it demotes that USD row itself (`demote_convenience_rows`) and never
deletes it. Known gaps: a switcher's years reported in a non-USD currency are not ingested in
that currency, and after a switch to USD its earlier years come from the USD convenience
translations, as before; a USD fact at a period-end the native list lacks (a stray, or a switch to
USD) puts that concept back on the USD list; and after such a flip, native rows an earlier sync
stored stay current beside the USD rows. Fixing them needs a per-filing pick and a product
decision.

**Evidence**: `backend/app/services/facts/currency.py`;
`backend/app/services/facts/companyfacts.py::_collect_companyfacts_concepts`;
`backend/app/services/facts/quarterly.py`; `backend/app/services/facts/derive.py`;
`backend/app/services/facts/ingest.py::_persist_companyfacts_payload`;
`backend/tests/unit/test_companyfacts_ingest.py` (`TestNativeReportingCurrency`,
`TestNativeReportingCurrencySync`); the peer panel's currency guard in
`backend/app/services/peers_service.py`.
