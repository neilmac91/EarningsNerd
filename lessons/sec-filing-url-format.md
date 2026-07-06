# SEC archive URLs: strip CIK leading zeros, strip accession dashes — and sec_url is NOT NULL

Date: 2026-07-06   Area: sec

**Context**: Filing archive URLs follow
`https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/` where `{cik}` has leading
zeros stripped (`320193`, not `0000320193`) and `{accession}` has dashes removed
(`000032019323000077`). Filings with NULL `sec_url` historically caused
`PendingRollbackError` cascades, so the model enforces NOT NULL via SQLAlchemy event
listeners (`before_insert` auto-generates sec_url from the accession; `before_update`
refuses to null it).

**Rule**: Build filing URLs only via `edgar/client.py`'s `_transform_filing()` — never
hand-format them. Never insert a Filing without `sec_url`/`document_url`; if corrupt rows
appear, use `backend/scripts/fix_null_sec_urls.py` (dry-run first).

**Evidence**: `backend/app/services/edgar/client.py` `_transform_filing()`;
`backend/app/models/__init__.py` Filing event listeners;
`backend/scripts/fix_null_sec_urls.py`.
