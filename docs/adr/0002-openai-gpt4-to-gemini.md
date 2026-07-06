# ADR 0002 — Use Google AI Studio (Gemini) via an OpenAI-compatible client

- **Status:** Superseded by [ADR-0006](./0006-gemini-to-deepseek.md)
- **Deciders:** EarningsNerd maintainers

## Context

EarningsNerd's core value is turning dense 10-K/10-Q filings into structured,
evidence-backed summaries. That requires a model that:

- handles **long context** (full filing sections plus extracted XBRL facts),
- reliably emits **strict JSON** against our summary contract, and
- is **cost-effective** per summary at the volumes a pre-launch product expects.

The summarization code was originally written against the OpenAI SDK / GPT-4-family
models. The `OPENAI_*` environment names and the `openai` Python package are still present
— but they are now only a **compatibility shim**, not a dependency on OpenAI the vendor.

## Decision

Point the OpenAI-compatible client at **Google AI Studio's** OpenAI-compatible endpoint and
standardize on **Gemini** models:

- `OPENAI_BASE_URL = https://generativelanguage.googleapis.com/v1beta/openai/`
  (`backend/app/config.py`).
- `AI_DEFAULT_MODEL = gemini-3.1-pro-preview` — the primary model for all AI tasks.
- The `openai>=1.30.0` SDK is retained purely as the HTTP client against that
  OpenAI-compatible surface; `OPENAI_API_KEY` carries the Google AI Studio key.
- A **default-off model-routing seam** exists for cost tuning without code changes:
  `AI_FAST_MODEL` (cheaper model any task can opt into, e.g. `gemini-2.5-flash`) and
  `AI_SECTION_RECOVERY_MODEL` (overrides just the section-recovery task; falls back to
  `AI_FAST_MODEL`, then `AI_DEFAULT_MODEL`). Both default to `""`, so behavior is unchanged
  until explicitly set in an environment.
- `config.py` validates that `OPENAI_BASE_URL` points at a recognized provider.

## Consequences

**Positive**
- Long context and strong JSON adherence at Gemini's price point.
- No code rewrite to switch providers: the OpenAI-compatible surface means the existing
  client, retry logic, and JSON-repair path are reused as-is.
- The routing seam lets us A/B a cheaper model per task (see `backend/evals/RUNBOOK.md`)
  and flip it via env var with no deploy of new code.

**Negative / costs**
- The `OPENAI_*` naming is **misleading** — it reads like a dependency on OpenAI/GPT-4.
  This is documented in `README.md`, `docs/ARCHITECTURE.md`, and here to prevent confusion.
- Reliance on the OpenAI-*compatible* surface of Google AI Studio; if that compatibility
  layer changes, the shim may need adjustment.
- Preview models (`-preview` suffix) can change or be deprecated; the routing seam and the
  deterministic fallback summary (`fallback_summary.py`) bound that risk.
