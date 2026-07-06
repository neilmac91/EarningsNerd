# Smoke 1-2 items and INSPECT the raw model result before a long run — auth/credits/params fail silently as 0

**Area:** ai-evals · **Date:** 2026-06-30

Getting the eval judge working took four separate fixes, each surfaced only by actually calling it:
(1) the `anthropic` SDK isn't in core requirements (judge is off by default) — `pip install anthropic`;
(2) the env key had no credits (`credit balance too low`) — verify with a 1-call test before a full run;
(3) `claude-opus-4-8` rejects the `temperature` param as deprecated (400); (4) it also rejects
assistant-message **prefill** ("conversation must end with a user message"), the usual JSON-pinning
trick — so reliability came from generous `max_tokens` (opus prepends a rationale before the JSON and
a tight cap truncated it → unparseable on ~30% of calls) + a `json_repair` fallback + one retry.
**Rule:** before a long/expensive model run, smoke 1–2 items and INSPECT the raw result (not just
exit code) — auth, credits, params, and parse-rate all fail silently as "0 score" otherwise. Don't
assume params/features (temperature, prefill) carry across model generations.
