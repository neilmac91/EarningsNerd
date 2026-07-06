# Give every deselected pytest marker an explicit CI execution path

Date: 2026-07-05   Area: test

**Context**: `pytest.ini` deselected both `performance` AND `slow` by default, but CI only re-ran `-m performance`. A future `@pytest.mark.slow` test would be skipped by the fast lane AND absent from the perf step — green in CI while never executing (same class as perf tests that lacked the marker entirely).

**Rule**: Every marker you deselect in `addopts` needs an explicit CI execution path, or don't deselect it. Prefer structural enforcement — a directory-scoped `pytest_collection_modifyitems` (e.g. `tests/performance/conftest.py`) that auto-stamps the marker so a new file can't forget it.

**Evidence**: `pytest.ini` deselects `performance` and `slow`; CI re-runs only `-m performance`; fix pattern: `tests/performance/conftest.py` + `pytest_collection_modifyitems`.
