# A test's bound on a wait for work that should finish only breaks a hang; never let it time the work

Date: 2026-11-04 · Area: testing / CI

**Context.** On 2026-11-04 main's `backend-tests` failed twice with nothing wrong, each time on a short bound:
- on `a20c02079`, a one-second `asyncio.wait_for` in `test_summary_active_streams.py` (fixed in #2009);
- on `8e712d806`, `asyncio.wait_for(ready.wait(), timeout=2)` in `test_summary_provider_lifecycle.py`. The same tree
  had passed CI in full on #2009's merge commit an hour before.

`backend-tests` runs the suite under pytest-xdist on a 2-vCPU runner for 18 to 26 minutes. There, work that takes
milliseconds alone stretches to seconds: a hold measured up to 4.8 s
(`lessons/test-a-burst-pool-timeout-breaks-a-deadlock-and-detects-nothing.md`). Read by the gate below, main's
`backend/tests` held 515 timed waits, and 244 of them, in 57 files, were under 10 s. Most bounded work that should
finish: a request, a thread, an event, a future, a barrier, a polling deadline, a child process.

**Rule.**
1. A bound on a wait for work that should finish only breaks a hang. Use `HANG_GUARD_S` (30 s) from
   `tests/support/hang_guard.py`. A defect the case guards still fails it, by an assertion or by hanging until the
   bound, and a passing run never waits for it.
2. Where production code would end the same wait sooner (a timeout or deadline, patched or not), keep the guard of
   that wait below it and at least 10 s, and name that timeout in a comment. Above it, a hung defect would pass when
   production's timeout ends the wait, instead of failing at the guard.
3. Keep nested bounds in order: an inner bound (a barrier, a wait handed to a thread) below its outer one, so the
   inner one fires first and the failure says where.
4. A bound under 10 s is right only where the case needs it to be short:
   - a negative window, where the case asserts that something does not happen within it;
   - a timing assertion, where the bound is the property under test;
   - a polling step, or pacing.
   List each such bound in the gate, with why it is short.
5. Never shorten a guard to make a check bite. Add a check that does not race the clock.
6. In a PostgreSQL step, which gives a file 3 minutes in CI, a defect can make every case wait out the same guard.
   A poll for a session to block on a lock is the usual one: under a missing lock, nothing ever blocks. Give such a
   wait an early exit once what it waits for can no longer happen, or a bound whose total over the file's cases fits
   the step. Above the step's time, CI kills the step with no report of which case failed.

**Evidence.**
- The failures: jobs 126548146317 (`a20c02079`) and 126618226224 (`8e712d806`), each a `TimeoutError` at the short
  bound. One re-run of the second passed.
- Rule 6: #2010's first review found that with 30 s guards, a missing lock would make up to 10 cases of one
  PostgreSQL file each poll 30 s, past its step's 3 minutes. The admin invite and maintenance files' polls now exit
  once a write that should be blocked has finished, and the filing-insert file's hold waits 10 s.
- Gate: `backend/tests/unit/test_wait_bounds_only_break_hangs.py` reads every tracked Python file under
  `backend/tests` for the timed waits its docstring lists, and resolves each bound to a number. It fails a bound
  under `FLOOR_S` (10 s) unless `SHORT_ON_PURPOSE` lists that site with its reason. That gates rule 1's 10 s floor and
  rule 4's list. Its docstring names what it cannot read, such as a bound it cannot resolve, waits in a string
  source, a pool's `pool_timeout` and an elapsed-time assertion, which `backend/tests/unit/test_wall_clock_bounds.py`
  gates. Rule 1's choice of `HANG_GUARD_S` over another bound of 10 s or more, and rules 2, 3, 5 and 6, are
  review-checked.
