# Synthetic fixture receipt — 21 September 2026

Command, from repository root:

```text
/private/tmp/earningsnerd-tranche-venv/bin/python tasks/readiness-2026-09-21/beta/fixture_check.py --dsn 'host=127.0.0.1 port=55434 user=earningsnerd dbname=tranche_beta'
```

Result: `PASS`. The exact `db_roster.sql`, `db_support_alerts.sql` and `db_paid_cohort.sql` text was executed with synthetic parameters against temporary PostgreSQL 15 tables. The transaction was rolled back; no application/customer table was read. Expected and observed: eligible verified IDs `[1,2,6]` (3); client-observed fixture IDs `1,6` (2); client-unobserved/known non-consenting ID `2` retained in denominator (1 unknown); cached/fresh summary viewers `1,6` (2). Feedback submissions 2, reporters 2, new 1, resolved 1. Accepted alert batches 3, in-window first clicks 1. Qualifying live attributed paying users 1 from one allocation. Internal user 3, test invite 106/user 5, unverified user 4, revoked unused invite 105, duplicate invite 108 and invite 111 redeemed after the window did not inflate the eligible denominator. Test-mode, $0 beta, internal, unsupported-type, non-subscription and unattributed payment fixtures did not inflate the payer count. A click after the UTC window did not count in-window.

The existing `backend/tests/unit/test_billing_revenue.py` gate also passed: **29 passed**. It exercises the canonical payment report's live/test, zero, type, subscription and attribution rules. No live Stripe call or payment replay was made.

The PostHog SQL was checked against the source event emissions and the [documented supported SQL functions](https://posthog.com/docs/sql/clickhouse-functions) and [aggregations](https://posthog.com/docs/sql/aggregations). Its synthetic client-coverage truth table is asserted by the fixture runner, but the HogQL itself was **not executed** because no PostHog project query was authorized or used. Syntax and real identity/consent coverage remain unobserved. The app persists no per-user analytics-consent record, and no current event proves explicit usefulness or a successful cached Analysis narrative. Weekly review must mark those fields unknown when no separate session-linked evidence is available.
