# Astra migration audit — September 12, 2026

Audit of `a811faf6cb11c74c0ffc12a4b0c93d385c194fdd` (#807) through `8e9ad24cb643688b7cbc146e0ecd1cfe4a2d069f` (#815), including the backend portion of #814. The audit confirms three must-fix findings: wrong production attribution, instructions to repeat merged work, and lost evaluation usage on failures/retries. The first two have dated documentation corrections. The third is under hosted assessment in [#818](https://github.com/neilmac91/EarningsNerd/pull/818); this audit remains incomplete until that fix is released and production-verified. Successful technical gates do not clear financial quality.

## Verification and current release state

The complete backend gate passed on clean audit main `8e9ad24cb643688b7cbc146e0ecd1cfe4a2d069f`, with all four PostgreSQL lanes and performance enabled:

```text
All checks passed!
No issues identified.
2870 passed, 29 warnings in 776.99s (0:12:56)
process exit: 0
```

Frontend lint, TypeScript, 592 tests across 106 files and the full production build passed on the same clean commit; all 27 static pages generated, process exit 0. The [retained frontend evidence](review-evidence/migration-audit-2026-09-12/frontend-gate.md) records the exact run. These automated checks do not establish both-theme visual or marketing-claim acceptance.

Verification required environmental recovery. A stopped PostgreSQL cluster was preserved while a disposable PostgreSQL 15 cluster was created on port 55433. The first frontend run was invalidated because Codex edited audit documents in its worktree during execution; the founder was informed immediately, documents were moved to a separate worktree, and clean-state verification restarted. An external dependency symlink then caused a build failure; installing the same locked dependencies locally allowed the full gate to pass. Neither incomplete nor invalidated runs count as evidence. Current verification cannot establish missing historical gates retroactively.

The latest backend deployment remains #814: main CI 34532285336, deploy job 103057415505, `apply_migrations: applied=0 skipped=39` at 2026-09-10T21:35:34.6414415Z, revision `earningsnerd-backend-00329-cx2` at 100% at 21:36:31.9419836Z, and healthy CI detailed health at 21:37:12.1102838Z. An independent September 12 detailed-health curl was healthy, database 7.19 ms, Redis disabled, SEC closed (response timestamp 1789201321.4936163). That response was captured in tool output, not a retained file. Actions establishes rollout traffic at deployment; no current console traffic check is claimed.

Docs #815 main CI 34580374370/deploy 103203221461 explicitly skipped deployment at 2026-09-11T08:44:36.3357990Z. The subsequent workflow-only [#817](https://github.com/neilmac91/EarningsNerd/pull/817) merged as `bf0ff3bf2dbbacef25f97945d470430ce0b5e26b`; main CI 34685717503 passed and deploy job 103532610441 skipped actual migration, deployment and health steps. Neither produced a serving revision.

## Usage correction and balance prerequisite

The integrated #818 head `208767ff4ae2016b55cb834316b88a3eb18649be` passed its full backend gate: 2,875 tests, 29 warnings, 89.86 seconds, exit 0, with Ruff/Bandit, four PostgreSQL lanes and performance. Its initial sandbox invocation could not connect to localhost; the complete restored run passed. Independent integration review verified all 11 locked anchors unchanged. The single existing mutation proof, five failures followed by five passes, is retained without repetition.

[#818 CI 34686113163](https://github.com/neilmac91/EarningsNerd/actions/runs/34686113163) and its first [paid Copilot assessment 34686148069](https://github.com/neilmac91/EarningsNerd/actions/runs/34686148069) are running. Initial draft Copilot run 34686113173 skipped. No additional assessment or merged/deployed fix is claimed. The accounting correction preserves final-generation metrics separately from incurred calls and elapsed work; it cannot reconstruct missing historical usage.

Before that assessment, the single [balance readout 34685968538](https://github.com/neilmac91/EarningsNerd/actions/runs/34685968538) returned at 2026-09-12T09:29:11.8595978Z: `is_available=true`, USD 89.17 total and topped-up balance, USD 0.00 granted balance. This is the existing Actions-configured account's balance at that instant. The GET made no model/SEC call or account/key change. It is not a future balance guarantee; the later ordinary paid assessment is recorded above.

## Provider notice and continuation boundaries

[DeepSeek's official pricing page](https://api-docs.deepseek.com/quick_start/pricing), retrieved September 12, now says V4 Pro continues after September 14 with unchanged billing. This supersedes the earlier retirement premise. Flash off-peak cache-hit/cache-miss/output rates remain $0.003/$0.15/$0.60 per million, doubled during weekday UTC 01–04 and 06–10 peak hours. Current Flash configuration matches; routing remains Flash with thinking off.

A separate should-fix remains: `backend/app/services/llm_pricing.py:23` maps `deepseek-v4-pro` to Flash rates, underpricing a Pro response. Refutation 1: the current official page confirms Pro's own $0.022/$0.66/$1.98 off-peak tariff. Refutation 2: the code's prefix lookup returns the Flash tuple before consulting Settings. This affects alternate/historical telemetry and does not authorize a provider or production-setting change.

#796, #799 and #803 are already merged and verified; do not repeat their implementations or consume a third #799/#803 assessment. #805 remains draft after its first assessment failed financial acceptance; no second round has launched. #808's historical output review does not certify current Flash acceptance. Its integration, independent cash-basis/source preparations and the remaining quality work follow the verified usage correction in reviewable slices.

The founder's “Approved. Please proceed” was reconciled against task history as approval of the exact two-row T9 metadata proposal. That narrow exception needs no further founder answer; implementation, documented contract scope and verification remain pending. Other locked contracts and founder prerequisites remain unchanged. Universe-wide pregeneration and historical replay stay held.

## Ranked findings and refutations


The independent [code review](review-evidence/migration-audit-2026-09-12/code-review.md) and [ledger review](review-evidence/migration-audit-2026-09-12/ledger-review.md) retain file/line references, concrete failure scenarios and both refutation attempts for every finding. Their claims have been reconciled against the current code and deployment evidence.

**Must-fix M1 — wrong production checkpoint.** The launch handover attributes production to #812, but #814's backend change deployed 00329-cx2. Both the PR's explicit registration API scope and its actual deploy log refute frontend-only attribution. The dated handover/todo correction identifies the correct release.

**Must-fix M2 — repeated merged work.** The handover and migration coordination plan treat #796/#799 as unfinished. Fresh merged-PR records and the current implementation plus September 9 release ledgers independently refute that status. The dated correction forbids repeating the releases or a third #799 assessment.

**Must-fix M3 — failed/retry usage omitted.** `backend/evals/runner.py:336,394–406,237–259` drops observed provider usage on exceptions/application errors and replaces prior generation usage on outer retry. The observer-to-return-path trace and a direct isolated retry reproduction both retain this finding. The W10 row recount independently shows two terminal errors without usage and 11 retried outcomes. The reviewed correction is in #818, whose first hosted assessment is running; M3 remains open until release and production verification. Historical unknown billing remains unknown.

**Should-fix — partial cache split underpricing.** `backend/app/services/llm_pricing.py:62–65` prices missing cache misses as zero even when total prompt tokens establish an unaccounted remainder. Both actual caller tracing and the real-function probe retain it: one million input tokens with 100,000 hits/absent misses yields $0.0003; specifying the remaining 900,000 misses yields $0.1353 at off-peak Flash rates. No provider-reported fields should be fabricated to hide an incomplete estimate.

**Should-fix — tariff overrides inconsistent.** `backend/app/services/llm_pricing.py:39–48,60` uses static prices for recognized models, ignoring Settings rates which the legacy helper honors. The configured-model branch trace and a comparison of both estimator paths independently retain the configuration inconsistency. The separate current-Pro tariff error is documented above. These are telemetry findings; no settings change is made by the audit.

**Should-fix/evidence limitation — measured working tree not identified.** Flash's stored source SHA predates its observed usage fields. Comparing generator changes refutes a proved prompt mismatch; checking the older runner against the stored report still fails to establish a clean measured commit. Preserve the recorded SHA and the caveat, not an invented replacement.

**Should-fix/evidence limitation — historical full gates and proofs not established.** PR809–812 bodies report 39 skips / 2 deselections and omit the required proof tails/independent historical health output. Green main/deploy logs refute a failed deployment; comments do not supply the missing evidence. Current full gates verify current state only.

**Nits — ADR means and unsupported execution order.** The actual Flash row means independently reproduce 0.9103 forward fidelity and 0.9316 depth, rather than the ADR's 0.923/0.936; append the corrected values. Baseline report stamps identify Flash 15:35:41 and Pro 15:43:18; neither filename nor report metadata establishes the README's claim that Pro ran first. Preserve originals and state the available timestamps.

## Refuted and bounded concerns

The pin matches the recorded Flash summary/harness exactly. Slim reports do not break identified scorer/comparison consumers, but lack the source evidence needed for independent financial rejudging. New telemetry keywords retain caller compatibility; live Copilot/Analysis operation labels are correctly assigned. Thinking is disabled by default, and enabled requests remove temperature. The punctuation fold is symmetric and no changed-word/figure bypass survived review. Registration metadata is GET-only and does not weaken the existing registration enforcement. The monitoring recipe explicitly remains unprovisioned; no nonexistent dashboard claim survived. Backend deploys were serially completed. Detailed evidence for each refutation is in the two linked reviews.

The W10 and reference scorer means reproduce, but their comparison changes output cap, temperature and code as well as thinking. It is descriptive evidence, not a causal experiment or a strong-judge financial acceptance. Failure/partial-source cases are not clean passes. No model change, broad generation or replay follows from this audit.
