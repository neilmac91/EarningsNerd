"""The bound a backend test puts on a wait for work that should finish.

Such a bound only breaks a hang. A defect the test guards fails it at any bound: by an assertion, or by hanging until
the bound. On a starved CI runner, work that takes milliseconds alone stretches to seconds (backend-tests runs the
suite under pytest-xdist on a 2-vCPU runner), so a short bound fails a correct run: a one-second ``asyncio.wait_for``
failed main's CI so on 2026-11-04 (``a20c02079``, ``test_summary_active_streams.py``). A passing run never waits for
the bound, so a long one costs a failing run only.

A wait whose production code ends it sooner keeps a bound of its own below that, so that a defect that hangs fails at
the bound and does not pass when production's timeout ends the wait. ``tests/unit/test_wait_bounds_only_break_hangs.py``
holds every bound under ``backend/tests`` to at least ``FLOOR_S`` there, except the ones it lists as short on purpose.
"""

from __future__ import annotations

HANG_GUARD_S = 30.0
