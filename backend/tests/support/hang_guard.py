"""The bound a backend test puts on a wait for work that should finish.

Such a bound only breaks a hang. A defect the test guards fails it at any bound: by an assertion, or by hanging until
the bound. On a starved CI runner, work that takes milliseconds alone stretches to seconds (backend-tests runs the
suite under pytest-xdist on a 2-vCPU runner), so a short bound fails a correct run: a one-second ``asyncio.wait_for``
failed main's CI so on 2026-11-04 (``a20c02079``, ``test_summary_active_streams.py``). A passing run never waits for
the bound, so a long one costs a failing run only.

Two waits keep a bound of their own instead, of at least ``FLOOR_S``. A wait that production code ends sooner keeps
one below that, so that a defect that hangs fails at the bound and does not pass when production's timeout ends the
wait. A wait that a defect makes every case of a PostgreSQL file wait out keeps one whose total over the file fits its
3-minute CI step, unless it can exit early once what it waits for can no longer happen.
``tests/unit/test_wait_bounds_only_break_hangs.py`` holds every bound it reads under ``backend/tests`` to at least
``FLOOR_S``, except the ones it lists as short on purpose, and names the forms it does not read. Whether a bound stays
below production's timeout, whether nested bounds stay in order, and whether a PostgreSQL file fits its step are
review-checked (``lessons/test-a-wait-bound-only-breaks-a-hang.md``, rules 2, 3 and 6).
"""

from __future__ import annotations

HANG_GUARD_S = 30.0
