# Source-unit quote-context release evidence — September 12, 2026

[PR #823](https://github.com/neilmac91/EarningsNerd/pull/823) merged as `d2c176f6019b3dbef431b44f55a7c635f8cf4a36` at 2026-09-12T14:54:28Z. Bounded assessment is accepted. Main CI `34700643792` and deploy job `103572015821` succeeded; production is verified. The preceding [cash-basis release](../cash-basis-2026-09-12/README.md) is verified.

The [summary acceptance](pr823-first-summary-unit-acceptance.md), [association integrity](pr823-first-summary-unit-integrity.json) and [usage accounting](pr823-first-summary-usage.json) preserve 52 outcomes, 85 quotes and 515 retained preview frames. Exactly two COST quotes received the correct complete source declaration; the other 83 abstained. All raw quote strings remain unchanged. Actual rendered Markdown places the declaration beside both selected quotes; no preview annotation is claimed. All source/XBRL and deterministic cash fields match the second #821 artifact. The missing persisted envelope in the artifact limits live trust/export claims to the existing committed consumer controls. COST authored guidance remains wrong; the separate correct quote does not repair it.

The [Copilot acceptance](pr823-first-copilot-acceptance.md) and [integrity](pr823-first-copilot-integrity.json) retain run `34700027398`, job `103570025423`: 18/18 within the existing six-question gate. Inherited ASML citation-scope and redundant-source advisories remain open. The execution source `2cb44227970a5614345d930e78bd6a7854884176` has the same full tree `ee4fe35c6a10c457bc75c4fa3c528234af0f4f8c` as gated head `be5e506cd29def3b684df28c7eebaa8629025eeb`. Summary CI was `34700012703`, job `103569985371`. These are assessment identities, not deployment revisions.

[Final integration review](source-unit-final-integration-review.md) clears that head and confirms eleven locked anchors unchanged. [Local proof verification](source-unit-local-verification.md) retains the original association/delivery and distinct historical-trust proof, including failed fixture preparation and exact red/green tails. Its earlier local checkpoint is historical; the final integrated Ruff/Bandit/performance/four-PostgreSQL-lane gate passed:

```text
2906 passed, 29 warnings in 104.03s (0:01:44)
```

Exit 0 was recorded for `work/source-unit-final-integrated-gate.log`. Original proof tails, without repetition:

```text
Association mutation 39a5389c: 1 failed, 9 passed, 2 warnings in 2.12s
Restoration bd8a35f6: 10 passed, 2 warnings in 1.87s
Trust mutation 3023c479: 3 failed, 1 passed, 10 deselected, 2 warnings in 2.63s
Restoration 690de5c7: 4 passed, 10 deselected, 2 warnings in 1.98s
```

All seven linked reports are immutable copies; [archive integrity](archive-integrity.json) identifies their hashes and original private paths. Original `work/<basename>` references resolve to these copies when the basename is present. Large provider/source artifacts, logs and utilities remain private and are not bundled. Summary artifact SHA-256 is `b77191f0634d49f823bf763abbc39a66cacfc01acd99af8e7bf1ab32b3069dcb`; this checksum is identification, not independent reproducibility without the original artifact.

No world-class financial-quality clearance follows from this bounded result. Authored-guidance units, debt scope, issuer cash-flow explanations and numerical relationship prose remain open. Future work must correct the actual false claim while preserving valid reasoning; a parallel correct paragraph or metadata alone is not completion. Universe-wide pregeneration, historical replay and other founder holds remain in force.

## Production verified — September 12

Main CI `34700643792` and deploy job `103572015821` succeeded. Migrations reported `applied=0 skipped=39` at 14:59:08.2960343Z; revision `earningsnerd-backend-00333-56s` serves 100% of traffic. CI detailed health was healthy at 15:00:48.5214041Z (database 6.52 ms); independent detailed health was healthy (database 6.27 ms, server timestamp `1789225367.402431`; Redis disabled, SEC circuit closed). The independent response is retained privately in `work/pr823-independent-health.json`.
