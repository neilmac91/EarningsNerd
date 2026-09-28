-- Point-in-time readback, separate from the historical Cloud Monitoring window.
-- No SQL text, user names, client addresses, account rows or arbitrary counters are emitted.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '2s';
SET LOCAL TIME ZONE 'UTC';
SELECT json_build_object(
  'kind', 'current_database_snapshot',
  'observed_at', clock_timestamp(),
  'read_only', current_setting('transaction_read_only'),
  'max_connections', current_setting('max_connections')::integer,
  'superuser_reserved_connections', current_setting('superuser_reserved_connections')::integer,
  'reserved_connections', current_setting('reserved_connections', true),
  'connections_include_observer', true,
  'activity_visibility', 'state/user details may be restricted by database privileges',
  'backend_counts', (SELECT json_agg(row_to_json(counts)) FROM (
    SELECT backend_type, count(*) AS total,
      count(*) FILTER (WHERE state = 'active') AS active_visible,
      count(*) FILTER (WHERE state = 'idle') AS idle_visible,
      count(*) FILTER (WHERE state IS NULL) AS state_unknown,
      count(*) FILTER (WHERE usename = current_user) AS same_database_role
    FROM pg_stat_activity GROUP BY backend_type ORDER BY backend_type
  ) counts)
);
WITH matched AS MATERIALIZED (
  SELECT * FROM earningsnerd_job_runs
  WHERE job_name IN ('pregenerate', 'filing-scan', 'filing-digest', 'backfill-facts',
                     'earnings-calendar-refresh', 'earnings-day-alerts', 'notable-filings', 'retention-purge')
    AND started_at < :'readout_end'::timestamptz
    AND (finished_at IS NULL OR finished_at >= :'readout_start'::timestamptz)
  ORDER BY started_at
  LIMIT 1001
)
SELECT json_build_object(
  'kind', 'historical_job_ledger', 'observed_at', clock_timestamp(),
  'window_start', :'readout_start', 'window_end', :'readout_end',
  'row_limit', 1000, 'truncated', (SELECT count(*) > 1000 FROM matched),
  'unfinished_rows', 'unknown/stale candidates; NULL finish does not prove currently running',
  'counter_scope', 'allowlisted numeric counters only; absent values are unknown, not zero',
  'rows', (SELECT coalesce(json_agg(row_to_json(runs)), '[]'::json) FROM (
    SELECT job_name, started_at, finished_at, status,
      (SELECT jsonb_object_agg(key, value) FROM jsonb_each(coalesce(counters::jsonb, '{}'::jsonb))
       WHERE jsonb_typeof(value) = 'number' AND key IN (
         'processed', 'succeeded', 'failed', 'skipped', 'errors', 'extracted', 'pending',
         'filings_found', 'filings_created', 'summaries_generated', 'facts_extracted',
         'companies_processed', 'filings_processed', 'filings_remaining', 'extraction_errors',
         'processed_filings', 'inserted', 'rejected', 'facts_inserted', 'facts_skipped', 'facts_rejected', 'extract_errors', 'flags_refreshed',
         'value_mismatch', 'facts_unstored', 'companyfacts_unavailable', 'source_errors',
         'companies_scanned', 'filings_upserted', 'alerts_sent', 'alerts_failed',
         'digests_sent', 'digests_failed', 'filings_included', 'generated', 'already_cached',
         'commit_failed', 'generation_failed', 'missing_urls', 'unsupported_form', 'company_not_found'
       )) AS numeric_counters
    FROM matched
    ORDER BY started_at
    LIMIT 1000
  ) runs)
);
ROLLBACK;
