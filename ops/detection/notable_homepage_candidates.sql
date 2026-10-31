-- Detection: complete stored Notable window for the homepage curation comparison.
-- Complete stored serving window; no candidate LIMIT, user tables, source calls or writes.
-- Matches notable_filings_service.py's America/New_York date and inclusive seven-day floor.
-- A future-dated stored row is retained for diagnosis, as in the current serving query.
\pset format unaligned
\pset tuples_only on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
WITH clock AS (
    SELECT CURRENT_TIMESTAMP AS snapshot_at,
           (CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York')::date AS serving_day
), candidates AS (
    SELECT accession_number, ticker, cik, company_name, form, items, reason,
           filed_date, score, sec_url, first_seen_at, last_seen_at
    FROM notable_filings, clock
    WHERE filed_date >= clock.serving_day - 7
), latest_scan AS (
    SELECT started_at, finished_at, status
    FROM earningsnerd_job_runs
    WHERE job_name = 'notable-filings' AND status = 'succeeded'
    ORDER BY finished_at DESC NULLS LAST
    LIMIT 1
)
SELECT json_build_object(
    'schema_version', 1,
    'transaction_read_only', current_setting('transaction_read_only'),
    'snapshot_at', clock.snapshot_at,
    'serving_day', clock.serving_day,
    'window_start_inclusive', clock.serving_day - 7,
    'candidate_count', (SELECT count(*) FROM candidates),
    'future_dated_count', (SELECT count(*) FROM candidates WHERE filed_date > clock.serving_day),
    'latest_successful_scan', (SELECT row_to_json(latest_scan) FROM latest_scan),
    'candidates', COALESCE((
        SELECT json_agg(row_to_json(candidates) ORDER BY filed_date DESC, score DESC, accession_number)
        FROM candidates
    ), '[]'::json)
)
FROM clock;
COMMIT;
