# Listing a company's filings: fetch the recent window in ONE call, and read cheap metadata fields — never edgartools properties that hit the network

Date: 2026-07-07   Area: sec

**Context**: The company filings list (`GET /api/filings/company/{ticker}`) failed outright for
mega-filers (Morgan Stanley: 105,377 lifetime filings across 44 submissions files) and was slow for
others. Two independent per-filing-count costs, both hidden inside the edgar layer:
1. `EdgarClient.get_filings` built a **fresh `EdgarCompany` per form type** and called
   `edgar_company.get_filings(form=ft)` with edgartools' default `trigger_full_load=True`, which
   downloads the company's **entire paginated submissions history** before filtering to the ~4
   report forms we show — repeated once per form type (5 in prod).
2. `_transform_filing` read `edgar_filing.period_of_report`. On `EntityFiling` that is **not** a
   plain attribute — it is a base-class `@property` that calls `self.sgml()`, a **live
   full-submission download from sec.gov per filing** (even `hasattr(f, 'period_of_report')`
   triggers it). So the listing did up to `limit × forms` extra SEC round-trips. The first-pass
   audit wrongly called the transform "metadata-only" because it avoided `filing_url` — a property
   can hide a network call that no `filing_url` grep will surface.

Both costs scale with filings, land the request past every timeout (inner 15s / router 20s / axios
30s), and — because the abandoned `run_in_executor` work can't be cancelled — exhaust the 4-thread
edgar pool and pressure the 1 GiB instance until the browser sees a connection-level error rendered
as "Unable to connect to the server".

**Rule**: To list a company's filings, make **one** `EdgarCompany` and **one**
`get_filings(form=[base forms], amendments=<bool>, trigger_full_load=False)` call — the recent
submissions window (SEC's "greater of ~1000 filings or ~1 year") always holds the newest
10-K/10-Q/20-F for an active filer; deeper history accrues in our DB across loads (serve **DB-first**,
refresh in the background). Pass **base** form strings + the `amendments` bool, never explicit `/A`
strings (edgartools' `amendments=False` path strips `/A` and would silently drop them). In any
transform of an edgartools listing object, read only fields the submissions JSON populates
(`report_date`, `primary_document`, `accession_number`, `filing_date`, `form`) — treat
`period_of_report`, `filing_url`, `.sgml()`, `.html()`, `.markdown()`, `.obj()` as network calls and
keep them off any path that runs per-filing over a list. When unsure whether an attribute is cheap,
open the edgartools source: an `@property` is a red flag.

**Evidence**: PR #573; `backend/app/services/edgar/client.py` (`get_filings_multi`,
`_transform_filing` → `report_date`), `compat.py` (single bulk call), `routers/filings.py` (DB-first
+ bounded `BackgroundTasks` refresh). edgartools 5.40.1: `edgar/entity/data.py:424-426`
(trigger_full_load gate), `edgar/_filings.py:1560` (`period_of_report` → `sgml()`),
`edgar/entity/filings.py:70` (cheap `report_date`). Regression gate:
`tests/unit/test_edgar_get_filings_multi.py` (asserts single `trigger_full_load=False` call and that
`period_of_report` is never accessed).
