# Every marker you deselect in addopts needs an explicit CI run-path, or it's a silent skip

**Area:** testing · **Date:** 2026-07-05

`pytest.ini` deselected both `performance` AND `slow` by default, but CI only re-ran `-m performance`.
A future `@pytest.mark.slow` test would be skipped by the fast lane AND absent from the perf step —
green in CI while never executing (same class as perf tests that lacked the marker entirely).

**Rule:** every marker you deselect in `addopts` needs an explicit CI execution path, or don't
deselect it. Prefer structural enforcement — a directory-scoped `pytest_collection_modifyitems`
(e.g. `tests/performance/conftest.py`) that auto-stamps the marker so a new file can't forget it.
