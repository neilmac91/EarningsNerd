# Apply a plan cap where its effect fires, not only where the setting is written

Date: 2026-10-16   Area: arch

**Context**: The earnings-day alert cap (Free 3, Pro 100) was checked only when a user switched an
alert on. A Pro user who enabled six alerts and then cancelled was downgraded by Stripe's
`customer.subscription.deleted` handler, which changes the plan and nothing else, so the daily
send kept emailing all six. Filing alerts did not leak because they resolve entitlements at
delivery time (`evaluate_delivery`).

**Rule**: A plan limit on a standing setting (how many things a user has switched on) is applied
by the path that acts on the setting, reading the current plan from `entitlements.py` at that
moment, as well as at the toggle. A downgrade rewrites no settings: the acting path keeps a subset
in a fixed, documented order and skips the rest for that run, without deleting the user's choices
or writing their ledger rows, so an upgrade restores them.

**Evidence**: `backend/app/services/earnings_alert_service.py` (`_alerting_company_ids`, used by
`send_earnings_day_alerts`); `backend/app/services/subscription_sync.py`
(`apply_subscription_deleted`); regressions
`test_downgrade_caps_the_send_at_the_plan_limit_and_an_upgrade_restores_it` and
`test_send_cap_keeps_the_earliest_watches_by_created_at_then_id` in
`backend/tests/unit/test_earnings_alerts.py`.
