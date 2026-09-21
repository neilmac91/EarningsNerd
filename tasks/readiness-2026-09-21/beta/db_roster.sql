-- v1; PostgreSQL/psql read-only query. All timestamps UTC, [start,end).
-- Required psql -v: cohort, window_start, window_end, excluded_user_ids,
-- excluded_invite_ids. Arrays use PG syntax, e.g. '{2,9}' or '{}'.
WITH parameters AS (
  SELECT :'cohort'::text AS cohort,
         :'window_start'::timestamptz AS window_start,
         :'window_end'::timestamptz AS window_end,
         :'excluded_user_ids'::bigint[] AS excluded_user_ids,
         :'excluded_invite_ids'::bigint[] AS excluded_invite_ids
),
scoped AS (
  SELECT i.id AS invite_id, i.user_id, i.created_at AS invite_created_at,
         i.used_at, i.expires_at, i.is_revoked,
         u.created_at AS registered_at, u.email_verified, u.is_beta,
         i.id = ANY(p.excluded_invite_ids) AS excluded_invite,
         coalesce(i.user_id = ANY(p.excluded_user_ids), false) AS excluded_user,
         row_number() OVER (PARTITION BY i.user_id ORDER BY i.used_at NULLS LAST, i.id) AS user_invite_rank
  FROM invite_codes i
  CROSS JOIN parameters p
  LEFT JOIN users u ON u.id = i.user_id
  WHERE i.cohort = p.cohort
    AND i.created_at < p.window_end
)
SELECT now() AS roster_observed_at, s.invite_id, s.user_id, s.invite_created_at, s.used_at,
       s.registered_at, s.email_verified, s.is_beta,
       s.excluded_invite, s.excluded_user,
       (s.used_at IS NULL AND s.is_revoked IS FALSE
          AND s.expires_at > p.window_end AND NOT s.excluded_invite) AS pending_reachable_at_window_end_current_state,
       (s.used_at IS NOT NULL AND s.used_at < p.window_end AND s.user_id IS NOT NULL) AS redeemed_by_window_end,
       (s.user_id IS NOT NULL AND s.registered_at IS NOT NULL
          AND s.registered_at < p.window_end) AS registered_by_window_end,
       (s.used_at IS NOT NULL AND s.used_at < p.window_end AND s.user_id IS NOT NULL
          AND s.registered_at IS NOT NULL AND s.registered_at < p.window_end AND s.email_verified IS TRUE
          AND s.is_beta IS TRUE AND s.user_invite_rank = 1
          AND NOT s.excluded_invite AND NOT s.excluded_user) AS eligible_verified,
       CASE WHEN s.user_id IS NULL THEN 'no linked user'
            WHEN s.user_invite_rank > 1 THEN 'duplicate invite for user'
            WHEN s.excluded_invite OR s.excluded_user THEN 'excluded fixture/internal/test'
            WHEN s.used_at IS NULL THEN 'not redeemed'
            WHEN s.used_at >= p.window_end OR s.registered_at >= p.window_end THEN 'joined after window'
            WHEN s.email_verified IS NOT TRUE THEN 'unverified'
            WHEN s.is_beta IS NOT TRUE THEN 'beta flag missing'
            ELSE 'eligible' END AS roster_state
FROM scoped s CROSS JOIN parameters p
ORDER BY s.invite_created_at, s.invite_id;
