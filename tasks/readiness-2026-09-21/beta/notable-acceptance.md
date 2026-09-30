# Notable filings acceptance worksheet — September 28 readout

Codex's authorized disposition is **retain the implementation, defer activation**. The scanner's seven-day operational observation is complete, and the additive source follow-up resolves the four initial acquisition gaps. The corrected labels still require release verification before activation. The founder’s September 27 delegation makes Codex responsible for the evidence-based retain/defer/kill decision and any later bounded release, as recorded in the [authoritative handover](../../handover-astra-2026-09-19.md).

| Control | Observed evidence |
|---|---|
| Deployment / flag | Merge `e2df7031edc3e01088f2cdb8866fc49ae9a0e54c`; revision `00407-vv2`; retained 06:42 UTC release readback has `NOTABLE_FILINGS_ENABLED=false`. No flag changed. |
| Seven-day interval / expected slots | `[2026-09-21 00:00, 2026-09-28 00:00)` UTC; 14 twice-daily slots. |
| Successful / failed / missing | All 14 slots eventually succeeded; 0 missing. 18 ledger attempts: 14 succeeded, 4 failed. First attempts failed at 12:30 UTC on Sep 22, 23, 25 and 26; automatic retries recovered each. First-attempt slot success is 10/14. |
| Distinct accessions / issuers / age | 312 / 291; first-observed age p50 0.938 days, p95 and max 1.521 days. This age uses filing-date midnight, not SEC publication latency. |
| Duplicates / reason mix / source errors | 0 duplicates; 146 executive-change, 120 material-agreement, 27 earnings, 11 acquisition, 3 annual-report, 3 registration, 1 bankruptcy and 1 non-reliance candidate. Four failed job attempts reported source errors. |
| Sample / selection | Frozen 12 rows covering all 8 reasons, 6 first-seen days and 12 issuers; no replacement. |
| EDGAR source checks | Initial pass: 8 sources support bounded wording, 4 indeterminate. Additive follow-up: all 4 resolved with the same sample, using 9 successful application-transport requests with network permission (5 indices, 4 primaries). Initial sandbox failures did not establish SEC unavailability. |
| Actual visible-card acceptance | Initial UI review: 6 supported labels, **2 unsupported overclaims**, 4 indeterminate. BOXL and OPTU expose the overclaims. #1002 uses category-faithful labels; the combined source review supports those labels for all 12 frozen cards, subject to release verification. This is not a cohort-wide precision estimate. |
| Impressions / clicks / CTR | Not measured; section remains dark, so zero exposure cannot decide utility. |
| Decision / next action | Codex, Sep 28: retain/defer. Release the corrected labels, then verify a bounded activation/rollback plan. All four frozen source gaps are resolved. No founder reapproval is needed for this engineering work. |

The [decision receipt](../../review-evidence/progress-2026-09-28/notable-disposition.json), [cohort aggregate](../../review-evidence/progress-2026-09-28/notable-cohort-aggregate.json), [per-card source review](../../review-evidence/progress-2026-09-28/notable-review.md) and [current-UI integration review](../../review-evidence/progress-2026-09-28/notable-integration-review.md) preserve the different denominators and limits. The [additive source review](../../review-evidence/progress-2026-09-28/notable-followup-review.md) resolves INBP, SGMOQ, CD and AETN and adds primary-document support for OPTU. The original indeterminate results remain in their dated evidence. The single reviewed PUMP executive change and RIME acquisition do not validate those category labels for all Item 5.02 or 2.01 filings.

Read-only source queries below are candidate diagnostics; they require an authorized DB read and are not a substitute for inspecting EDGAR source documents. Replace the two UTC bounds and read actual job outcome semantics before running. Use the `ALL REASONS` row for the worksheet's cohort-wide distinct counts and age p50/p95/max; the other rows show the reason mix. The job-ledger role may lack `SELECT`; record `unavailable` rather than retrying or broadening that grant. `notable_filings` is pruned after 14 days, so the table cannot reconstruct missing older runs.

```sql
-- Candidate freshness, issuer diversity and reason mix in [start,end).
SELECT CASE WHEN GROUPING(reason) = 1 THEN 'ALL REASONS' ELSE reason END AS reason,
       count(*) AS candidates, count(DISTINCT accession_number) AS distinct_accessions,
       count(DISTINCT ticker) AS distinct_issuers,
       min(filed_date) AS oldest_filing, max(filed_date) AS newest_filing,
       percentile_cont(0.5) WITHIN GROUP
         (ORDER BY extract(epoch FROM (first_seen_at - (filed_date::timestamp AT TIME ZONE 'UTC')))/86400) AS age_days_p50,
       percentile_cont(0.95) WITHIN GROUP
         (ORDER BY extract(epoch FROM (first_seen_at - (filed_date::timestamp AT TIME ZONE 'UTC')))/86400) AS age_days_p95,
       max(extract(epoch FROM (first_seen_at - (filed_date::timestamp AT TIME ZONE 'UTC')))/86400) AS age_days_max,
       count(*) - count(DISTINCT accession_number) AS duplicate_accessions
FROM notable_filings
WHERE first_seen_at >= :'window_start'::timestamptz
  AND first_seen_at < :'window_end'::timestamptz
GROUP BY ROLLUP(reason)
ORDER BY GROUPING(reason) DESC, candidates DESC;

-- At least seven consecutive scheduled days; inspect every expected slot.
SELECT id, started_at, finished_at, status, error_type, counters
FROM earningsnerd_job_runs
WHERE job_name = 'notable-filings'
  AND started_at >= :'window_start'::timestamptz
  AND started_at < :'window_end'::timestamptz
ORDER BY started_at;
```

Use `posthog.hogql` C for enabled-section impression/click counts. CTR denominator is observed section impressions; card clicks are absolute. Retain requires acceptable source precision, freshness, run reliability and an evidence-based Codex product judgment that the card helps the chosen beta task. Kill records the observed reason and keeps the section dark. Do not treat a dark section's zero CTR as a kill signal or a successful seed as seven days of autonomous job health.
