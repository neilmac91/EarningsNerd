# Read each companyfacts filing in its own currency and the series in its latest annual report's; a USD figure beside a filing's own currency is a convenience translation

Date: 2026-10-16, per-filing pick and stale-payload guard 2026-10-24   Area: sec (financial facts)

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
one stray foreign fact dated after every USD period took a domestic filer's whole series.

The first fix (#1365) read a foreign list only when the USD list was its convenience translation
(every USD period also in the foreign list), and kept the USD list otherwise. A choice made for a
whole unit list still misread two shapes (F61 call 3). A CNY-to-USD switcher kept the USD
convenience years of its CNY 20-Fs, so at that shape's year-end rates its FY2022 growth read -4.4%
where the filer reported +7.1%; a USD-to-CNY switcher lost its newest years; and one stray USD item
from a 20-F/A turned a CNY history into its USD convenience translations, while the CNY rows an
earlier sync stored stayed current beside them. The currency belongs to each filing, not to a list.

**Rule**: Pick the currency per filing, never per unit list over the whole history
(`facts/currency.py::filing_currencies`). A filing's (accession's) own currency is the one that
tags more of its kept amount items than any other, instants included, each counted once per tag,
period end and span through the collector's own `admitted_items`; a tie leaves the filing
undetermined. Never reuse `_reporting_currency`'s tie toward a non-USD code at filing level: one
stray EUR fact at a USD 10-K's own period-end would make that 10-K EUR. The series takes the
currency of the deciding filing, the one ranking highest on (an annual report, its currency spans
two period-ends, its latest period-end, filed): a one-period amendment or a later quarterly report
never flips it, and neither does a 10-K/A or 20-F/A restating an older year filed after the newer
annual report. The collector reads every concept in that currency and skips every item of a
filing whose own currency is another: never read a filing's convenience translation, never
hard-code "USD", and never let one later or wider list win on its own. `_reporting_currency` still
lives in that dependency-free module, which `edgar/instance/core.py` re-exports, so the normalizer
loads no Settings, ORM or EDGAR code when it runs. Carry the picked unit on every row and every
calculation built from it, and treat "additive" as "a currency amount" (`is_amount_unit`), not as
"USD".

`is_latest` is kept per unit, so the companyfacts writer corrects stored rows itself
(`demote_convenience_rows`), at any key with a fiscal period, whatever a row's source or filing,
for a USD series too, and never deletes one. It reads the payload's own view (`payload_view`): the
collector's very pick (`companyfacts_currencies`), and every accession and the newest `filed` date
its us-gaap items carry. It demotes every current row of its batch's concepts in another currency
amount or per-share unit, and every amount or per-share row under a filing whose own currency is
another: there a figure in the series currency is that filing's convenience translation, which the
syncs before #1365 and #1365's list pick stored. Where a demotion leaves a key the batch presents
with no current row, it promotes the batch's own row there (the upsert's known-filing-date rule can
store it behind the convenience row), never a quarantined one. A ratio (`pure`) keeps its unit
across currencies, so the upsert's filing-date rule can keep one computed from other-currency
operands current and store the batch's calculation behind it; the writer then demotes the stale
ratio and promotes the batch's. A derived ratio with no filing owner and no recorded operands
predates provenance and was read from the USD lists, so it counts as USD-derived. It never rewrites
an identity: a ratio stored under the batch calculation's own identity (same filing) is corrected
by the journaled repair.

Never let a payload demote what is newer than it. A sync can persist a payload older than stored
rows: a delayed SEC response, another process's earlier fetch, or the sync a new Filing triggers
(the TTL bypass) before SEC's companyfacts shows that filing. A demotion is permanent, because the
upsert skips a stored identity and never promotes it again, so a stale pre-switch payload once
demoted every newer-currency row (FY2025 included) and a fresh sync restored none. A row is
therefore protected on every path, ratios included, when its accession is not among the payload's
and its filing date (its Filing row's, else its provenance's `filed_at`) is later than the
payload's newest `filed`; a row with no known date is not protected.

Known gaps: a switcher's current series holds only the periods its filings in the new currency
present (its earlier rows are demoted, not deleted, and stay readable by accession); a ratio at a
period the batch does not compute is left current, and so is one under a filing in another
currency (a margin carries no currency); a filing that presents a single period in two currencies
is a tie, so its items in the series currency are read; a switch first reported in a 10-Q or 6-K,
or a first annual report in the new currency that tags one year, takes effect only with the next
annual report presenting comparatives. The per-filing writer keeps `is_latest` per unit, so
opening an old-currency filing after a switch can add a current row in the old currency, and a new
filing's own rows in a new currency stand beside the old currency's until a sync whose payload
names that filing demotes the old ones. The guard needs a filing date: a newer filing's row with
no Filing row and no `filed_at`, or one filed the same day as the payload's newest, is not
protected. A promotion happens only at a key this sync demoted, so a key emptied earlier stays
empty: a filer that switches currency and back keeps its pre-switch years demoted, since their
identities are stored and the upsert skips them.

**Evidence**: `backend/app/services/facts/currency.py`;
`backend/app/services/facts/companyfacts.py::_collect_companyfacts_concepts`;
`backend/app/services/facts/quarterly.py`; `backend/app/services/facts/derive.py`;
`backend/app/services/facts/ingest.py::_persist_companyfacts_payload`;
`backend/tests/unit/test_companyfacts_ingest.py` (`TestNativeReportingCurrency`,
`TestFilingCurrencies`, `TestNativeReportingCurrencySync`); the peer panel's currency guard in
`backend/app/services/peers_service.py`; #1365 (the list-level pick); F61 call 3 (the per-filing
pick).
