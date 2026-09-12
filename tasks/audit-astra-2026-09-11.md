# Astra migration audit — September 12, 2026

Audit of `a811faf6cb11c74c0ffc12a4b0c93d385c194fdd` (#807) through `8e9ad24cb643688b7cbc146e0ecd1cfe4a2d069f` (#815), including the backend portion of #814. This is the September 11 handover's requested audit, performed on September 12. Code and GitHub evidence establish three must-fix findings: stale production attribution, instructions to repeat already-merged work, and lost evaluation usage on failures/retries. Financial quality is not cleared by successful deployment or deterministic scorer gates.

## Current verification status

The full current-main gates are pending. The first backend invocation stopped before Ruff/Bandit/pytest because the former local PostgreSQL cluster was down. Its startup subsequently entered slow crash recovery after an earlier filesystem timeout. A separate disposable PostgreSQL15 cluster was created on local port55433 without deleting or modifying the old data, and the entire gate restarted on the same clean committed main SHA with all four named PostgreSQL lanes and performance enabled. No partial gate is counted as passing. The first frontend run was invalidated because Codex edited only audit documents in its worktree while the gate ran. The founder was informed, draft documents were moved to a separate worktree, and the original worktree was restored to clean main. The full frontend gate is restarting; none of the invalidated run counts as verification. This audit does not substitute current gates for missing historical proof.

The latest backend deploy is #814: main CI34532285336, deploy103057415505, `apply_migrations: applied=0 skipped=39` at2026-09-10T21:35:34.6414415Z, `earningsnerd-backend-00329-cx2` at100% at21:36:31.9419836Z, healthy CI detailed health at21:37:12.1102838Z. #815 main CI34580374370 deploy103203221461 explicitly skipped at2026-09-11T08:44:36.3357990Z. An independent September12 detailed-health curl returned healthy, database7.19ms, Redisdisabled, SECclosed (response timestamp1789201321.4936163). The latter was captured in the tool response, not a retained response file. Actions establishes rollout traffic at deployment; no current console traffic check is claimed.

## Current provider notice — dated correction

[DeepSeek's official pricing page](https://api-docs.deepseek.com/quick_start/pricing), retrieved September12, now says V4 Pro will continue after September14 with unchanged billing. Flash off-peak cache-hit/cache-miss/output rates remain $0.003/$0.15/$0.60 per million; weekday UTC01–04 and06–10 peak rates are twice those values. Current Flash constants and peak windows match. The September10 retirement premise is superseded, not silently rewritten. Current routing remains Flash with thinking off.

Additional should-fix: `backend/app/services/llm_pricing.py:23` maps `deepseek-v4-pro` to Flash rates. An actual Pro response would be underpriced; current published Pro rates are $0.022/$0.66/$1.98 off-peak. Refutation1: direct live official-page retrieval confirms Pro retains its own tariff, unlike the retired Flash aliases. Refutation2: the code's prefix lookup returns the Flash tuple for Pro before checking Settings. This affects alternate/historical model telemetry, not current Flash routing, and does not authorize changing provider or production settings.

## Release and measurement boundaries

#796 and #799 are already merged and verified; no replacement implementation or third #799 assessment is required. #803 is also merged and verified after its two authorized rounds. #805 remains draft after its first assessment failed financial acceptance, with no second round launched. #808 remains draft: its historical summary assessment succeeded, but neither that assessment nor old local gates establish acceptance after the Flash migration. Its current-model integration and complete offline projection verification remain pending. The independent cash-basis and source-diagnostic candidates remain local.

Fix the usage-conservation defect before another paid cohort, then integrate and gate candidates against current main one reviewable PR at a time. Preserve final-generation statistics separately from total incurred calls/work. Historical omitted usage cannot be reconstructed from slim report totals or invented. Thinking remains off. No new paid/model/SEC calls, production settings changes or remote writes were performed by this audit at this checkpoint. Broad replay and universe-wide pregeneration remain held.

The findings below retain independent code and ledger refutations. The full-gate and fix status must be completed before this report is treated as a finished audit.

---

## Ranked findings and refutations

The independent [code review](review-evidence/migration-audit-2026-09-12/code-review.md) and [ledger review](review-evidence/migration-audit-2026-09-12/ledger-review.md) retain file/line references, concrete failure scenarios and both refutation attempts for every finding. Their claims have been reconciled against the current code and deployment evidence.

**Must-fix M1 — wrong production checkpoint.** The launch handover attributes production to #812, but #814's backend change deployed00329-cx2. Both the PR's explicit registration API scope and its actual deploy log refute frontend-only attribution. The dated handover/todo correction identifies the correct release.

**Must-fix M2 — repeated merged work.** The handover and migration coordination plan treat #796/#799 as unfinished. Fresh merged-PR records and the current implementation plus September9 release ledgers independently refute that status. The dated correction forbids repeating the releases or a third #799 assessment.

**Must-fix M3 — failed/retry usage omitted.** `backend/evals/runner.py:336,394–406,237–259` drops observed provider usage on exceptions/application errors and replaces prior generation usage on outer retry. The observer-to-return-path trace and a direct isolated retry reproduction both retain this finding. The W10 row recount independently shows two terminal errors without usage and 11 retried outcomes. Future accounting needs a fix; historical unknown billing remains unknown.

**Should-fix — partial cache split underpricing.** `backend/app/services/llm_pricing.py:62–65` prices missing cache misses as zero even when total prompt tokens establish an unaccounted remainder. Both actual caller tracing and the real-function probe retain it: one million input tokens with100,000 hits/absent misses yields$0.0003; specifying the remaining900,000 misses yields$0.1353 at off-peak Flash rates. No provider-reported fields should be fabricated to hide an incomplete estimate.

**Should-fix — tariff overrides inconsistent.** `backend/app/services/llm_pricing.py:39–48,60` uses static prices for recognized models, ignoring Settings rates which the legacy helper honors. The configured-model branch trace and a comparison of both estimator paths independently retain the configuration inconsistency. The separate current-Pro tariff error is documented above. These are telemetry findings; no settings change is made by the audit.

**Should-fix/evidence limitation — measured working tree not identified.** Flash's stored source SHA predates its observed usage fields. Comparing generator changes refutes a proved prompt mismatch; checking the older runner against the stored report still fails to establish a clean measured commit. Preserve the recorded SHA and the caveat, not an invented replacement.

**Should-fix/evidence limitation — historical full gates and proofs not established.** PR809–812 bodies report39skips/2deselections and omit the required proof tails/independent historical health output. Green main/deploy logs refute a failed deployment; comments do not supply the missing evidence. Current full gates verify current state only.

**Nits — ADR means and unsupported execution order.** The actual Flash row means independently reproduce0.9103 forward fidelity and0.9316 depth, rather than the ADR's0.923/0.936; append the corrected values. Baseline report stamps identify Flash15:35:41 and Pro15:43:18; neither filename nor report metadata establishes the README's claim that Pro ran first. Preserve originals and state the available timestamps.

## Refuted and bounded concerns

The pin matches the recorded Flash summary/harness exactly. Slim reports do not break identified scorer/comparison consumers, but lack the source evidence needed for independent financial rejudging. New telemetry keywords retain caller compatibility; live Copilot/Analysis operation labels are correctly assigned. Thinking is disabled by default, and enabled requests remove temperature. The punctuation fold is symmetric and no changed-word/figure bypass survived review. Registration metadata is GET-only and does not weaken the existing registration enforcement. The monitoring recipe explicitly remains unprovisioned; no nonexistent dashboard claim survived. Backend deploys were serially completed. Detailed evidence for each refutation is in the two linked reviews.

The W10 and reference scorer means reproduce, but their comparison changes output cap, temperature and code as well as thinking. It is descriptive evidence, not a causal experiment or a strong-judge financial acceptance. Failure/partial-source cases are not clean passes. No model change, broad generation or replay follows from this audit.
