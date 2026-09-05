# Resilience and complete-report gate — implementation archive

Archived 2026-09-05 after [PR #701](https://github.com/neilmac91/EarningsNerd/pull/701) merged and its deployment was verified.
Final local backend gate: `2138 passed, 2 deselected, 72 warnings in 41.03s`; Ruff and Bandit passed. The initial 52-attempt/51-score report falsely passed the old gate and remains failed evidence. The final manifest/identity/error/score-count boundary rejects incompleteness without fabricating zero quality. Invalid clock proof and leaking nested mocks were corrected; only intended-assertion failures count. Locked shared harness remains unchanged.

See the [current evidence ledger](../wave2-ledger-2026-09.md) for merge SHAs, actual CI and deployment links,
and [active handover](../handover-wave2-2026-09.md) for unmet programme conditions.
The original plan below is historical: unchecked implementation boxes record its pre-execution
state, not a request to repeat completed work. Explicit readout, broader-coverage and founder
residuals remain open in the active todo. No wave-completion claim is made.

---

## WS-6 resilience implementation — after #700

Base: measurement merged `80314db6`; deployment and detailed health are verified. Parity #698
and measurement implementation #700 are complete; the first strong-judge readout remains
credential-held. This stage does not re-pin, arm a guard, or perform founder operations.

- [ ] Integrate exact OpenAI 3.7.0 / jiter 0.16 / native httpx2 lock, preserving cryptography 50.
- [ ] Own one bounded call-local deadline and retry policy across primary, stream fallback,
  optional independently authenticated provider fallback, and section recovery; close streams.
- [ ] Record actual response model and usage per attempt, including empty-choice usage chunks;
  expose bounded summary aggregates and preserve unknown values.
- [ ] Require usable excerpt or numeric XBRL for full quality; preserve locked SSE/quota contracts.
- [ ] Update fallback Settings/inventory/deployment instructions, processor and stale routing docs.
- [ ] Prove native SDK request/retry/SSE/cancellation behavior offline, kill each new-test mutant,
  run exact full backend gate, inspect actual full CI evaluation artifact, and obtain three lenses.

### Re-plan after the first actual resilience evaluation

CI `33975395335` completed, but artifact `9972247044` is incomplete: BABA 20-F run 0
raised `TimeoutError`; only 51 of 52 attempts were scored. The existing regression gate
reported PASS because errored attempts were excluded from quality means. This is not merge
evidence. Keep the original artifact and the single baseline pin unchanged.

- [ ] Gate owner (plan_rules): fail incomplete/error/missing-score reports with explicit attempt
  denominators, preserving existing quality metrics and tolerances; prove the check by mutation.
- [ ] AI Engineer (plan_gates): retain elapsed time, stream request and preview diagnostics on
  error rows; expose sanitized actual attempt telemetry in eval logs and prove those paths.
- [ ] Chief engineer: review the correction, run the complete backend gate and inspect a new
  actual full evaluation before merging. Do not raise deadlines or re-pin without observed cause.

The first report does not identify whether the timeout occurred in a provider attempt,
recovery or the total summary deadline. No specific timeout cause is claimed yet.
