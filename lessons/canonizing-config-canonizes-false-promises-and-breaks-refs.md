# Single-sourcing config canonizes any false promise; moving a file breaks out-of-diff refs — grep the whole repo

**Area:** process · **Date:** 2026-07-05

Making `pytest.ini` the single source of test config carried over a marker description that lied
(`requires_db: ... skips gracefully` — nothing implements the skip). And moving
`test_edgar_services.py` into `tests/unit/` broke `evals/RUNBOOK.md` Step A (pytest hard-errors on a
missing path before collecting anything) plus 5 CLAUDE.md statements.

**Rule:** when you canonize config, make every description literally true (or reword it). When you
move or delete a file, grep the WHOLE repo (docs, runbooks, CLAUDE.md, CI) for its old path/symbol
and fix the refs in the same change — "fix drift now where it misleads" applies to the moves you make.
