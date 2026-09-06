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
user-visible output — cross-filing insight belongs to the labeled Change Report
(`GET /api/summaries/filing/{id}/what-changed`), as required by CLAUDE.md rule 2.

**Evidence**: PRs #549/#565; T1/T2 anchors (`test_summary_stream_contract.py`,
`test_background_generation_characterization.py`); founder decision record in the plan
delta log (filing-only convergence, 9-section verdict, `Summary.filing_id` UNIQUE).

**Database ownership (2026-09-06)**: The shared generator's DB units create and close
their sessions inside the worker, returning plain snapshots or scalar IDs. Progress
writes also close the read transaction opened by their post-commit refresh. Neither
admission/provider waits nor the background drain retain preflight connections; the
SSE route copies loaded primitive identity/subscription inputs before releasing its request
session; missing subscription fields are loaded in a fresh worker session. Inspect ORM state
without triggering lazy loads, including expired fields on an already-loaded relationship.
Pass the frozen snapshot across threads, never the request session or its ORM objects. The pinned FastAPI runtime otherwise keeps yielded request dependencies open
until the streaming response finishes. A cancelled coroutine must not close a session
that its worker is still using.

Gate: `backend/tests/unit/test_summary_provider_lifecycle.py::test_generation_waits_release_database_connections`
uses a real one-connection pool across leader, follower, queue, drain and SSE waits,
including cancellation while a DB worker owns its transaction. Real User/Subscription cases
record SQL thread identity; standalone fixtures alone cannot prove lazy-load safety. The health-probe
worker ownership gate lives in `backend/tests/smoke/test_critical_paths.py`.


**Local leader handoff (2026-09-06)**: Joining another generation includes awaits, including
its persisted-result read. Recheck the registry and claim an empty slot without yielding;
never overwrite an active leader after a follower timeout. A joined follower's empty DB
snapshot may return after a replacement has already committed and released. Hold any new
claim while reading persisted state again before admitting provider work. This is process-local
deduplication; API instances and jobs still have independent registries. Preserve the existing
force-regenerate follower behavior, overall timeout, quota rules and owner-only cleanup.

Gate: `backend/tests/unit/test_inflight_dedup.py` drives competing followers after failed
leadership, exhausted follower budgets, and delayed empty reads after replacement completion.
The tests retain one replacement provider call and the same persisted result, including forced
requests. Existing provider lifecycle gates continue to prove cleanup before ownership release.
