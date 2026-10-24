# Read each companyfacts filing in its own currency and the series in its latest annual report's; a USD figure beside a filing's own currency is a convenience translation

Date: 2026-10-16, per-filing pick, stale-payload guard, convergence and the filing-currency switch rule 2026-10-24   Area: sec (financial facts)

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
its items carry in any taxonomy. It demotes every current row of its batch's concepts in another
currency amount or per-share unit, and every amount or per-share row under a filing whose own
currency is another: there a figure in the series currency is that filing's convenience
translation, which the syncs before #1365 and #1365's list pick stored. A ratio (`pure`) keeps its
unit across currencies, so the upsert's filing-date rule can keep one computed from other-currency
operands current and store the batch's calculation behind it; the writer then demotes the stale
ratio and promotes the batch's. A derived ratio with no filing owner and no recorded operands
predates provenance and was read from the USD lists, so it counts as USD-derived. It never rewrites
an identity: a ratio stored under the batch calculation's own identity (same filing) is corrected
by the journaled repair.

Make a fresh sync converge, never bookkeep per key incrementally. The upsert skips a stored identity
and never touches its `is_latest`, so the state an earlier sync or the per-filing writer left
decided the key: a stale payload, or the sync that names a new-currency 10-Q before the annual
report switches the series, demoted that report's rows and no later sync restored them; a lagging
sync made the payload's older figure current over a newer filing's demoted row; and the per-filing
writer's own rule (a current companyfacts row with no Filing row counts as newer) stored a 10-K/A
behind its original's row. Promoting only at a key with no current row left the last two for good:
each superseded figure the reviews found current after a fresh sync. So at every key the batch
presents in an amount or per-share unit, the writer makes the batch's own row there (same unit and
accession) the one current row and demotes every other there (`_promote_batch_rows`), whichever sync
or writer left the key so, outside four cases, each left as found: a key where a protected row of
the sync's view sits, current or not (below), so a lagging sync leaves a gap there, never the
batch's older figure; a quarantined batch row (provenance `unavailable`, any reason), never
promoted; a quarter whose unlabelled twin in that unit is current (the bulk writer's NULL-period
rule); and a proven switch, which promotes nothing. A sync whose payload names every stored filing
then leaves each key it presents one current row, its payload's winner, whatever came before; check
that by row, not by currency or count (the tests' `_checked_sync` asserts which row in every sync
outside a switch). Before widening or narrowing a promotion, read every writer that sets
`is_latest=False` and check that none leaves such a key empty on purpose.

Never let a payload demote a row of a filing it does not name and that was filed after it, in the
currency the sync reads, unless those newer filings' rows prove a switch (below) or that filing's
own stored rows vote another currency, and never make the payload's older figure current at a key
such a row holds, current or not. A sync can persist a payload older than stored rows: a delayed SEC
response, another process's earlier fetch, or the sync a new Filing triggers (the TTL bypass) before
SEC's companyfacts shows that filing. Such a row (`protected_rows`: its accession is not among the
payload's, and its filing date, its Filing row's else its provenance's `filed_at`, is strictly later
than the payload's newest `filed`) holds its key on both of the sync's paths, ratios included, while
it is in the payload's view (`_in_view`: an amount or per-share row in the series currency under a
filing whose stored rows vote no other currency, a ratio not computed from another currency's
operands, a share count) and those rows prove no switch (below). The ids go into the upsert, which
stores the batch's row behind one as behind a known newer filing, and into the currency step, which
never demotes one, demotes any other amount, per-share or ratio row current beside it, and promotes
nothing at a key where one sits: where it sits behind a later convenience translation this sync
demotes, the key is a gap until the sync that names its filing makes it current. A guard on the
currency step alone is not enough: the upsert's own demotion is per (concept, period, unit), and a
ratio's unit is the same in every currency. A newer filing's row outside that currency is not
protected: the sync that names its filing would demote it, so this one does, and no key holds two
currencies. Nor is one in that currency under a filing whose stored rows vote another (more of its
amount rows in one other currency than in any other, counted as the switch counts them below;
`_foreign`; every filing the payload does not name votes, newer or not): the sync that names the
filing reads that row as a convenience translation, so this one demotes it too, on both paths;
outside a switch the batch's own row then holds a key the batch presents, and a key it does not
present is a gap. Protecting every newer row in the series currency kept a CNY 20-F/A's USD capex
current against a payload that lagged only that amendment (FY2025 capex growth +9.1% against the
translation, +5.0% against the filer's restatement), while a stale pre-switch payload synced first
demoted it: the order of two syncs decided the number.

Prove a switch from a newer filing's own currency, never from one row, and only where that filing
would decide over the payload's own. The protected rows prove a switch (`_proven_switch`, defined
once in `currency.py`) when they are read as `filing_currencies` reads a payload: each newer
filing's own currency is the one more of its amount rows carry than any other, each counted once per
concept and period (not always a majority; per-share rows do not vote; a tie decides nothing); it
may decide when it is an annual report, holds a current row, its currency spans two period-ends, and
it outranks the payload's own deciding filing (`PayloadView.decider`) on `filing_currencies`' rank,
so it reports a period-end at least as late; the one reporting the latest period, then filed last,
decides. Ranking the newer filings only against each other let a CNY 20-F/A restating FY2023-24,
filed after a switcher's USD 20-F for FY2025, prove a switch back that the payload's own 20-F
outranked: the lagging sync kept only the amendment's two revenue years current. On a proven switch
no row is protected, the sync stores nothing from the payload, and it demotes every current amount
or per-share row of its concepts in another currency than the switch's, and every one in that
currency under a filing whose own currency is another: as this payload reads it (`PayloadView.own`),
else, for a filing it does not name, as that filing's stored rows vote (`Guard.own`). Those are the
convenience translations earlier syncs stored, which the sync that names every stored filing demotes
too; it promotes nothing and replaces no ratio. Demoting only the other currency left 20F-2022's USD
translation current beside the restated years (FY2023 growth -7.8% where the filer reported +1.8%),
and reading only the payload's view left a CNY 20-F/A's USD capex current where its stored rows were
mostly CNY (FY2025 capex growth against a translation). Neither middle way holds. Stored current,
the payload's own rows made FY2021-22 read CNY beside USD FY2023-25, so a growth figure across the
switch compared CNY with USD (a wrong number is worse than a gap). Stored not current, they add only
identities the sync naming every stored filing stores itself, and while that sync promoted nothing
at a held key they stranded an amendment or recast the payload carried behind its superseded figure.
A trigger on any one row is wrong both ways: a stray (one concept the per-filing pick read in
another currency) froze a domestic filer's sync, and a quarterly report filed ahead of the annual
report would wipe a whole history. Check such a rule by every concept's current amount rows reading
one currency across all periods, and by the stale sync's current amount rows against those the fresh
sync converges to (equal, or fewer wherever that sync makes current a row that is not current now;
Known gaps names the shapes the tests show, and the windows that leave more), never by the set
before and after the stale sync: the per-filing writer keeps `is_latest` per unit, so the state
before can already hold two currencies at one period. A newer filing in the payload's own currency
proves no switch: a payload that lags a stored 10-K still fills the years before it.

Known gaps: a switcher's current series holds only the periods its filings in the new currency
present (its earlier rows are demoted, not deleted, and stay readable by accession); a ratio at a
period the batch does not compute is left current, and so is one under a filing in another currency
(a margin carries no currency), and so is a stale ratio where the batch's own calculation is
quarantined; a filing that presents a single period in two currencies is a tie, so its items in the
series currency are read; a switch first reported in a 10-Q or 6-K, or a first annual report in the
new currency that tags one year, takes effect only with the next annual report presenting
comparatives, and until then the sync demotes that report's rows. The per-filing writer keeps
`is_latest` per unit, so opening an old-currency filing after a switch can add a current row in the
old currency, and a new filing's own rows in a new currency stand beside the old currency's until
the next companyfacts sync of the company, which reads one currency whether or not its payload
names that filing. A misjudged switch only picks between two views that each read one currency: a
gap, never a wrong number.

A sync whose payload lags a stored filing is not the fresh sync (one whose payload names every
stored filing), and each difference below lasts until the sync that names that filing, which
converges. A stale sync across a switch stores and promotes nothing, so it lacks each row the fresh
sync makes current and that is not current now. The tests show four such shapes: rows in the new
currency that no writer has stored yet (the switching report's derived or unextracted amounts; on a
switch back, the older filings' rows, so the stale sync keeps 2 of the fresh sync's 29 current
amount rows in the tests' switch back); the switching report's rows the per-filing writer's own rule
stored behind older ones; a new-currency quarterly report's rows that an earlier lagging sync, which
could prove no switch, demoted (it keeps 20 of the fresh sync's 22); and the switching report's rows
a later filing's row in the new currency demoted, which the stale sync demotes as a convenience
translation. Outside a switch, a key where a protected row sits behind another row is left as found:
a gap where the sync demoted that row as a convenience translation, and the original's figure where
the per-filing writer stored an amendment behind it. A row of a filing the payload does not name and
not known to be newer (no Filing row and no `filed_at`, or filed on or before the payload's newest
date) is not protected, so at a key the batch presents it yields to the batch's row, an older
filing's included. And the vote reads a filing's own currency from the stored units, the per-filing
writer's per-concept picks with their tie toward a non-USD code, so on both paths it can disagree
with the payload items the sync naming the filing reads, two ways. Where it names no other currency
but those items read another, a row in the sync's currency under the filing (a convenience
translation an earlier sync stored, or one concept the per-filing pick read in that currency) stays
current, a wrong number: the filing's stored amount rows, each counted once per concept and period,
current or not, tie for the most, or more of them are in the sync's currency than in any other (all
of them, where an earlier sync stored only its convenience rows), or it holds no amount row
(per-share rows do not vote); at a key the batch presents only a protected row of a newer filing
stays so. Where it names another currency than those items, the filing's rows in the sync's currency
are demoted: a gap at a key the batch does not present, and at one it presents from an older filing
that older figure, a wrong number (a probe's USD 10-Q whose picks read net income and cash flow in
EUR left Q1 2024 revenue at the original 250 where the 10-Q restated it at 260); and a newer 10-K
most of whose concepts those picks read in another currency proves a switch its payload items would
not (a gap). Both windows are recorded, not closed: nothing stored tells them from the common case
they share a key with, an old-currency report's convenience translation demoted beside a newer
filing's own row, where a gap would lose a right figure.

**Evidence**: `backend/app/services/facts/currency.py`;
`backend/app/services/facts/companyfacts.py::_collect_companyfacts_concepts`;
`backend/app/services/facts/quarterly.py`; `backend/app/services/facts/derive.py`;
`backend/app/services/facts/ingest.py::_persist_companyfacts_payload`;
`backend/tests/unit/test_companyfacts_ingest.py` (`TestNativeReportingCurrency`,
`TestFilingCurrencies`, `TestNativeReportingCurrencySync`); the peer panel's currency guard in
`backend/app/services/peers_service.py`; #1365 (the list-level pick); F61 call 3 (the per-filing
pick).
