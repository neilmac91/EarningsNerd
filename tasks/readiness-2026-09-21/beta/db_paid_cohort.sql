-- v1; PostgreSQL/psql read-only cohort payer count. This is only the
-- denominator-compatible supplement to the existing billing_revenue_report.py,
-- not a new revenue/ARR report. Same qualifying predicate as payment_report.
WITH parameters AS (
  SELECT :'cohort'::text AS cohort,
         :'window_start'::timestamptz AS window_start,
         :'window_end'::timestamptz AS window_end,
         :'excluded_user_ids'::bigint[] AS excluded_user_ids,
         :'excluded_invite_ids'::bigint[] AS excluded_invite_ids
),
ranked_invites AS (
  SELECT i.id, i.user_id, i.used_at,
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
qualified AS (
  SELECT b.user_id, b.stripe_payment_id
  FROM earningsnerd_billing_payments b JOIN eligible e ON e.user_id = b.user_id
  CROSS JOIN parameters p
  WHERE b.livemode IS TRUE AND b.amount_minor > 0
    AND b.payment_type IN ('payment_intent', 'charge')
    AND b.subscription_invoice IS TRUE
    AND b.paid_at >= p.window_start AND b.paid_at < p.window_end
)
SELECT (SELECT count(*) FROM eligible) AS eligible_verified_users,
       count(DISTINCT user_id) AS observed_paying_users,
       count(*) AS qualifying_payment_allocations
FROM qualified;
