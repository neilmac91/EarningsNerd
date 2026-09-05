# Filing-only input and recovery hygiene — implementation archive

Archived 2026-09-05 after [PR #702](https://github.com/neilmac91/EarningsNerd/pull/702) merged and its deployment was verified.
Final local backend gate: `2167 passed, 2 deselected, 72 warnings in 40.28s`; Ruff and Bandit passed. 54 valid intended mutation failures (33 context, 21 AST). Equivalent BeautifulSoup mutations and exception/setup-only failures were retained but excluded. The final deadline test proves the inner task ended before cleanup; a no-op reschedule fails that assertion. Only the documented obsolete locked-symbol references/binding were removed; shared harness and remaining assertions were preserved.

See the [current evidence ledger](../wave2-ledger-2026-09.md) for merge SHAs, actual CI and deployment links,
and [active handover](../handover-wave2-2026-09.md) for unmet programme conditions.
The original plan below is historical: unchecked implementation boxes record its pre-execution
state, not a request to repeat completed work. Explicit readout, broader-coverage and founder
residuals remain open in the active todo. No wave-completion claim is made.

---

## WS-6 hygiene — implementation plan after verified resilience deployment

Owner: AI Engineer (plan_gates), with Knowledge Curator (plan_rules) owning RUNBOOK updates.
Base: #701 merged `f4c6041f50648fa2e5a5e4347afc1a4cd5085818`; deployment 33977786320
applied 0/skipped 34 migrations, revision `00266-q6k` serves 100% traffic and health is healthy.
#684 is closed by that integration. Hygiene implementation and its gates are pending.

- [ ] Delete both prior-filing parameters, context construction/interpolation and all forwarding
  callers; add a production AST gate for retired symbols and direct input/signature regressions.
- [ ] Delete only the three locked-background references to the retired symbol, as explicitly
  permitted by CLAUDE rule 6, plus the binding made unused by that removed assertion; preserve every other assertion and shared harness.
- [ ] Prepare immutable labelled recovery blocks once in the existing parsing worker, preserving
  exact per-form and recovered-window labels, multiple blocks and chosen-filing source only.
- [ ] Allocate at most 30,000 context characters including labels/separators: families first,
  then blocks, with deterministic redistribution and no combined-window duplication.
- [ ] Prefer an existing plain excerpt; clean fallback HTML once, remove hidden/non-content
  elements, fail closed on cleaning errors, and skip recovery when no usable source remains.
- [ ] Remove the now-unused raw-recovery parser only after proving it has no remaining caller;
  preserve the 75-second shared budget, off-loop parsing, actual usage and snap exclusions.
- [ ] Correct both observed actual-producer heading losses: exact FINANCIAL DATA alias and the
  first heading after the generated 50-equals prefix. Preserve primary excerpt bytes; prove
  actual >60k extractor-to-native-request cases without dense-backfill masking.
- [ ] Prove every new/changed test with an intended-assertion mutant; restore sources exactly,
  run the full pinned backend gate and obtain three independent review lenses.
- [ ] Inspect actual strict 26×2 CI report identities/errors/vetoes, source/figure replay and
  provider telemetry against the unchanged single pin before merge/deployment.

No model-prose tuning, re-pin, guard arming, founder operation or future Copilot feature work.
