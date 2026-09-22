# Notable filings retain/kill worksheet v1 — blank

The scanner, job, stored candidates, homepage mount and client events already exist. Current server flag is off, so zero section impressions/clicks cannot decide utility. The founder owns retain/kill and any flag change. This worksheet asks for at least seven consecutive scheduled days of job and source evidence before that decision.

| Control | Receipt to fill |
|---|---|
| Candidate deployment SHA / service flag observation | `[ ]` / `[enabled or dark; UTC time]` |
| Seven-day UTC interval and expected scheduled slots | `[ ]` / `[ ]` |
| Observed successful / failed / missing job runs | `[ ] / [ ] / [ ]`; list every missing/failed slot |
| Stored distinct accessions / issuers; age p50/p95/max | `[ ]`; `[ ]` |
| Duplicate accessions / reason mix / source errors | `[ ] / [ ] / [ ]` |
| Editorial sample size and selection rule | `[bounded sample across reasons, days and issuers]` |
| EDGAR source checks | `[accession, form, filing date, reason evidence, false-positive disposition per card]` |
| Section impressions / card clicks / CTR | `[ ] / [ ] / [ ]`, only if section enabled and impressions observed |
| Reviewer recommendation; founder decision/date | `[retain/kill/pending with rationale]`; `[ ]` |

Read-only source queries below are candidate diagnostics; they require an authorized DB read and are not a substitute for inspecting EDGAR source documents. Replace the two UTC bounds and read actual job outcome semantics before running. The job-ledger role may lack `SELECT`; record `unavailable` rather than retrying or broadening that grant. `notable_filings` is pruned after 14 days, so the table cannot reconstruct missing older runs.

```sql
-- Candidate freshness, issuer diversity and reason mix in [start,end).
SELECT reason, count(*) AS candidates, count(DISTINCT accession_number) AS distinct_accessions,
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
GROUP BY reason ORDER BY candidates DESC;

-- At least seven consecutive scheduled days; inspect every expected slot.
SELECT id, started_at, finished_at, status, error_type, counters
FROM earningsnerd_job_runs
WHERE job_name = 'notable-filings'
  AND started_at >= :'window_start'::timestamptz
  AND started_at < :'window_end'::timestamptz
ORDER BY started_at;
```

Use `posthog.hogql` C for enabled-section impression/click counts. CTR denominator is observed section impressions; card clicks are absolute. Retain requires acceptable source precision, freshness, run reliability and a founder judgment that the card helps the chosen beta task. Kill records the observed reason and keeps the section dark. Do not treat a dark section's zero CTR as a kill signal or a successful seed as seven days of autonomous job health.
