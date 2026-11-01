# XBRL facts: select for the filing's OWN reporting period — fy/fp label the filing, not the fact

Date: 2026-07-06   Area: sec

**Context**: A filing's XBRL carries facts for many periods (comparatives, restatements).
Two independent hard-won rules: (1) the summary pipeline's primary extraction is
accession-aware (`edgar/instance_extractor.py`) — it selects facts for the filing's own
reporting period rather than trusting whatever the DataFrame surfaces first; (2) the
companyfacts ingest (Multi-Period Analysis) learned that a fact's `fy`/`fp` fields label
the REPORTING FILING, not the fact's period — quarter labels must be derived from the
fact's own duration window (distance-anchored Q1–Q4), with latest-filed-wins for
restatements and derived Q4 (FY − Q1..Q3, flows only, never EPS).

**Rule**: Never trust `fy`/`fp` as the fact's period. For per-filing metrics use the
accession-aware instance path; for time series classify by the fact's duration window. A
financial filer's (SIC 6000-6799) companyfacts revenue and the backfill's cross-check never
read the generic revenue tuple, whose first tag is the ASC 606 fee subset beside a bank's,
insurer's or REIT's total: they read `facts/fi_revenue.financial_revenue_tags` (the reported
total; the fee tag only on evidence that it is that total), and every
`normalize_companyfacts` and `extract_authoritative_values` call outside tests names its
filer, both gated by `backend/tests/unit/test_fi_revenue.py` (E264). The per-filing path reads
the same rule over the chosen filing's own facts and nothing else: its choice
(`edgar/instance/financial_revenue.py`) is the only revenue anchor of the statement reader's
bank and catch-all profiles and the generic list's only revenue candidate for a financial filer,
gated by `backend/tests/unit/test_instance_financial_revenue.py` (E278; its segment table and the
companyfacts fallback are still open there). E211's proxy step still reads the generic tuple
(E206). Concept list ORDERINGS encode tag priority — reordering one changes which tag wins on
multi-tagged filers, so treat the lists as behavior, not style.

**Evidence**: `backend/app/services/edgar/instance_extractor.py`;
`facts_service` companyfacts ingest + `test_companyfacts_ingest.py` (PR #552);
T9 anchor `test_companyfacts_fixture.py`; the S4 concept-list-unification deferral
(PR #551 body) documenting the ordering hazard; E264's `facts/fi_revenue.py` and
`backend/tests/fixtures/companyfacts_fi/`; E278's `edgar/instance/financial_revenue.py`, which
moved IBKR's FY2019 10-K from its $2.58B gross Revenues to its $1.94B net total on SEC's filing.
