-- v1; PostgreSQL/psql read-only query. Exact roster eligibility is repeated
-- here so support/alert denominators cannot drift from db_roster.sql.
WITH parameters AS (
  SELECT :'cohort'::text AS cohort,
         :'window_start'::timestamptz AS window_start,
         :'window_end'::timestamptz AS window_end,
         :'excluded_user_ids'::bigint[] AS excluded_user_ids,
         :'excluded_invite_ids'::bigint[] AS excluded_invite_ids
),
ranked_invites AS (
  SELECT i.id, i.user_id, i.cohort, i.created_at, i.used_at,
         row_number() OVER (PARTITION BY i.user_id ORDER BY i.used_at NULLS LAST, i.id) AS user_invite_rank
  FROM invite_codes i CROSS JOIN parameters p
  WHERE i.cohort = p.cohort AND i.created_at < p.window_end
),
eligible AS (
  SELECT i.user_id
  FROM ranked_invites i JOIN users u ON u.id = i.user_id CROSS JOIN parameters p
  WHERE i.user_invite_rank = 1
    AND i.used_at < p.window_end AND u.created_at < p.window_end
    AND u.email_verified IS TRUE AND u.is_beta IS TRUE
    AND NOT (i.id = ANY(p.excluded_invite_ids))
    AND NOT (i.user_id = ANY(p.excluded_user_ids))
),
feedback_counts AS (
  SELECT count(*) AS submitted,
         count(*) FILTER (WHERE f.status = 'new') AS open_new,
         count(*) FILTER (WHERE f.status = 'triaged') AS open_triaged,
         count(*) FILTER (WHERE f.status = 'resolved') AS resolved,
         count(DISTINCT f.user_id) AS reporters
  FROM feedback f JOIN eligible e ON e.user_id = f.user_id CROSS JOIN parameters p
  WHERE f.created_at >= p.window_start AND f.created_at < p.window_end
),
alert_counts AS (
  SELECT count(*) AS accepted_batches,
         count(*) FILTER (WHERE b.first_click_at IS NOT NULL
           AND b.first_click_at < p.window_end) AS first_clicked_batches,
         count(DISTINCT b.user_id) AS alerted_users,
         count(DISTINCT b.user_id) FILTER (WHERE b.first_click_at IS NOT NULL
           AND b.first_click_at < p.window_end) AS alert_clicked_users
  FROM earningsnerd_delivery_batches b JOIN eligible e ON e.user_id = b.user_id
  CROSS JOIN parameters p
  WHERE b.status = 'accepted' AND b.provider_email_id IS NOT NULL
    AND b.first_dispatch_at >= p.window_start AND b.first_dispatch_at < p.window_end
)
SELECT (SELECT count(*) FROM eligible) AS eligible_verified_users,
       f.submitted AS feedback_submissions, f.reporters AS feedback_reporters,
       f.open_new, f.open_triaged, f.resolved,
       a.accepted_batches, a.first_clicked_batches, a.alerted_users, a.alert_clicked_users
FROM feedback_counts f CROSS JOIN alert_counts a;
