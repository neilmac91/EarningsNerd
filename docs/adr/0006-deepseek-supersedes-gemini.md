# ADR 0006 — Standardize on DeepSeek V4 as the default AI provider (supersedes ADR-0002)

- **Status:** Accepted
- **Supersedes:** [ADR-0002](./0002-openai-gpt4-to-gemini.md) (Gemini via Google AI Studio)
- **Deciders:** EarningsNerd maintainers

## Context

ADR-0002 pointed the OpenAI-compatible client at Google AI Studio (Gemini). Since then the summary
quality work moved to a real eval harness (`backend/evals/`, see `RUNBOOK.md`): a golden set scored
by deterministic scorers plus an LLM judge, run as a bake-off across candidate models. That harness
is now the gate for a provider/model change — and it selected **DeepSeek V4** as the default.

The decision is fundamentally the ADR-0002 architecture paying off: because the provider is just an
OpenAI-compatible `OPENAI_BASE_URL` + `AI_DEFAULT_MODEL` seam, switching vendors is an env change,
not a code rewrite. Nothing about the client, retry logic, or JSON-repair path changed.

## Decision

Standardize on **DeepSeek V4** via its OpenAI-compatible endpoint:

- `OPENAI_BASE_URL = https://api.deepseek.com/v1` (`backend/app/config.py`).
- `AI_DEFAULT_MODEL = deepseek-v4-pro` — chose `pro` over `flash` on the quality preference.
- **Thinking mode is disabled for deterministic extraction.** DeepSeek is a reasoning model; the
  pipeline turns "thinking" off for the structured-extraction calls so the whole token budget goes to
  the answer (a reasoning model left in thinking mode can return empty `content` under a normal cap).
  The switch is gated on a `"deepseek" in model/base_url` check plus the generic z.ai-style
  `extra_body={"thinking":{"type":"disabled"}}` path, so any reasoning provider can opt in.
- `config.py` validates `OPENAI_BASE_URL` against a small allow-list of recognized providers
  (`api.deepseek.com`, `generativelanguage.googleapis.com`, `openrouter.ai`).
- The **default-off routing seam** from ADR-0002 is retained unchanged: `AI_FAST_MODEL` (a cheaper
  model any task can opt into) and `AI_SECTION_RECOVERY_MODEL` (overrides just section recovery,
  falling back to `AI_FAST_MODEL` then `AI_DEFAULT_MODEL`). Both default to `""`.

Provider + model remain fully env-configurable; Gemini stays a validated env-swap failover, not the
default. GLM-5.2 was bench-tested and rejected (matched quality but ~48% slower / ~3.5× costlier).

## Consequences

**Positive**
- The default is now chosen by measured eval quality/cost, not by an untested switch.
- Zero code change to adopt: same OpenAI-compatible client, retry, and JSON-repair path as ADR-0002.
- DeepSeek's context-cache pricing lowers per-summary input cost on cache hits.

**Negative / costs**
- The `OPENAI_*` env naming remains **misleading** (it is a compatibility shim, not an OpenAI
  dependency) — carried over from ADR-0002 and documented in the README + `docs/ARCHITECTURE.md`.
- Reasoning-model handling (thinking-off for extraction) is a per-provider quirk; a new provider needs
  the same treatment verified with a 1-call smoke before a bake-off (see
  `lessons/bake-off-a-model-swap-the-way-prod-runs-it.md`).
- Reliance on DeepSeek's OpenAI-compatible surface; the deterministic `fallback_summary.py` bounds the
  outage risk, and the env seam makes a provider switch a config change.
