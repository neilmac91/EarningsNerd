# The CI lint gate runs before tests — a trivial unused import reds the build even if pytest is green

**Area:** ci · **Date:** 2026-06-30

Pushed a new test file importing `pytest` without using it; `pytest` was green locally so I shipped
it, but the `backend-tests` job runs `ruff check .` FIRST and failed on F401 (unused import). This is
a repeat of the 2026-06-16 lesson in spirit.
**Rule:** run `ruff check .` (and `bandit`) before every push, not just pytest — the lint gate runs
before the tests and a trivial unused import will red the build.
