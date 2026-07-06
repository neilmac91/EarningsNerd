# Summary generation has ONE orchestrator — stream_filing_summary; cron/background drain it

**Area:** backend · **Date:** 2026-07-06

S1 (architecture refactor) collapsed the two summary pipelines into one. `services/summary_pipeline.stream_filing_summary` is the SOLE orchestrator: the SSE endpoint streams it, and `generate_summary_background` (cron/precompute/pregenerate) drains it headless. There is no longer a separate in-file background generator, and no `USE_PIPELINE_FOR_BACKGROUND` flag.

**Rule:** route any new summary-generation work through `stream_filing_summary`; never re-introduce a second generation path. The background path is filing-only (no previous_filings), persists partials with a quality tier, and charges usage once on a full result via the pipeline's `count_usage`.
