# Run ruff (and bandit) before every push, not just pytest

Date: 2026-06-30   Area: ops

**Context**: Pushed a new test file importing `pytest` without using it; pytest was green locally, but the `backend-tests` job runs `ruff check .` FIRST and failed. A repeat of the 2026-06-16 lesson in spirit.

**Rule**: Run `ruff check .` (and `bandit`) before every push, not just pytest — the lint gate runs before the tests and a trivial unused import will red the build.

**Evidence**: `backend-tests` job runs `ruff check .` FIRST; failed on F401 (unused import).
