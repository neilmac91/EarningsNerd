# Runtime per-filing facts carry no `period_start` — certify annual SCOPE, never duration

Date: 2026-09-12   Area: sec / verification

**Context**: Repairing the Copilot's uncited reported-figure answers needed proof that the fact
behind "for the fiscal year ended March 31, 2025" really is the annual figure. The obvious test —
`period_end - period_start` inside the 357–373-day window `copilot_tools._prior_comparable`
already uses — would have abstained on every real answer: `facts_service._build_facts` never puts
`period_start` in the dict it writes, so every `edgar_xbrl` row stores NULL. Both retained #825
Copilot assessments confirm it: all 30+ successful `get_financial_fact` results carry
`period_start: null`. A duration guard written from the schema alone would have looked correct,
passed its fixtures, and been a no-op in production.

**Rule**: Before gating on a fact field, confirm the writer actually populates it — read the
writer, then a real retained artifact, not just the model's nullable column. When duration is
needed and absent, certify annual **scope** from evidence that does exist (the viewed filing is a
10-K/20-F/40-F, its `period_of_report` equals the fact's `period_end`, and the fact carries the
`FY` label only an annual-form point receives) and say plainly that this is scope, not a proven
duration — a same-period-end quarterly point that collapsed under `uq_financial_fact_identity`
stays indistinguishable until the writer records durations.

**Evidence**: `backend/app/services/facts_service.py::_build_facts` (no `period_start` key) and
`_fiscal_period`; `backend/app/services/copilot_service.py::_fact_certifies_claim`;
`backend/evals/RUNBOOK.md` ("Runtime per-filing facts currently omit duration starts");
`backend/tests/unit/test_copilot_citation_repair.py`.
