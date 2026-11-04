# A test's bound on a wait for work that should finish only breaks a hang; never let it time the work

Date: 2026-11-04 · Area: testing / CI

**Context.** On 2026-11-04 main's `backend-tests` failed twice with nothing wrong, each time on a short bound:
- on `a20c02079`, a one-second `asyncio.wait_for` in `test_summary_active_streams.py` (fixed in #2009);
- on `8e712d806`, `asyncio.wait_for(ready.wait(), timeout=2)` in `test_summary_provider_lifecycle.py`. The same tree
  had passed CI in full on #2009's merge commit an hour before.

`backend-tests` runs the suite under pytest-xdist on a 2-vCPU runner for 18 to 26 minutes. There, work that takes
milliseconds alone stretches to seconds: a hold measured up to 4.8 s
(`lessons/test-a-burst-pool-timeout-breaks-a-deadlock-and-detects-nothing.md`). A scan of every timed wait under
`backend/tests` found 236 bounds under 10 s, in 54 files. Most bounded work that should finish: a request, a thread,
an event, a future, a barrier, a polling deadline.

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

**Evidence.**
- The failures: jobs 126548146317 (`a20c02079`) and 126618226224 (`8e712d806`), each a `TimeoutError` at the short
  bound. One re-run of the second passed.
- Gate: `backend/tests/unit/test_wait_bounds_only_break_hangs.py` reads every tracked Python file under
  `backend/tests` for a timed wait and resolves its bound to a number. It fails a bound under `FLOOR_S` (10 s) unless
  `SHORT_ON_PURPOSE` lists it with its reason. Its docstring names what it cannot read: a bound it cannot resolve
  to a number, an aliased `asyncio.timeout`, and a pool's `pool_timeout`. Rules 2 and 3 are review-checked.
