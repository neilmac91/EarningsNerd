# Code moved out of a patched module keeps resolving its collaborators through that module at call time

Date: 2026-10-09   Area: arch

**Context**: Splitting `summary_pipeline.stream_filing_summary` (a 1,198-line async generator)
into stage modules looked like a pure move, but 40+ tests patch collaborators ON the pipeline
module object — `patch.object(summary_pipeline, "record_progress", …)`,
`monkeypatch.setattr(pipeline, "run_in_threadpool", …)`, `patch("app.services.summary_pipeline.
check_usage_limit")`, even `summary_pipeline.asyncio` (a proxy intercepting `asyncio.timeout`) and
`summary_pipeline.time` (a fake clock) — and the offline acceptance harnesses under
`backend/evals/` patch `get_sixk_text` and `acquire_statement_context` the same way. A stage module
that wrote `from app.services.summary_generation_service import record_progress` would have been
correct code that silently bypassed every one of those patches: the suite would still pass on the
unpatched paths and fail, confusingly, only where the patch mattered.

**Rule**: When code moves out of a module that tests patch, the moved code reaches every
collaborator as `<module>.<name>` at call time — `from app.services import summary_pipeline as
pipeline` then `pipeline.record_progress(...)` — never by importing the collaborator itself, and
never by binding `pipeline.<name>` at import time (a class-body default, a default argument, a
module constant). The patched module keeps importing those names, marked as seams (`# noqa: F401`
with the reason), and binds the new modules ONLY as module objects (`from pkg import stage`, never
`from pkg.stage import Name`) so the circular import works in either order. Land the gate in the
same PR: derive the seam set by scanning the tests' patch sites, assert no stage module imports or
uses a seam name bare, assert every `pipeline.<name>` a stage uses exists on the module, and import
each new module FIRST in a fresh interpreter.

**Evidence**: `backend/tests/unit/test_summary_stages_seams.py` (the gate; its seam scan covers
`tests/` and `evals/`); `backend/app/services/summary_stages/__init__.py` (the package docstring);
`backend/scripts/prove_summary_pipeline_move.py` (the AST-normalized pure-move proof the split
shipped with); the design-review finding that caught `acquire_statement_context`/`get_sixk_text`
(`tests/unit/test_statement_relationship_integration.py:614-622`,
`evals/acceptance_worker.py:241-326`).
