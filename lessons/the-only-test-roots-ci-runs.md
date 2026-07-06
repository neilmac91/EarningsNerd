# CI collects only backend/tests/{unit,integration,smoke,performance} + frontend/tests — a test elsewhere does not run

**Area:** testing · **Date:** 2026-07-06

CI runs `cd backend && pytest` (testpaths = tests) and the frontend vitest/playwright roots. A test file at the repo root, in `backend/scripts/`, or in a stray `/tests/` is invisible to CI and provides zero coverage (and has almost certainly bit-rotted).

**Rule:** put a backend test under `backend/tests/{unit,integration,smoke,performance}` and a frontend test under `frontend/tests/{unit,e2e}` — nowhere else. Before trusting or 'adopting' a test outside these roots, run it isolated AND in-suite; if it fails or pollutes global state, treat it as dead.
