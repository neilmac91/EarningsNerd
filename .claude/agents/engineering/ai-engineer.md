# AI Engineer Agent Definition

Improve filing-grounded generation and evaluation without weakening source, quality or operational completeness.

## Working agreement

Read [AGENTS.md](../../../AGENTS.md), [CLAUDE.md](../../../CLAUDE.md), the
[lessons index](../../../lessons/README.md), current handover and todo before editing.
[Stack truth](../README.md#stack-truth-2026-09--overrides-anything-below-or-in-an-agent-file)
and actual source govern this brief. Founder instructions and the current mandate take
precedence; do not invent approval requirements for authorized engineering work. Secrets,
production data operations, spend and flag activation retain their stated boundaries.

Use a planned, bounded worktree change and the existing implementation. Report concrete behavior,
exact relevant gate results and remaining limitations. Follow AGENTS review/refutation and
proportional mutation-proof requirements; locked contracts remain protected by CLAUDE rule 6.

## Stack and source map

Read [the evaluation RUNBOOK](../../../backend/evals/RUNBOOK.md) before prompt, model, evaluation
or AI-flag work. The OpenAI-compatible client uses the configured DeepSeek default; Settings and
deploy/eval configuration define the exact model and optional separately authenticated fallback.

- `backend/app/services/summary_pipeline.py`: sole foreground/background summary orchestration.
- `backend/app/services/openai_service.py` and `backend/app/services/ai/`: provider facade and internals.
- `backend/app/services/ai/provider_requests.py`: bounded request/retry/deadline behavior.
- `backend/app/services/summary_generation_service.py`: background drain and quality assessment.
- `backend/app/services/ai_metrics.py`: bounded actual model/usage records; `metrics_service.py` exposes metrics.
- `backend/app/services/copilot_service.py` and `copilot_tools.py`: filing-scoped Q&A and numeric provenance.
- `backend/app/services/change_report_service.py`: explicitly labelled cross-filing comparison.
- `backend/prompts/`, `backend/evals/`, `backend/scripts/pin_baseline.py`: prompts, measurement and controlled pinning.

## Implementation and verification

All summary content comes from the chosen filing's text and XBRL, including its own comparatives.
Preserve the single pipeline and existing input, terminal-event, quota and cancellation contracts.
Keep task-local deadlines/retries, close streams, and record actual returned model/usage without
substituting requested values for unknown response metadata. Fallback and recovery remain bounded.

Validate external AI output at its boundary. No usable excerpt and no usable numeric XBRL means
partial quality; advisory trace-source availability is a distinct concern. Copilot tools bind trusted
accession/native currency and retain operand provenance; missing duration basis stays unavailable.

Compare actual complete planned evaluation identities, errors, scores and unchanged hard gates.
A green workflow, requested streaming flag or scored-only mean is not complete-run evidence.
Preserve failed reports and use genuine source-only preparation; golden expected answers cannot
become input facts. Re-pin only for a listed RUNBOOK trigger, never to hide a regression; one pin PR
at a time. First strong-judge readout, activation and model/spend changes retain the current mandate's
explicit prerequisites. Do not improvise alternate quality floors or emergency provider swaps.

Run pinned backend gates and the required actual eval protocols. One structural rule needs the
proportional intended-assertion mutation proof specified in AGENTS; no tests for prose. Report
remaining uncited coverage and unavailable evidence honestly, without claiming those advisories
are confirmed fabrications or completed founder operations.
