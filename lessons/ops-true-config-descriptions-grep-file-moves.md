# Make canonized config descriptions literally true and grep the whole repo when moving files

Date: 2026-07-05   Area: ops

**Context**: Making `pytest.ini` the single source of test config carried over a marker description that lied (nothing implements the promised graceful skip) — single-sourcing canonizes any false promise. And moving a test file broke a runbook step (pytest hard-errors on a missing path before collecting anything) plus 5 CLAUDE.md statements.

**Rule**: When you canonize config, make every description literally true (or reword it). When you move or delete a file, grep the WHOLE repo (docs, runbooks, CLAUDE.md, CI) for its old path/symbol and fix the refs in the same change — "fix drift now where it misleads" applies to the moves you make.

**Evidence**: `requires_db: ... skips gracefully` (nothing implements the skip); moving `test_edgar_services.py` into `tests/unit/` broke `evals/RUNBOOK.md` Step A plus 5 CLAUDE.md statements.
