-- Fixed incident identities plus a bounded current active-job sample. No write or arbitrary input.
-- Reference thresholds below are NOT a runtime-settings read and do not diagnose scheduler success.
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '2s';
SET LOCAL TIME ZONE 'UTC';
WITH
expected(filing_id, accession, form) AS (
  VALUES (45003, '0000872589-26-000034', '10-Q'), (45004, '0000872589-26-000032', '8-K')
),
identities AS MATERIALIZED (
  SELECT e.filing_id,
    CASE WHEN f.id IS NULL THEN 'missing_filing'
         WHEN f.accession_number = e.accession AND f.filing_type = e.form
           AND c.cik IN ('872589', '0000872589') THEN 'matched'
         ELSE 'identity_mismatch' END AS identity_state
  FROM expected e LEFT JOIN filings f ON f.id = e.filing_id
  LEFT JOIN companies c ON c.id = f.company_id
),
active_sample AS MATERIALIZED (
  SELECT id, status, created_at, next_attempt_at, last_dispatched_at, lease_until
  FROM earningsnerd_summary_jobs
  WHERE status IN ('queued', 'running', 'retry_wait')
  ORDER BY created_at, id
  LIMIT 1001
),
active_retained AS MATERIALIZED (SELECT * FROM active_sample ORDER BY created_at, id LIMIT 1000),
details AS MATERIALIZED (
  SELECT i.filing_id, i.identity_state, j.id IS NOT NULL AS job_present,
    j.generation, j.attempts, j.system_funded,
    CASE WHEN j.status IN ('queued', 'running', 'retry_wait', 'complete', 'partial', 'failed')
      THEN j.status ELSE 'unknown' END AS status,
    CASE WHEN j.stage IN ('queued', 'initializing', 'fetching', 'parsing', 'analyzing',
                         'summarizing', 'saving', 'completed', 'partial', 'error')
      THEN j.stage ELSE 'unknown' END AS stage,
    CASE WHEN j.charge_state IN ('unreserved', 'reserved', 'charged', 'settled', 'refunded')
      THEN j.charge_state ELSE 'unknown' END AS charge_state,
    j.created_at, j.updated_at, j.lease_until, j.next_attempt_at, j.last_dispatched_at,
    j.error_code IS NOT NULL AS error_recorded,
    (j.status = 'running' AND j.lease_token IS NOT NULL AND isfinite(j.lease_until)
      AND j.lease_until > transaction_timestamp()) IS TRUE AS active_owner,
    CASE WHEN j.lease_token IS NULL AND j.lease_until IS NULL THEN 'absent'
         WHEN j.lease_token IS NULL OR j.lease_until IS NULL THEN 'inconsistent'
         WHEN NOT isfinite(j.lease_until) THEN 'nonfinite'
         WHEN j.lease_until <= transaction_timestamp() THEN 'expired' ELSE 'live' END AS lease_state,
    CASE WHEN j.summary_id IS NULL THEN 'absent'
         WHEN s.id IS NULL THEN 'missing'
         WHEN s.filing_id <> j.filing_id THEN 'wrong_filing' ELSE 'matching_filing' END AS result_reference,
    CASE WHEN j.reservation_token IS NULL THEN 'absent'
         WHEN r.token IS NULL THEN 'missing'
         WHEN r.user_id IS DISTINCT FROM j.user_id OR r.kind <> 'summary' THEN 'wrong_owner_or_kind'
         WHEN r.month !~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN 'invalid_month'
         WHEN NOT isfinite(r.expires_at) THEN 'nonfinite'
         WHEN r.expires_at <= transaction_timestamp() THEN 'expired' ELSE 'live' END AS reservation_reference,
    CASE WHEN j.charge_month IS NULL THEN 'absent'
         WHEN j.charge_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN 'valid_shape'
         ELSE 'invalid_shape' END AS charged_month_shape
  FROM identities i
  LEFT JOIN earningsnerd_summary_jobs j ON j.filing_id = i.filing_id AND i.identity_state = 'matched'
  LEFT JOIN summaries s ON s.id = j.summary_id
  LEFT JOIN earningsnerd_usage_reservations r ON r.token = j.reservation_token
),
intervals AS (
  SELECT d.filing_id, v.name,
    CASE WHEN v.value IS NULL THEN 'absent'
         WHEN NOT isfinite(v.value) THEN 'nonfinite'
         WHEN v.value < transaction_timestamp() - interval '30 days' THEN 'past_bound'
         WHEN v.value > transaction_timestamp() + interval '30 days' THEN 'future_bound'
         ELSE 'bounded' END AS state,
    CASE WHEN v.value BETWEEN transaction_timestamp() - interval '30 days'
                          AND transaction_timestamp() + interval '30 days'
         THEN trunc(extract(epoch FROM (v.value - transaction_timestamp())))::bigint
         ELSE NULL END AS seconds_from_snapshot
  FROM details d CROSS JOIN LATERAL (VALUES
    ('created', d.created_at), ('updated', d.updated_at), ('lease_until', d.lease_until),
    ('next_attempt', d.next_attempt_at), ('last_dispatch', d.last_dispatched_at)
  ) v(name, value)
),
coordinator AS MATERIALIZED (
  SELECT next_admission_at, cooldown_until FROM earningsnerd_sec_request_gate WHERE id = 1 LIMIT 1
),
coordinator_intervals AS (
  SELECT v.name,
    CASE WHEN v.value IS NULL THEN 'absent'
         WHEN NOT isfinite(v.value) THEN 'nonfinite'
         WHEN v.value < transaction_timestamp() - interval '30 days' THEN 'past_bound'
         WHEN v.value > transaction_timestamp() + interval '30 days' THEN 'future_bound'
         ELSE 'bounded' END AS state,
    CASE WHEN v.value BETWEEN transaction_timestamp() - interval '30 days'
                          AND transaction_timestamp() + interval '30 days'
         THEN trunc(extract(epoch FROM (v.value - transaction_timestamp())))::bigint
         ELSE NULL END AS seconds_from_snapshot
  FROM coordinator c CROSS JOIN LATERAL (VALUES
    ('next_admission', c.next_admission_at), ('cooldown', c.cooldown_until)
  ) v(name, value)
)
SELECT json_build_object(
  'schema_version', 1,
  'read_only', current_setting('transaction_read_only'),
  'isolation', current_setting('transaction_isolation'),
  'observed_at', transaction_timestamp(),
  'filings', (SELECT json_agg(json_build_object(
    'filing_id', d.filing_id, 'identity', d.identity_state, 'job_present', d.job_present,
    'generation', d.generation, 'attempts', d.attempts, 'system_funded', d.system_funded,
    'status', d.status, 'stage', d.stage, 'charge_state', d.charge_state,
    'error_recorded', d.error_recorded, 'active_owner', d.active_owner, 'lease_state', d.lease_state,
    'result_reference', d.result_reference, 'reservation_reference', d.reservation_reference,
    'charged_month_shape', d.charged_month_shape,
    'times', (SELECT json_object_agg(t.name, json_build_object(
      'state', t.state, 'seconds_from_snapshot', t.seconds_from_snapshot))
      FROM intervals t WHERE t.filing_id = d.filing_id)
  ) ORDER BY d.filing_id) FROM details d),
  'active_jobs', json_build_object(
    'retained', (SELECT count(*) FROM active_retained),
    'truncated', (SELECT count(*) > 1000 FROM active_sample),
    'queued', (SELECT count(*) FROM active_retained WHERE status = 'queued'),
    'running', (SELECT count(*) FROM active_retained WHERE status = 'running'),
    'retry_wait', (SELECT count(*) FROM active_retained WHERE status = 'retry_wait'),
    'unacknowledged', (SELECT count(*) FROM active_retained
       WHERE status IN ('queued', 'retry_wait') AND last_dispatched_at IS NULL),
    'acknowledged_due_over_300s', (SELECT count(*) FROM active_retained
       WHERE status IN ('queued', 'retry_wait') AND next_attempt_at <= transaction_timestamp()
         AND last_dispatched_at <= transaction_timestamp() - interval '300 seconds'),
    'expired_leases', (SELECT count(*) FROM active_retained
       WHERE status = 'running' AND lease_until <= transaction_timestamp()),
    'running_without_lease_deadline', (SELECT count(*) FROM active_retained
       WHERE status = 'running' AND lease_until IS NULL),
    'older_than_3600s', (SELECT count(*) FROM active_retained
       WHERE created_at <= transaction_timestamp() - interval '3600 seconds'),
    'oldest_age_seconds_capped', (SELECT CASE WHEN count(*) = 0 THEN NULL
       ELSE least(2592000, greatest(0, trunc(extract(epoch FROM
         (transaction_timestamp() - min(created_at))))))::bigint END FROM active_retained)
  ),
  'sec_coordinator', json_build_object(
    'present', EXISTS (SELECT 1 FROM coordinator),
    'times', (SELECT coalesce(json_object_agg(name, json_build_object(
       'state', state, 'seconds_from_snapshot', seconds_from_snapshot)), '{}'::json)
       FROM coordinator_intervals)
  )
);
ROLLBACK;
