# There is ONE summary orchestrator — never add a second generation path

Date: 2026-07-06   Area: arch

**Context**: The codebase spent months with two parallel summary pipelines — the SSE
stream (`summary_pipeline.stream_filing_summary`) and a ~500-line legacy background body —
which silently diverged: different verdict functions, different coverage taxonomies,
prior-10-K context injected on one path only, partials persisted on one and discarded on
the other. Unifying them (S1) required a characterization-test anchor, a feature flag, an
eval gate, and a prod validation cycle. The legacy body is deleted (PR #565).

**Rule**: `stream_filing_summary` is the only summary generator. Cron/precompute/
pregenerate callers drain it headless via `generate_summary_background` (funnel telemetry
suppressed, `current_user=None`). Any new consumer drains the same generator; anyone
proposing a second generation code path must first read the S1 saga in
`tasks/architecture-refactor-plan.md`'s delta log. Summaries are filing-only by product
decision: no content from outside the chosen filing (prior filings included) may enter
user-visible output — cross-filing insight belongs to explicit surfaces (Multi-Period
Analysis).

**Evidence**: PRs #549/#565; T1/T2 anchors (`test_summary_stream_contract.py`,
`test_background_generation_characterization.py`); founder decision record in the plan
delta log (filing-only convergence, 9-section verdict, `Summary.filing_id` UNIQUE).
