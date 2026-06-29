# Task: Copilot inference-cost instrumentation (roadmap item 2.1)

## Context
Phase 2's prove-it loop. 2.1 is the prerequisite for the free-Copilot taste (2.2): before giving
free users a few Copilot questions, we need the **per-answer token usage + estimated $ cost** so the
unit economics are known. A recon found the copilot stream did NOT capture usage (streaming APIs
only return it when `stream_options={"include_usage": True}` is set), and there was no pricing config
— so 2.1 is more than "add one event."

## Decision (backend-only, surgical)
- **Capture usage** in `openai_service.stream_chat_with_tools` via an OPT-IN `usage_sink` dict:
  set `stream_options={"include_usage": True}` only when a sink is passed (default contract
  unchanged), and accumulate the final-chunk usage across tool rounds (the loop already skips the
  choices-empty chunk; now it reads `usage` first).
- **Thread it** through `copilot_service` onto the `complete` event (`usage: {model, *_tokens}`).
- **Emit** a best-effort `copilot_inference_cost` PostHog event from the router's complete-event hook
  (where `_meter_qa_best_effort` already runs), keyed on `str(user_id)` (the same id the frontend
  identifies on → joins the person; **no ph_id / frontend change needed** since copilot is Pro-only).
- **Pricing:** env-configurable `$/1M`-token rates in config + a tiny `llm_pricing.estimate_inference_cost_usd`.
- Best-effort throughout: telemetry never raises on the stream; missing usage → quiet no-op.

## Plan
- [x] `config.py`: `AI_INPUT/OUTPUT_PRICE_PER_1M_TOKENS` (env-overridable placeholders)
- [x] `services/llm_pricing.py` (new): `estimate_inference_cost_usd(prompt, completion)`
- [x] `openai_service.stream_chat_with_tools`: opt-in `usage_sink` + `stream_options` + accumulate usage
- [x] `copilot_service`: pass `usage_sink`; add `usage` to both `complete` events
- [x] `posthog_client`: `EVENT_COPILOT_INFERENCE` + `capture_copilot_inference(...)` (best-effort)
- [x] `summaries.py`: `_emit_copilot_cost_best_effort` + call at the complete-event hook
- [x] Tests: cost estimator (formula + zero), capture helper (event name + None-filtering), router
      wiring (usage→cost+context; no-usage no-op)
- [x] `py_compile` all changed files (pytest/pydantic absent here → CI runs the suite)
- [ ] Commit + push + open draft PR

## Notes
- **Not eval-relevant:** touches the copilot path (`stream_chat_with_tools`), not summary generation
  (`stream_chat`/`summarize_filing`) — `eval-baseline` is unaffected.
- **Pricing rates are placeholders** ($0.14 / $0.28 per 1M) — set `AI_INPUT/OUTPUT_PRICE_PER_1M_TOKENS`
  to the provider's actual rates so `cost_usd` reflects real spend.
- DeepSeek (the default provider) supports `stream_options.include_usage`; if usage is ever absent,
  the cost event is simply skipped.
- Unblocks 2.2 (free-Copilot taste) once a few weeks of cost data confirm affordability.

## Review
- Surgical + opt-in: the streaming-contract change is gated on `usage_sink`, so nothing but the
  copilot cost path is affected; no frontend change.
- Honest unit-economics signal: per-answer tokens + estimated cost, broken down by filing/ticker/kind,
  keyed to the same person the frontend funnel tracks.
