# Seed fixture months that can never be the wall-clock month; pin the clock where cases depend on it

Date: 2026-10-01   Area: test

**Context**: `tests/integration/test_usage_counter_transactions.py` seeded usage buckets and leases
in `MONTH = "2026-09"`, while `reserve_summary_use` admitted in `get_current_month()` (the wall
clock). Five summary-reservation cases never pinned the clock. Two of them depended on the
admission month, so they passed only while the calendar said September and broke at
2026-10-01T00:00Z on every PR's required `migrations-postgres` job. One saw
`convert_reservation` return `'2026-10'`, and the other saw a completion that found no current-month
bucket take the `users` lock and time out. The slice-2 cases in the same file already pinned
the month; the older cases never did, and a plausible current month hid the gap.

**Rule**: A fixture month that production code compares with the clock must be a month the clock
can never return (`"2000-01"`). Then a case whose outcome depends on the admission month fails at
authoring time if it forgets to pin, instead of on the 1st of a later month. Cases that seed that
month and exercise admission or conversion pin `get_current_month` explicitly, and a rollover case
moves the clock to a different sentinel. Gate it where the constant lives: the usage file's
`test_fixture_months_are_sentinels_the_clock_never_returns` fails if `MONTH` or `ROLLOVER_MONTH`
leaves the year-2000 sentinel range. A month literal that nothing compares with the clock (such as
a lease's stored month) is out of scope.

**Evidence**: CI run 36796447015 (PR #1036, 2026-10-01T00:30Z): `assert '2026-10' == '2026-09'`
and `LockNotAvailable` in the two cases; reproduced locally on main `ae95322a` against
PostgreSQL 16 (2 failed / 27 passed). The fix pins the five summary-reservation cases and moves
`MONTH` to `"2000-01"`. Its mutation proofs: dropping one pin makes that case fail immediately,
and setting `MONTH` back to the current month fails the sentinel gate.
