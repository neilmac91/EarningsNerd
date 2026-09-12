# Source-qualified debt release — September 12, 2026

[PR #829](https://github.com/neilmac91/EarningsNerd/pull/829) merged as `b251ead4ff52bf05576adedd857e123af82c0d1e` at 21:53:38 UTC. This record supersedes the local-candidate status in earlier dated notes without rewriting them.

## Accepted behavior

Selected debt balances are labelled by their own source concept. Separately acquired debt components retain their own scope, currency, date and source identity. Unproven totals and net-cash conclusions are withheld. The visible leverage slot is code-owned; unsupported model prose cannot re-enter it. Neutral commentary previously placed in this slot is intentionally lost; broader analysis remains a separate quality task.

Independent review found and corrected a selected-value/other-component-label mismatch and a model-prose admission bypass before publication. The first actual assessment found a smaller explanation error: overlapping components were described as missing other borrowings. The second assessment confirms the explanation now names overlap without relaxing the sum guard.

## Verification

Final debt code gate: Ruff and Bandit passed; PostgreSQL 15.15, four isolated CI-named concurrency lanes, performance included, `3001 passed, 29 warnings in 97.97s (0:01:37)`. Eleven locked anchors unchanged. Agent A's two committed mutation proofs for source-scope fidelity and code-owned leverage are retained in the PR body and lane ledger.

The first summary run [34720068225](https://github.com/neilmac91/EarningsNerd/actions/runs/34720068225) completed 52 attempts without errors, retries or hard vetoes. It is retained as evidence of the overlap-explanation finding. First report SHA256: `ab9ae97da620721f4c16eadd3e77fd059b51f3a24e9ecc46be58dcbd9dd222f9`.

The accepted second summary run [34720728788](https://github.com/neilmac91/EarningsNerd/actions/runs/34720728788), job `103625963404`, scored all 52 attempts without errors, retries, repairs or hard vetoes. Actual regression PASS with one advisory warning at 21:50:28.7987094 UTC. Report `eval_20260912T215027Z.json`, SHA256 `917635d57aa6c3064b3187bdd01dc9995df588836623f1c554123e6a76851221`. Verified source merge `fd322bf25214c6bd976cd64dfb952122a55a36eb` binds main `48f3758e` and head `4b64eaa7`.

Exactly six AMZN/COIN/JD leverage strings changed from the first assessment; the other 46 were unchanged. All 78 component amounts and scope labels match their source observations. All 52 raw leverage fields match final rendering; all 86 leverage-bearing occurrences across 516 retained previews match their own finals. All source and XBRL records match the first assessment. The second summary used 52 known primary calls, 2,178,056 prompt and 200,195 completion tokens; zero unknown calls. A recorded zero-dollar cost is not proof of free usage.

Second [Copilot run 34720728784](https://github.com/neilmac91/EarningsNerd/actions/runs/34720728784), job `103625963367`, passed 18/18 with no execution errors. Requested figures, currencies and periods are correct. All three ASML answers are uncited and BABA redundant sourcing remains. Inputs are byte-identical to the first Copilot round. The earlier table-attribution residual remains open even when not sampled. This release does not establish universal citation compliance.

## Limits and next work

Source inventories remain observed_partial. Preview/final association metadata remains not_observed; the matching retained text is narrower evidence. No strong judge ran. No baseline floors were relaxed or cosmetically re-pinned. No live email/job/account test, historical replay or universe-wide pregeneration was performed.

Agent B's citation/duration correction is integrated locally with this change: 3,071 tests passed on PostgreSQL 15. Its T9 exception was separately approved by the founder. Publication remains serial after this release's production verification. Existing undated fact rows remain untouched.

## Production verification

Main [CI 34721229716](https://github.com/neilmac91/EarningsNerd/actions/runs/34721229716) is green on the merge SHA. Deployment job `103627743455` records `apply_migrations: applied=0 skipped=39` at 21:58:35.8168399 UTC. Revision `earningsnerd-backend-00335-wws` serves 100 percent at 21:59:19.1348458 UTC, confirmed by the traffic listing at 21:59:20.5291609 UTC. Image `b251ead` matches the merge.

CI detailed health is healthy at 21:59:57.1021571 UTC (database 6.49 ms). Independent post-deployment `curl -fsS https://api.earningsnerd.io/health/detailed` succeeded, healthy, database 6.22 ms, timestamp 1789250429.283757; Redis disabled/healthy and SEC circuit closed in both checks. Local retained evidence: `work/pr829-main-deploy.log` and `work/pr829-independent-health.json`. This proves serving health, not a live-account generation test.
