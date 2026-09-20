# E3 deployment — independently verified

[Receipt](receipt.json) verifies successful main CI 35482983157 / deploy job 106004482403 on merge 38cad16189dc24d1c6b4405b9e7b4ddb4a9ca95a, completed 2026-09-20T02:11:10Z. [Migration tail](migration-tail.txt): 0 applied / 39 skipped. [Selected service state](service-selected.json) records earningsnerd-backend-00374-ddw Ready at 100% traffic. [Independent health](health-detailed.json) at 02:11:39.543493Z is healthy, database 6.51ms, after job completion. [Selected flags](selected-flags.json) confirm both attribution flags false and the expected release SHA.

The [original source hash inventory](sha256.txt) includes full run/log/read-command records retained outside Git; all source hashes were checked before copying these compact sanitized receipts. Earlier premerge deployment-pending fields remain historical, superseded by this receipt. This verifies the serving dormant release, not verifier quality, acceptance or activation.
