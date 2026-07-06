# Relocating a test/script breaks its __file__-relative sys.path shims (cwd-on-path masks it under pytest)

**Area:** testing · **Date:** 2026-07-05

`test_startup.py` moved from `scripts/` to `tests/smoke/`. Its
`sys.path.insert(0, Path(__file__).parent.parent)` had resolved to `backend/` from `scripts/`; from
`tests/smoke/` it now inserts `backend/tests/` (no `app` package). It passed anyway under
`cd backend && pytest` only because cwd is already on `sys.path` — masking the break until someone
runs it as a standalone script.

**Rule:** when relocating a test/script, audit every `__file__`-relative path, `sys.path` shim, and
fixture-relative reference (cwd-on-sys.path masks a broken shim under pytest). If the file is now a
pytest test, delete the script scaffolding (`sys.path` shim, `if __name__ == "__main__"` runner)
rather than repair it — pick one identity.
