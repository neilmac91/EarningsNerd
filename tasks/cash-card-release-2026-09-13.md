# Cash-card applicability release — September 13, 2026

PR [#845](https://github.com/neilmac91/EarningsNerd/pull/845) merged reviewed head 9c74719d5471473c7a75a1a34b62a89d7e9617bf as 8667f9902a3bbe759b22e49e09b7933992e87afe at 2026-09-13T03:59:53Z. Both conventional cash owners require affirmative nonfinancial classification and retain the bank-components veto. New financial/unknown inputs withhold the derived card; existing summaries are not replayed. Stamp summary-2026-09-m, schema 2.

Full committed Ruff/Bandit/PostgreSQL 15 gate, four CI-named lanes and performance, exited 0:

```text
3261 passed, 29 warnings in 105.61s (0:01:45)
```

The first full run failed eight ordinary fixture premises (3253 passed); their nonfinancial premise was made explicit, preserving prior assertions. No locked anchor changed. [Implementation/proof history](cash-card-applicability-local.md) and [independent review](review-evidence/cash-card-2026-09-13/independent-review.md) retain the failed run and final identical-tree mutation proof.

## Actual acceptance

CI 34736361672, summary job 103668398611, and Copilot 34736385365 / job 103668462885 passed. [Summary acceptance](review-evidence/cash-card-2026-09-13/summary-acceptance.md) verifies 52 completed attempts with no errors or retries, exact sources/excerpts/XBRL/statement descriptors versus PR #842, and only the two intended COIN card removals. Forty-six cards remain; the other 50 card fields are identical, including already-absent JPM/COST. All 52 cash/debt/owned financing strings, 67 selected exact source passages, and complete SE/MELI owned disclosures survive. [Copilot acceptance](review-evidence/cash-card-2026-09-13/copilot-acceptance.md) records 18/18, exact inputs/messages/schema/options, 24 unchanged sources and 30 unchanged numeric citations. The existing ASML supplemental-scope issue remains.

Report SHA256 ae205ecca56d30c67fe204b768b1390a08dbd0cd178331be043c028a94281e61; source 363dfcd615fc5def463092a5845f5bccd6b5ca71 has GitHub-verified parents 707e64b6788d33e9b871bec04e8d2a9da3b75ad5 and the reviewed head. [Identity/usage evidence](review-evidence/cash-card-2026-09-13/identity-checks.json) records 52 successful calls, 2,179,026 prompt tokens and 192,440 completion tokens. All observed callbacks were retained, but final-response association is not observed. No strong judge or native 52-export sweep is claimed. No finite lead qualifier activated in this sample; broader unmatched wording and MELI economic meaning remain unresolved.

## Production verification

Main CI 34736826776 and deployment job 103670068270 succeeded. Migration log at 2026-09-13T04:05:27.7028320Z reports `apply_migrations: applied=0 skipped=39`. Revision `earningsnerd-backend-00342-bmf` serves 100% at 04:06:23.3798664Z, with the latest-revision traffic confirmation at 04:06:24.8395585Z. CI detailed health is healthy at 04:07:03.0389389Z (database 6.89 ms, response timestamp 1789272423.0040007). Independent `curl -fsS` is healthy (database 7.22 ms, response timestamp 1789272462.6017158). No backend deployment remains unverified.

## Next work

The [E09 refinement](review-evidence/cash-card-2026-09-13/e09-proposal-refinement.md) credits bounded successful scan history and explicitly retains missing fleet/database/provider/SEC evidence. It remains a proposal, not fleet implementation or capacity clearance. Universe pregeneration and historical replay stay held; quality-corpus acceptance does not supersede the founder's world-class requirement.
