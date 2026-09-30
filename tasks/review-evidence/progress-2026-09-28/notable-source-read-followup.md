# Bounded Notable source-read follow-up

## Prepared packet

The deterministic packet contains 12 public SEC candidates, 12 distinct issuers, all eight reasons
present in the cohort, and all six UTC days on which new cohort rows were first observed. The
database schema has no filing-title column; `company_name` is retained without inventing a title.
No URL was opened and no SEC request or model call was made while preparing the packet.

## Next read-only source pass

Review exactly the 12 retained candidates in `source-packet.json`; do not resample after seeing the
results. Use the existing SEC transport identity and shared limiter. Start with the retained filing
index URL for each row. If the index cannot establish the reason, open at most the filing's primary
document; cap the pass at 24 SEC responses total and stop rather than following exhibits or related
filings. Make no database, flag, job, Scheduler, IAM or account change.

For every row, record:

1. whether accession, form and filed date match the SEC source;
2. for an 8-K, whether the source identifies the item that maps to the stored reason;
3. for 10-K and S-1 rows, whether the stored form-derived reason matches the actual filing type;
4. a `pass`, `false_positive`, or `indeterminate` disposition with a short source locator;
5. any title visible in the SEC source as newly observed source evidence, never as a value claimed
   to have come from the database packet.

Keep quotations short; URL, item/section locator and a paraphrase are sufficient. Count precision
overall and by reason, but do not invent an acceptance threshold: the worksheet requires an
evidence-based product judgment. Record every false positive. An indeterminate source does not
become a pass.

## Decision boundary

Combine this source review with the completed seven-day ledger record and `aggregate.json`.
Engineering can then recommend retain or kill under the current delegation. The current packet
does not authorize `NOTABLE_FILINGS_ENABLED`, and a dark section's zero impressions/clicks remains
non-evidence. Root owns the feature disposition and any release.
