# SEC archive URLs: strip CIK leading zeros, strip accession dashes — and sec_url is NOT NULL

Date: 2026-07-06   Area: sec

**Context**: Filing archive URLs follow
`https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/` where `{cik}` has leading
zeros stripped (`320193`, not `0000320193`) and `{accession}` has dashes removed
(`000032019323000077`). Filings with NULL `sec_url` historically caused
`PendingRollbackError` cascades, so the model enforces NOT NULL via SQLAlchemy event
listeners (`before_insert` derives sec_url from the loaded Company's CIK + accession and
REFUSES to insert when the company is not loaded — it used to fabricate a `cik=0` placeholder;
`before_update` refuses to null it; both validate the URL shape: absolute URL, and canonical
archive form whenever the host is on SEC's domain).

**Rule**: Build filing URLs only via `app/utils/sec_urls.py::build_sec_archive_url()` (the
one builder; `edgar/client.py`, `integrations/sec_api.py`, the Filing listener and the repair
script all call it) — never hand-format them. Test fixtures either use canonical URLs or a
non-SEC host (`https://sec.example/...`); a hand-formatted SEC-hosted URL fails the listener. Never insert a Filing without `sec_url`/`document_url`; if corrupt rows
appear, use `backend/scripts/fix_null_sec_urls.py` (dry-run first).

**Evidence**: `backend/app/utils/sec_urls.py` (+ `tests/unit/test_filing_url_listeners.py`);
`backend/app/services/edgar/client.py` `_transform_filing()`;
`backend/app/models/__init__.py` Filing event listeners;
`backend/scripts/fix_null_sec_urls.py`.
