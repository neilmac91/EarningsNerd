# Seed fixture months that can never be the wall-clock month; pin the clock where cases depend on it

Date: 2026-10-01   Area: test

**Context**: `tests/integration/test_usage_counter_transactions.py` seeded usage buckets and leases
in `MONTH = "2026-09"`, while `reserve_summary_use` admitted in `get_current_month()` (the wall
clock). Five summary-reservation cases never pinned the clock, so they passed for all of September and two
broke at 2026-10-01T00:00Z on every PR's required `migrations-postgres` job. One saw
`convert_reservation` return `'2026-10'`, and the other saw a completion that found no current-month
bucket take the `users` lock and time out. The slice-2 cases in the same file already pinned
the month; the older cases never did, and a plausible current month hid the gap.

**Rule**: A fixture month that production code compares with the clock must be a month the clock
can never return (`"2000-01"`), so a case that forgets to pin fails at authoring time. Cases that
seed that month and exercise admission or conversion pin `get_current_month` explicitly; a rollover
case pins a different sentinel. Never use the current or a recent month as a fixture constant.

**Evidence**: CI run 36796447015 (PR #1036, 2026-10-01T00:30Z): `assert '2026-10' == '2026-09'`
and `LockNotAvailable` in the two cases; reproduced locally on main `ae95322a` against
PostgreSQL 16 (2 failed / 27 passed). The fix pins the five summary-reservation cases and moves
`MONTH` to `"2000-01"`. Its mutation proof drops one pin, and that case fails immediately.
