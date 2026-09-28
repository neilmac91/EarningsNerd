# Price the actual provider model at its own published tariff

Date: 2026-09-28 · Area: provider cost telemetry

The DeepSeek Pro retirement announcement was superseded by continued service at its own
tariff. ADR-0008 already retained that correction, but the runtime table and its test still
priced a returned Pro model as Flash. The configured production model remained Flash.

Keep per-model telemetry prices separate from the selected production model. When an upstream
availability decision changes, reconcile the runtime price table and its actual-response-model
gate with current primary documentation; do not rewrite retained historical measurements or
infer that a model selection changed. Estimates remain distinct from provider invoices.

Keep one numeric tariff gate: `test_per_model_price_table_and_peak_multiplier` covers cache
hit/miss, dated model suffix, off-peak/peak and unchanged Flash pricing. The separate
`test_record_carries_requested_vs_actual_model_fingerprint_latency_trigger_and_cost` gate uses
model-specific estimator sentinels to check actual-model routing and emitted/accumulated cost
without duplicating tariff constants.

Completion telemetry must reuse the recorded cost of every physical call, including tool rounds,
transport retries and rejected selection attempts. Never reprice aggregate tokens using Settings,
the requested model, the final returned model or the completion-time tariff window. An unknown
counter or cost makes that total unknown; a missing actual model remains unknown, and differing
known models are labelled `mixed`. The existing per-call records retain their individual detail.
`test_completion_telemetry_preserves_physical_call_accounting` follows both services through SDK
mock transport into their completion emitters with model-specific cost sentinels, missing data and
measured-zero cases. Keep this accounting gate separate from the sole numeric tariff gate.

Source: [DeepSeek's pricing notice](https://api-docs.deepseek.com/quick_start/pricing/), checked
September 28, and [ADR-0008's continued-service addendum](../docs/adr/0008-deepseek-v4-pro-to-v41-flash.md).
