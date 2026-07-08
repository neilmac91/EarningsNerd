# A re-pin that first records an advisory eval dimension makes its "advisory" doc stale — sync it in the same PR

Date: 2026-07-08   Area: ops

**Context**: The T3.0 content scorers (`mean_redundancy`, `mean_delta_consistency`) shipped
"advisory": the regression gate `_check` skips any metric absent from the pinned baseline, so a
WARN gate the baseline never recorded is inert. `backend/evals/RUNBOOK.md` documented that state
("inert WARN gates today … re-pin them together with the v2 rewrite"). PR #606 re-pinned
`baseline_scores.json` on a run that DID record both dimensions — which silently flipped them from
inert to binding (floors = pinned − 0.05) and made the RUNBOOK paragraph false in the same commit.
Founder staff review caught it under the docs-vs-code rule. (The same review surfaced a second,
pre-existing drift: the RUNBOOK claimed the PR `eval-baseline` job runs a "6-filing smoke" when
`ci.yml` actually runs the full verified set × 1 run.)

**Rule**: Re-pinning is not only a numbers change — it changes which gates *bind*. Whenever a
re-pin records a metric the previous baseline lacked, grep the docs (RUNBOOK, ADRs, PR templates)
for any text calling that dimension "advisory / inert / skipped / not yet pinned" and rewrite it in
the SAME PR: state that it now binds, as of which `SUMMARY_PROMPT_VERSION` / report stamp, and its
floor. WARN floors are one-directional (fire only on a drop > tol), so pinning an improvement
protects it and cannot cap a future rewrite — say that explicitly so a future operator doesn't
"defer pinning" to avoid a lock-in that can't happen. While in that file, reconcile any description
of what the CI eval job actually runs against `ci.yml` (code is truth).

**Evidence**: PR #606 (`5dde70f`); `backend/evals/regression_gate.py::_check` (skips metrics absent
from baseline); `backend/evals/RUNBOOK.md` "Content-quality WARN dimensions … now pinned";
`.github/workflows/ci.yml` eval-baseline step (full set × 1 run on PRs). Complements
`ops-eval-gate-for-ai-changes.md` (re-pin in the same PR) and `arch-structural-gates-over-prose-rules.md`.
