# ADR 0008 — Move to DeepSeek V4.1 Flash (`deepseek-flash`) on the forced retirement of `deepseek-v4-pro`

- **Status:** Accepted (supersedes [ADR-0006](./0006-gemini-to-deepseek.md) on the model choice; the provider decision stands)
- **Deciders:** EarningsNerd maintainers
- **Date:** 2026-09-10

## Context

ADR-0006 standardized on DeepSeek via the OpenAI-compatible client and chose `deepseek-v4-pro`
over the flash-class model "on the quality preference". On 10 September 2026 DeepSeek announced
V4.1 Flash (`deepseek-flash`), retired V4 Flash, and set 04:00 UTC on 14 September as the date
from which every `deepseek-v4-pro` request is routed to V4.1 Flash and billed at Flash rates,
until an unannounced V4.1 Pro. The `deepseek-v4-flash*` names route temporarily and can be
withdrawn without notice. There is no V4 Pro to prefer after that date; the decision is whether to
carry the retired name on a temporary alias or move to the canonical id with a measured re-pin.

V4.1 Flash is a new pretraining run (552B MoE, 8B/16B active, causal encoder–decoder), not a
post-training refresh, so prompt adherence and output shape were treated as unknown and measured:
measured on 10 September (26 verified filings × 3 runs, deterministic gate, judge off;
`backend/evals/baselines/eval_20260910T153541Z.json`, compared filing-by-filing with
`python -m evals.compare_reports` against both the 5 Sept V4 Pro pin and a same-code 1 × 26 V4 Pro
arm, `eval_20260910T154318Z.json`; evidence in `tasks/review-evidence/deepseek-v41-flash-2026-09-10/`):

- Hard gates: 78/78 scored, no errors, `gate_fail_rate` 0.0, numeric precision/accuracy/coverage
  1.0 on both models; no filing lost a gate.
- Advisory: redundancy 0.953 → 0.902 (figures restated across sections; 22/26 filings), forward-quote
  fidelity 0.962 → 0.923 (one filing); citation fidelity 0.819 → 0.906 and financial depth
  0.897 → 0.936 improved. The delta-consistency drop against the 5 Sept pin (0.947 → 0.852) is code
  drift since that pin (the same-code Pro arm scores 0.847), not the model.
- Output: 3,894 vs 2,758 completion tokens per summary (×1.42, min 1.03, max 1.87); latency
  25.6 s → 14.5 s. Cost per fresh summary still falls ~65%.
- Copilot golden set (6 questions × 3, same code): Pro 18/18, Flash 17/18; the one failure was a
  verbatim-copy miss where the source carries stray spaces before punctuation and the model tidied
  them (runs 0 and 1 of the same question passed). Numeric recall and figure coverage 1.0 on both;
  uncited figures 8 (Pro) vs 5 (Flash); no misplaced fact markers; mean answer 5.9 s vs 4.7 s.
  The verifier could tolerate that whitespace normalisation; that is a follow-up, not a blocker.

Cost on the 5–9 September token mix falls ~73% (output $1.98→$0.60, cache-miss $0.66→$0.15,
cache-hit $0.022→$0.003 per 1M, off-peak). Most of that spend was CI eval traffic, not product
traffic (see `tasks/deepseek-v41-flash-migration-2026-09-10.md` §1.4).

## Decision

- `AI_DEFAULT_MODEL = deepseek-flash` everywhere the value is written: `backend/app/config.py`,
  the Cloud Run service and pregenerate-job env in `.github/workflows/ci.yml`, the `eval-baseline`,
  `copilot-eval` and `data-quality-weekly` workflow envs, `backend/.env.example`,
  `docs/CONFIGURATION.md`, `tasks/gcp-deploy-runbook.md`. A unit test fails on any reappearance
  of a retired `deepseek-v4-` id in code or workflows.
- Thinking mode stays **off** on every path (`extra_body={"thinking": {"type": "disabled"}}`),
  because `deepseek-flash` defaults to thinking ON, thinking mode rejects `temperature`, and tool
  loops would have to replay `reasoning_content`. Enabling thinking is a separate measured change.
- Telemetry prices move to Flash off-peak (`0.003 / 0.15 / 0.60`); the peak surcharge remains
  unmodelled until the per-model price table lands (observability follow-up).
- `baseline_scores.json` is re-pinned from the Flash run; the pinned bar now encodes
  `deepseek-flash` behaviour. Prompt candidates in flight are measured against it, once each.
- Provider abstraction, per-request cost/latency/reasoning-token logging and a CI-only API key are
  follow-ups recorded in `tasks/todo.md`; none is a precondition for the cutover.

## Consequences

**Positive:** canonical id instead of a withdrawable alias; ~73% lower inference cost at the
measured quality; eval runs cheap enough to keep 3 repeats on every AI-relevant PR.

**Negative / costs:** quality is re-based on a model with no independent financial-document
evaluation beyond our own gate; V4.1 Pro, when it ships, needs its own bake-off before adoption;
the model id is still written in nine places until the single-source change lands.

**Later opportunity (parked):** `deepseek-flash` accepts image input natively; filings are text
and iXBRL, so no near-term use. Revisit for scanned 6-K/20-F exhibits.

## September 12 factual correction

[DeepSeek's current official pricing notice](https://api-docs.deepseek.com/quick_start/pricing), retrieved September12, now states that V4 Pro service continues after September14 with unchanged billing. This supersedes the retirement premise recorded above. It does not reverse this accepted model choice: production remains Flash with thinking off. Current Flash off-peak prices and2× peak schedule match the configuration; Pro retains its own $0.022/$0.66/$1.98 tariff per million tokens.

The frozen Flash report's forward fidelity and financial-depth means are0.9103 and0.9316 (also reproduced from its rows), correcting0.923 and0.936 above. Its source SHA records HEAD but does not establish a clean measured working tree: the report includes observer fields introduced after that commit. The generation code comparison found no prompt difference; a different working tree is not evidence of different generation. See the [September12 audit](../../tasks/audit-astra-2026-09-11.md) for bounded measurement and historical cost/gate evidence.
