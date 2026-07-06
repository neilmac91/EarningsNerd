# Audit __file__-relative shims whenever relocating a test or script

Date: 2026-07-05   Area: test

**Context**: `test_startup.py` moved from `scripts/` to `tests/smoke/`. Its sys.path shim had resolved to `backend/` from `scripts/`; from `tests/smoke/` it now inserts `backend/tests/` (no `app` package). It passed anyway under `cd backend && pytest` only because cwd is already on `sys.path` — masking the break until someone runs it as a standalone script.

**Rule**: When relocating a test/script, audit every `__file__`-relative path, `sys.path` shim, and fixture-relative reference (cwd-on-sys.path masks a broken shim under pytest). If the file is now a pytest test, delete the script scaffolding (`sys.path` shim, `if __name__ == "__main__"` runner) rather than repair it — pick one identity.

**Evidence**: `test_startup.py` moved `scripts/` → `tests/smoke/`; `sys.path.insert(0, Path(__file__).parent.parent)` now inserts `backend/tests/` (no `app` package).
