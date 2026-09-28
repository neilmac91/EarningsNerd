# Price the actual provider model at its own published tariff

Date: 2026-09-28 · Area: provider cost telemetry

The DeepSeek Pro retirement announcement was superseded by continued service at its own
tariff. ADR-0008 already retained that correction, but the runtime table and its test still
priced a returned Pro model as Flash. The configured production model remained Flash.

Keep per-model telemetry prices separate from the selected production model. When an upstream
availability decision changes, reconcile the runtime price table and its actual-response-model
gate with current primary documentation; do not rewrite retained historical measurements or
infer that a model selection changed. Estimates remain distinct from provider invoices.

The existing `test_record_carries_requested_vs_actual_model_fingerprint_latency_trigger_and_cost`
gate exercises both the emitted and accumulated cost for a Pro response to a Flash request.
`test_per_model_price_table_and_peak_multiplier` retains cache-hit/miss, dated model suffix,
off-peak/peak and unchanged Flash coverage. Reinstating the stale Pro-as-Flash rate is the single
deliberate fault for this correction.

Source: [DeepSeek's pricing notice](https://api-docs.deepseek.com/quick_start/pricing/), checked
September 28, and [ADR-0008's continued-service addendum](../docs/adr/0008-deepseek-v4-pro-to-v41-flash.md).
