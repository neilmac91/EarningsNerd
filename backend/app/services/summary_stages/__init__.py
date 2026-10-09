"""The named stages of the ONE summary orchestrator, ``summary_pipeline.stream_filing_summary``.

This package is not a second generation path (CLAUDE.md rule 1): the orchestrator drives these
stages in a fixed order and every consumer still drains that single generator. Each stage is an
async generator that receives the shared ``GenerationRun`` and yields the same event dicts the
orchestrator yields to its caller; a stage that yields a terminal event (``complete``, ``partial``,
``error``) ends the pipeline, exactly as the inline ``yield …; return`` did before the split.

Patch seams (why these modules import the pipeline module). The tests patch collaborators on the
``app.services.summary_pipeline`` MODULE object (``check_usage_limit``, ``record_progress``,
``run_in_threadpool``, ``openai_service``, ``settings``, ``_release_inflight``, ``time``, …) and
expect the patch to take effect at call time. So every stage reaches every app collaborator as
``pipeline.<name>`` through ``from app.services import summary_pipeline as pipeline``, never by
importing the collaborator itself; only ``app.database`` (``SessionLocal`` is patched on that
module), the ORM models and stdlib are imported directly. The import is circular by design: these
modules bind only MODULE objects at import time and touch no attribute of the pipeline until a
call, so either import order works (the pipeline builds its stage map lazily for the same reason).
``tests/unit/test_summary_stages_seams.py`` is the gate.
"""
