# Deterministic Notable source-packet selection

The cohort is every `notable_filings` row first observed in the half-open UTC interval
`[2026-09-21T00:00:00Z, 2026-09-28T00:00:00Z)`.

The sample is deterministic and capped at 20 rows:

1. Select one row for every reason, ordered by UTC observation day and then the MD5 of the public
   accession number.
2. Select one row for every UTC observation day not already represented by the reason seeds.
3. If fewer than 12 rows have been selected, add one row from previously unrepresented issuers,
   ordered by the MD5 of ticker plus accession, until the target of 12 is reached.
4. Sort the final packet by reason, observation day, ticker and accession. The internal observation
   day is used only to prove temporal coverage and is removed from each public candidate row.

The candidate packet contains only the table's public SEC metadata and the scanner's reason:
accession number, ticker, company name, form, 8-K items when present, reason, filed date and SEC
filing URL. The reviewed SQL does not select score because it can include user-demand boosts. The
schema has no filing-title column, so the packet retains `company_name` and does not invent a title.

This packet is source-review preparation. It does not visit the SEC URLs, validate the reason,
measure feature utility, or authorize a production flag change.
