# Smoke one or two items and inspect raw output before any long or expensive model run

Date: 2026-06-30   Area: test

**Context**: Getting the eval judge working took four fixes, each surfaced only by actually calling it: (1) the `anthropic` SDK isn't in core requirements; (2) the env key had no credits; (3) `claude-opus-4-8` rejects the `temperature` param as deprecated (400); (4) it also rejects assistant-message prefill, so reliability came from generous `max_tokens` (a tight cap truncated the pre-JSON rationale) + a `json_repair` fallback + one retry.

**Rule**: Before a long/expensive model run, smoke 1–2 items and INSPECT the raw result (not just exit code) — auth, credits, params, and parse-rate all fail silently as "0 score" otherwise. Don't assume params/features (temperature, prefill) carry across model generations.

**Evidence**: `claude-opus-4-8` rejects `temperature` (400) and assistant prefill ("conversation must end with a user message"); "credit balance too low"; ~30% of calls unparseable under a tight `max_tokens` cap.
