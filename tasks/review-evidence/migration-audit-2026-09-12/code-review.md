# Migration correctness audit — 2026-09-12

Read-only audit of `a811faf6..8e9ad24cb643688b7cbc146e0ecd1cfe4a2d069f`. Reviewed the migration changes to provider request assembly, call telemetry and consumers, eval runner/report comparison, shared provenance normalization, retired-model gates, and the additive registration-config backend endpoint. No repository edits, pytest process, paid calls or SEC calls. The root agent owns the full gate, external pricing verification, authorization and ledger reconciliation.

## Surviving findings

### Must-fix before another measured cohort: failed generations and outer retries lose provider usage

`backend/evals/runner.py:336`, `:394–404`, and `:237–259`.

If a generation records a successful primary call followed by a timeout, `_attempt` exits through the exception handler without serializing its observer records. This also affects an application `status:error` response: usage is computed at line 336, then the raised ValueError takes the same return that omits it. A successful outer retry replaces the failed generation entirely; `_run_one` retains first error/latency and preview evidence but no usage. Thus report usage/call totals can look complete for all final rows while omitting known tokens and unknown-usage attempts incurred during failed generations. This is material to the W10 cost/retry comparison and future paid acceptance; it does not itself prove a production summary regression.

Refutation 1: traced `record_ai_call` → ContextVar observer → `_attempt` success and exception returns. Provider records are collected and logged in provider `finally` blocks, but `stop_observing` only resets the binding; it does not publish records to the failed result. `_usage_stats` only reads final row `provider_usage`, so it cannot recover lost records. Application errors lose even already-computed usage.

Refutation 2: executed the actual `_run_one` AST in an isolated stdlib fixture, with a first transient result containing two calls/400 completion tokens and a successful retry containing one call/200 tokens. Returned row contains only one call/200 tokens, `retried=1`, first error/latency and an empty retry preview record. Existing `test_eval_provider_usage.py` covers success and explicitly treats a failed row as having no usage; no error/retry retention invariant refutes the defect.

Recommended correction: preserve per-generation provider records/usage on success and every failure, keep retry-generation usage separately, and expose complete known totals plus unknown counters without double-counting the final generation. Retain final-generation latency/output metrics separately from total incurred work. Correct historical cost claims with append-only qualifications; original logs may recover costs but report totals alone cannot.

### Should-fix: partial cache metadata silently underprices the new per-call estimate

`backend/app/services/llm_pricing.py:62–65`, consumed by `backend/app/services/ai_metrics.py:154`.

A valid provider response may include `prompt_tokens` and nested `prompt_tokens_details.cached_tokens` but omit cache misses. `_usage` explicitly accepts that wire shape. The estimate prices the hits and zero misses, discarding the known remaining prompt tokens. The symmetric missing-hit case also treats unpriced tokens as zero. This is telemetry, not billing or a generation-spend control, so severity is should-fix rather than a production correctness blocker.

Refutation 1: read `_usage` and the real `record_ai_call` call site: they preserve missing cache counters as None and pass them straight to the estimator; no caller fills the remainder. The estimator's fallback runs only when BOTH hit and miss are None. Normalization guards malformed counts but does not infer missing counts.

Refutation 2: executed the real pricing functions extracted from the committed AST. At an explicit Saturday off-peak timestamp, 1,000,000 prompt tokens, 100,000 hits, missing misses, zero output produces $0.0003. Supplying the other 900,000 misses produces $0.1353. This discrepancy is independent of current external tariff accuracy. The existing new pricing test covers a full split and no split, not a partial split. Although an older PostHog helper has a related behavior, this newly introduced estimator independently carries the defect to `ai_call` logs.

Recommended correction: conservatively price known prompt tokens not accounted for in a valid split, or explicitly expose incomplete cost instead of treating it as complete. Do not rewrite provider-reported token fields as if inferred counts were reported.

### Should-fix: Flash tariff Settings cease controlling new `ai_call` estimates

`backend/app/services/llm_pricing.py:39–48` and `:60`; compare `:90–94`.

For the default `deepseek-flash`, `prices_for_model` returns the static table before inspecting any of the three configurable per-million-token Settings. An operator updating those documented rates changes the legacy PostHog estimate but leaves new per-request `ai_call` prices unchanged. This can create contradictory cost telemetry for the same traffic after a tariff/configuration update.

Refutation 1: traced model selection and configuration: actual or requested `deepseek-flash` always matches the hardcoded prefix, so configured default-model rates are not consulted. `AI_PEAK_PRICE_MULTIPLIER` still works, but cannot express an individual hit/miss/output tariff change.

Refutation 2: compared the existing per-model test and legacy helper: the test deliberately changes Settings only for `other-model`, whereas the legacy helper always reads them. There is no override merge for a recognized model. Thus this is a real configuration contract discrepancy, not just an inaccurate rate copied in documentation. Root is independently checking published tariffs.

Recommended correction: give the configured model an explicit Settings override policy or document and expose per-model overrides consistently; preserve actual-model attribution for genuinely different model routes.

## Refuted or bounded candidates

- **New telemetry keyword arguments break production callers:** refuted by signatures retaining defaults for every new keyword and auditing the two live record sites. Added fields are additive, `_chat_chunks` iterates normalized usage keys, and raw call counters retain existing grouping fields. Historical consumers needing `chat_stream` must be updated, but the live plain `stream_chat` caller is only trend analysis; tool chat is Copilot. Their new labels are correctly assigned. Root owns local acceptance-script reconciliation.
- **Thinking accidentally enabled by default or temperature still sent in its enabled arm:** refuted by empty Settings default, truthy-effort branch predicate, recovery/fallback exclusions, and explicit `request.pop("temperature")`. Both chat paths still explicitly disable thinking. Thinking is a founder-held opt-in. Request/output/deadline limits are not a dollar-cost cap, and this audit does not bless a new thinking run.
- **Shared punctuation fold permits changed words/figures or asymmetric source matching:** not confirmed. The new regexes remove whitespace immediately before selected punctuation/after opening brackets on both sides. Changed words, elisions and changed figures still differ; existing targeted tests cover them. No concrete semantic false positive surviving two code/test passes was found. Scores before and after the fold remain different measurement versions; higher citation scores alone are not stronger analysis.
- **Slim tracked baselines break required grounding consumers:** no live dependency found in the audited downstream paths. `compare_reports`, regression gate and pinning consume metrics/summary data rather than omitted source text. Slim reports remain insufficient to independently rejudge financial claims or prove source identity. `compare_reports` pairs ticker/form/run, not accession/source hashes; it is a numeric comparison aid, not provenance verification. Do not use its paired count as a source-equality proof.
- **Retired ID gate misses a live routing literal simply because tests/archive are excluded:** not confirmed. Historical baseline/report/test identifiers are intentionally data; current configured literal sites and provider workflows are separately checked. The skip for `retired`/`ADR-0008` commentary is broad and is not a general semantic routing proof, but no live stale route was identified by the production-code search. Static alias tariff keys are historical pricing identifiers, not requests.
- **New public registration endpoint bypasses registration authorization:** refuted by additive GET-only handler returning mode and promo-configured boolean. Existing POST register enforcement is unchanged. It reports configuration presence, not Stripe promotion validity; no account or signup setting was changed by this audit.
- **Unknown-cost counter aggregate equals zero:** aggregate cost treats unknown calls as zero contribution, but accompanying usage unknown counters remain available. This limits interpretation of aggregate `estimated_cost_usd`; it is not proof of free failed traffic. Prefer an explicit known-cost/unknown-call presentation alongside the primary cost fixes.

## Verification limits

The isolated probes execute selected real function bodies with injected fixture dependencies; they are diagnostic reproductions, not replacement tests, mutation proofs, or a full integration gate. No new invariant was implemented. No current provider prices, rollout revision, or financial quality claim was independently certified by this code-only audit. Root must combine this with its gates, production checks and ledger evidence.
