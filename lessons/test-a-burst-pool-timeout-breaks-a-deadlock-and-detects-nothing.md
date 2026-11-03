# Give a burst test's pool a timeout that only breaks a deadlock; catch a held connection with a check that does not race the clock

Date: 2026-11-03 · Area: test / verification

**Context.** `backend/tests/unit/test_cached_filings_pool_lifetime.py` sends bursts of eight or nine requests at
four-slot pools, and 30 of its 38 pools gave a request one second to get a slot. Three times a case timed out on a
change that touched neither its route nor the pool: under #1848's overlapping runs, under #1972's trial-merge gate
(the auth refresh case), and under #1962's gate beside a mutation run (the watchlist add case). A probe that timed
every checkout (E295) found the holds stretched, not leaked:
- with twice as many runnable processes as CPUs, a hold that takes tens of milliseconds alone lasted up to 1.2 s;
- with four times as many, it lasted up to 4.8 s. 82% of the holds of 0.3 s or more went inside DBAPI calls, each
  waiting to take the GIL back or for a starved writer's SQLite lock, while the holding thread spent 15% of that time
  on a CPU.

Four such holds left a fifth request waiting up to 2.1 s, and with the one-second timeout two of four runs failed.

**Rule.** A burst test's pool timeout breaks a deadlock and detects nothing else.
- A checkout that blocks the event loop, or a unit that waits for a second connection, never finishes, so it answers
  500 at any finite timeout.
- A connection held too long without a deadlock makes another request time out only when the hold outlasts the
  timeout, which a fast step never does and a starved runner always may. A check that does not race the clock
  catches it: `open_at_close`, a checkout log by thread, or `checkedout()` read while the slow step runs.

Give the pool room for a starved runner (the pool-lifetime file's `POOL_TIMEOUT`, 5 s), and never shorten a timeout
to make a check bite: add the check.

**Evidence.** E295, 2026-11-03: `POOL_TIMEOUT` and its comment in
`backend/tests/unit/test_cached_filings_pool_lifetime.py`. The gate `test_every_pool_here_takes_the_file_timeout`
there covers that file only; other files' pool tests set their own timeouts, some of which fire on purpose. The
probe's runs are in E295's pull request.
