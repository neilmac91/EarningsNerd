# E3 #933 — dormant release and deployment verified

[PR #933](https://github.com/neilmac91/EarningsNerd/pull/933) merged as `38cad16189dc24d1c6b4405b9e7b4ddb4a9ca95a` at 2026-09-20T02:03:28Z. Reviewed head `c7d6fa858ed9164504e0d6062243ec13e861db1b` is based on KO merge `83419e4636c501b0f1a91e1b6d819bfbbe2c3a73`. [Independent deployment receipt](e3-deploy/README.md) verifies main CI 35482983157 / job 106004482403 completed at 02:11:10Z; migrations 0 applied / 39 skipped; revision `00374-ddw` Ready at 100%; healthy independent response at 02:11:39.543493Z, database 6.51ms. Both attribution flags remain false. The dormant engineering release is complete; activation and semantic acceptance remain held.

The new subject/anchor context is labelled model-authored, capped and visibly clipped. Source selection, parser and deletion mechanics are unchanged. Verification disabled returns before request construction; deletion separately requires an armed flag and not_stated verdict.

[Compact gate/provenance receipt](e3-release-checks.json) records committed Ruff/Bandit and **3,430 tests, 78 warnings in 114.51s**, exit 0, all four PostgreSQL 15.15 lanes and performance. The original single propagation mutation failed (1 failed, 2 warnings, 5.70s); restored targeted suite passed (45 passed, 2 warnings, 6.07s). [Independent review](e3-independent-review.md.txt) covers preparation and final-base parity. No new mutation is claimed.

All six required checks passed: review-gate, backend-tests, frontend-tests, e2e-tests, lighthouse and migrations-postgres. Eval-baseline and Copilot are additional artifact checks. Actual Codex completed at 01:51:05.989396Z, with subsequent thumbs-up and zero review/inline findings; completion is distinct from the gate status.

[Baseline](e3-baseline-audit.json): CI 35482347251, 70/70 exact planned/scored, zero errors/retries/hard vetoes; all 70 excerpt hashes and source profiles verified (66 general / 4 insurer). Artifact source 950ce364c79f01beb563ef43900fdc70041c57c3 has the candidate's full tree. Trace WARN 2.1, twelve below-one citation scores, ASML currency score 0.9878, missing raw source bodies and six existing 6-K raw-provenance gaps remain disclosed.

[Copilot](e3-copilot-audit.json): run 35482355892, 18/18 planned/scored/passed terminal answers with zero errors/vetoes, 24 source files and portable DB hash verified. Five uncited-figure advisories remain. These are deterministic runner results, not new semantic judging.

[Dormancy audit](e3-dormancy-audit.json) shows both attribution flags false in the baseline harness; 66 recorded audits are unarmed, with zero dropped clauses and zero verification records. Provider records show 70 summary calls and no verifier operation. Therefore these fresh corpora **do not exercise the changed verifier prompt or measure its quality/effect**. [Bounded artifact audit](e3-artifact-audit.md.txt) retains these limits.

Historical manual review remains 48 flagged clauses across 140 attempts: 26 prospective drops = 5 correct + 4 unsafe + 17 unresolved; 21 rescues = 19 confirmed + 2 unresolved, plus one unknown. No actual deletion or E3 Fable judging occurred. Unsafe and unresolved cases block activation; different generated claims defeat causal improvement claims. PFE's missing source lead-in, joined-passage quote matching, partial-JSON repair and model-instructed unknown remain open.

User authority permits this dormant engineering release through ordinary gates despite Fable unavailability. It does not authorize activation, semantic acceptance, another judge or a general future-prompt exception. [Final observed balance](balance-after-releases.json) is USD 73.50; that snapshot is not a spending mandate.

The later [post-body review-gate receipt](e3-post-body-review-run.json) completed successfully on the same head before merge (run 35482937750). Its [separate hash record](later-review-receipts.json) identifies it as subsequent evidence, not part of the original artifact inventory.
