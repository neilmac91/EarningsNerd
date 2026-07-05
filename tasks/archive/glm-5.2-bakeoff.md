# GLM-5.2 vs DeepSeek-v4-pro bake-off (2026-06-30)

**Question (founder):** GLM-5.2 looks "amazing and reasonably cost-effective" — should we switch
the report-generation model from DeepSeek-v4-pro to GLM-5.2?

**Method:** full-pipeline env-swap. Ran the *real* EarningsNerd pipeline (`baseline` candidate =
`openai_service.summarize_filing` → deterministic markdown) on the golden set (26 verified filings ×
3 runs = 78) with `AI_DEFAULT_MODEL`/`OPENAI_BASE_URL` swapped to GLM-5.2 (z.ai,
`https://api.z.ai/api/paas/v4`). DeepSeek arm ran the identical Wave-2 prompts. Judge-on
(claude-opus-4-8). Only variable = the model.

## Result — a quality dead-heat; DeepSeek wins on speed and cost

| Metric | DeepSeek-v4-pro | GLM-5.2 | Note |
|---|---|---|---|
| schema-valid | 100% | 100% | tie |
| numeric recall | 0.815 | 0.821 | +0.6% (within stdev ~0.054 → noise) |
| numeric precision | 1.000 | 1.000 | tie (no contradicted figures) |
| coverage | 1.000 | 1.000 | tie |
| financial_depth | 0.944 | 0.940 | noise |
| specificity | 0.987 | 0.993 | noise |
| gate_fail / errors | 0% / 0 | 0% / 0 | both flawless across 78 runs |
| judge clarity / specificity | 4.00 / 3.64 | 3.99 / 3.56 | tie (old-cap judge; see caveat) |
| **latency / filing** | **31.4s** | 46.3s | DeepSeek ~48% faster |
| **price /M (input / output)** | **$0.435 / $0.87** | $1.40 / $4.40 | DeepSeek 3.2× / 5.1× cheaper |
| **est. cost / summary** | **~$0.018** | ~$0.062 | ~3.5× (input-dominated ~35k tok) |

Per-form recall was a wash (GLM better on 10-K +0.045; DeepSeek better on 10-Q/20-F ~0.02). Every
quality delta is inside the run-to-run stdev.

## Decision: STAY on DeepSeek-v4-pro; keep GLM-5.2 as a validated failover

GLM-5.2 is genuinely excellent — it matches DeepSeek on every quality dimension and ran 78/78 clean,
including the large 20-F ADRs (ASML 260k chars). It is **not**, however, more cost-effective for us:
it is ~48% slower and ~3.5× more expensive at equal quality. There is no adoption case (the runner's
rule requires *beating* baseline on schema/accuracy/coverage at acceptable latency/cost — GLM ties on
quality and loses on latency + cost).

**Value delivered anyway:** proved the pipeline is not model-locked, and wired provider-agnostic
reasoning-model handling so GLM is a one-line env-swap failover.

### How to flip to GLM-5.2 (failover / second-source)
Set on the backend service:
```
OPENAI_API_KEY=<z.ai key>
OPENAI_BASE_URL=https://api.z.ai/api/paas/v4
AI_DEFAULT_MODEL=glm-5.2
```
The pipeline auto-disables GLM's "thinking" mode for deterministic extraction via
`_thinking_disabled_model()` in `openai_service.py` (covers DeepSeek + GLM/z.ai). No code change
needed. NOTE: the hardcoded fallback models (`gemini-2.5-*` in `openai_service._fallback_models`) are
NOT served by z.ai — on a GLM failure they error rather than substitute, so results never silently
mix providers, but there is no cross-provider fallback. Add a GLM fallback id if GLM becomes primary.

## Caveats
- **Cost/latency are the deciding factors**, both measured (latency observed; price from published
  z.ai + DeepSeek rate cards, 2026-06-30). The harness does not capture per-call tokens on the
  baseline path (`cost_usd=0`), so per-summary cost is an estimate (input-dominated).
- **Judge dims used the old 60k excerpt cap** (fixed in 528827a). faithfulness/insight were
  artifact-suppressed *uniformly* across both models, so the tie holds; a fixed-cap re-run would only
  refine absolute numbers, not the verdict (deterministic precision=1.0 for both is the real
  faithfulness signal).
