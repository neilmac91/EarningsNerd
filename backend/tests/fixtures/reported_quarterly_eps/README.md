# Reported quarterly EPS source fixtures

These are complete public SEC Exhibit 99.1 HTTP entity bytes, gzip-compressed with
`mtime=0`. Retrieved October 10, 2026 using the application's existing
`SECEdgarServiceCompat.get_filing_attachment_bytes` transport, one request each.
Companion JSON files retain the URL, accession, CIK, filename, response metadata,
byte count and SHA-256 of the uncompressed representation.

- [META Q4 2023 earnings exhibit](https://www.sec.gov/Archives/edgar/data/1326801/000132680124000010/meta-12312023xexhibit991.htm)
- [META Q4 2024 earnings exhibit](https://www.sec.gov/Archives/edgar/data/1326801/000132680125000014/meta-12312024xexhibit991.htm)

The assertion reads the directly reported Basic/Diluted EPS pair from the
consolidated income statement's three-month column. Annual values and prior-year
quarters coexist in the table. No company-specific selection or value replacement
exists in application code. Synthetic controls in the unit test exercise rejected
geometry, dates, ambiguous amounts, non-GAAP metrics and share-class splits.

The helper supports an explicitly reviewed source manifest. It does not discover
historical earnings exhibits automatically; unsupported layouts abstain, and the
repair journal retains the selected raw table and transport receipt.
