# ADR 0006 — Standardize on DeepSeek V4 via the OpenAI-compatible client

- **Status:** Accepted (supersedes [ADR-0002](./0002-openai-gpt4-to-gemini.md))
- **Deciders:** EarningsNerd maintainers

## Context

ADR-0002 pointed the OpenAI-compatible client at Google AI Studio and standardized on
Gemini models. Since then:

- Production config drifted ahead of the record: `backend/app/config.py` has defaulted to
  **`AI_DEFAULT_MODEL = deepseek-v4-pro`** with
  **`OPENAI_BASE_URL = https://api.deepseek.com/v1`** — the code was the truth, the ADR
  was stale. This record closes that gap (found during the 2026-07 architecture review).
- The eval harness (`backend/evals/`) now provides an adoption/regression gate: the pinned
  `baseline_scores.json` bar and the `eval-baseline` CI job both run against DeepSeek, and
  the full 26-filing verified golden set passes with `gate_fail_rate 0.0`,
  `numeric_precision 1.0`, `coverage 1.0` (see PR #565's recorded runs).
- DeepSeek's pricing model (context-cache hit vs miss input pricing) is wired into the
  cost-estimation helpers (`config.py` cost fields, `analysis_inference_cost` /
  `copilot_inference_cost` telemetry).

The architecture constraint from ADR-0002 is unchanged and is the reason this was a
config-level migration rather than a rewrite: **all provider access goes through the
OpenAI-compatible surface** (`openai` SDK as a plain HTTP client, `OPENAI_*` env names as
a compatibility shim, provider chosen by `OPENAI_BASE_URL`).

## Decision

Standardize on **DeepSeek** as the AI provider and **`deepseek-v4-pro`** (non-thinking) as
the primary model for all AI tasks:

- `OPENAI_BASE_URL = https://api.deepseek.com/v1` (`backend/app/config.py`).
- `AI_DEFAULT_MODEL = deepseek-v4-pro` — chosen over the cheaper flash-class variant on
  quality preference, validated by the eval gate.
- The model-routing seam from ADR-0002 is retained unchanged: `AI_FAST_MODEL` and
  `AI_SECTION_RECOVERY_MODEL` default to `""` (no behavior change until set).
- `config.py` validates `OPENAI_BASE_URL` against the recognized-provider allowlist
  (`api.deepseek.com`, `generativelanguage.googleapis.com`, `openrouter.ai`), so switching
  back — or onward — remains an env-var change gated by `backend/evals/RUNBOOK.md`.

## Consequences

**Positive**
- Model/provider reality and the decision record agree again; future sessions can trust
  the ADRs.
- Strong long-context JSON adherence at DeepSeek pricing; context-cache pricing rewards
  the pipeline's stable prompt prefixes.
- Provider portability preserved: the same client, retry, JSON-repair, and deterministic
  fallback paths run unmodified against any OpenAI-compatible endpoint.

**Negative / costs**
- The `OPENAI_*` naming is now two providers removed from OpenAI — the shim naming is
  actively misleading without this record (kept for zero-churn compatibility; renaming it
  is deliberately out of scope).
- Single-provider dependence on DeepSeek's OpenAI-compatible surface; the routing seam,
  the provider allowlist, and the eval gate bound the switching cost if it degrades.
- Any future model/provider change **must** re-run the eval adoption gate and re-pin
  `baseline_scores.json` in the same PR (`backend/evals/RUNBOOK.md`, "Re-pinning the
  baseline") — the bar now encodes DeepSeek-v4-pro behavior.
