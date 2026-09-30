# Isolate process-wide ContextVars per test; CI's file order can hide a leak

Date: 2026-09-25   Area: test

**Context**: `app/services/ai_metrics.py` labels every `ai_call` with a `ContextVar` trigger
(`user`/`job`/`eval`). Script entrypoints set it for their whole process and never reset it,
including `evals.runner`, the weekly readouts and the Cloud Run job scripts. That is correct for
a CLI process, but `tests/unit/test_eval_attempt_diagnostics.py` runs `evals.runner` in-process via
`runpy`, which left the trigger at `eval` for the rest of the pytest session. Two
`test_ai_metrics.py` tests then failed when run after it. CI never saw this, because
alphabetical collection runs `test_ai_metrics.py` first. The leak surfaced only in an independent
review of the #953 SDK refresh, from a hand-picked file order.

**Rule**: Treat a module-level `ContextVar` that an entrypoint sets as process state. Isolate it in
`backend/tests/conftest.py` with an autouse set/reset fixture, like the existing table resets.
Do not rely on each test that runs an entrypoint to clean up. Pin the isolation with an in-file
probe pair: one test leaves the state set, and the next test in definition order asserts the
default. That runs deterministically in CI's order. A cross-file pair does not.

**Evidence**: `backend/tests/conftest.py::_isolate_ai_call_trigger`;
`backend/tests/unit/test_ai_metrics.py::test_isolation_probe_leaves_the_trigger_set_like_a_script_entrypoint`
and `::test_isolation_next_test_starts_from_the_default_trigger`. The reproduction was
`pytest tests/unit/test_eval_attempt_diagnostics.py tests/unit/test_ai_metrics.py`, which gave
2 failed on `0dfc291`. It was identical under the old and new SDKs in the #953 review.
