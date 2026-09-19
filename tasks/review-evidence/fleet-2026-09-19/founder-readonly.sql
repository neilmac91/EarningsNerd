BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '15s';
SET LOCAL idle_in_transaction_session_timeout = '30s';
SET LOCAL TIME ZONE 'UTC';
SELECT transaction_timestamp() AS observed_at_utc,
       current_database() AS database_name,
       current_setting('max_connections') AS max_connections,
       current_setting('transaction_read_only') AS transaction_read_only,
       current_setting('lock_timeout') AS lock_timeout,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('idle_in_transaction_session_timeout') AS idle_in_transaction_session_timeout;

-- Latest and last successful attempt, preserving missing expected jobs.
WITH expected(job_name) AS (VALUES
 ('pregenerate'), ('filing-scan'), ('filing-digest'), ('backfill-facts'),
 ('earnings-calendar-refresh'), ('earnings-day-alerts'), ('notable-filings'),
 ('retention-purge'), ('data-quality-report'))
SELECT e.job_name, l.started_at AS latest_started_at,
       l.finished_at AS latest_finished_at,
       coalesce(l.status, 'never_observed') AS latest_status,
       l.error_type, s.finished_at AS last_success
FROM expected e
LEFT JOIN LATERAL (
 SELECT started_at, finished_at, status, error_type
 FROM public.earningsnerd_job_runs j WHERE j.job_name=e.job_name
 ORDER BY started_at DESC, id DESC LIMIT 1
) l ON true
LEFT JOIN LATERAL (
 SELECT finished_at FROM public.earningsnerd_job_runs j
 WHERE j.job_name=e.job_name AND status='succeeded' AND finished_at IS NOT NULL
 ORDER BY finished_at DESC LIMIT 1
) s ON true
ORDER BY e.job_name;

-- Latest twenty attempts per known identity; counters remain counts only.
WITH expected(job_name) AS (VALUES
 ('pregenerate'), ('filing-scan'), ('filing-digest'), ('backfill-facts'),
 ('earnings-calendar-refresh'), ('earnings-day-alerts'), ('notable-filings'),
 ('retention-purge'), ('data-quality-report'), ('refresh-stale'),
 ('universe-company-seed'), ('reconciliation-flag-audit'),
 ('remediate-financials'), ('backfill-company-sic'))
SELECT e.job_name, a.id, a.started_at, a.finished_at, a.status, a.error_type,
       (SELECT jsonb_object_agg(k, v)
        FROM jsonb_each(CASE WHEN jsonb_typeof(a.counters::jsonb)='object'
                       THEN a.counters::jsonb ELSE '{}'::jsonb END) AS c(k,v)
        WHERE jsonb_typeof(v) IN ('number','boolean')) AS numeric_counters
FROM expected e CROSS JOIN LATERAL (
 SELECT id, started_at, finished_at, status, error_type, counters
 FROM public.earningsnerd_job_runs j WHERE j.job_name=e.job_name
 ORDER BY started_at DESC, id DESC LIMIT 20
) a
ORDER BY e.job_name, a.started_at DESC, a.id DESC;

-- Aggregate actual identities, retaining maintenance names as separate rows.
SELECT job_name, status, count(*) AS attempts,
       min(started_at) AS first_started_at, max(started_at) AS last_started_at,
       max(finished_at) AS last_finished_at,
       count(*) FILTER (WHERE finished_at IS NULL) AS incomplete_attempts
FROM public.earningsnerd_job_runs
WHERE started_at >= transaction_timestamp() - interval '14 days'
GROUP BY job_name, status ORDER BY job_name, status;

SELECT job_name, id, started_at, status
FROM public.earningsnerd_job_runs
WHERE started_at >= transaction_timestamp() - interval '14 days'
  AND finished_at IS NULL
ORDER BY started_at LIMIT 200;
ROLLBACK;
