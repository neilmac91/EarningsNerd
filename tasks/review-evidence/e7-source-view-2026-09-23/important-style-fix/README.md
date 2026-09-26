# Inline important-style annotation fix — 23 September 2026

[Hosted review](https://github.com/neilmac91/EarningsNerd/pull/940#discussion_r4079772760) found that `display:none!important` and `visibility:hidden !important` kept their source text but lacked the reader's hidden-content annotation. Commit `a0fea57bb981ae55f21bb3aa72146fbc19eacb20` accepts the optional important suffix with whitespace/case handling and preserves declaration boundaries. It extends the existing source-view invariant gate. Raw style attributes, exact source spans and all text remain intact. This is lexical annotation; full CSS rendering is still explicitly unassessed.

**3655 passed, 40 warnings in 166.33s (0:02:46)**, zero failures/errors/skips, all four PostgreSQL lanes and both performance tests. Ruff, Bandit and dependency checks passed. [Full gate](full-gate-receipt.json). An earlier sandbox attempt had 39 PostgreSQL setup errors because local TCP was denied; its failed receipt is retained, and the identical backend passed with authorized local database access. The known interpreter-shutdown logging warning is outside successful pytest execution.

On committed state, restoring only the old matcher caused **1 failed, 2 warnings in 3.93s**, at the intended missing-hidden-annotation assertion. Exact restoration produced **1 passed, 2 warnings in 0.73s**. No readiness or budget guard changed. The receipt script initially expected a later assertion; the original logs establish the earlier valid failure, and the mutation was not repeated. [Mutation proof](mutation-proof.json).

[Independent review](independent-review.md) found no actionable issue after correctness, custody and gate checks, with fresh refutations of matching, raw-span preservation, descendant/table-row propagation and boundary controls.

All six H29 views were regenerated with the fixed code: all 24 generated artifacts are byte-identical to the original frozen dossier. [Equivalence receipt](pilot-equivalence.json). The historical view-code identity and source-review artifacts are preserved; no financial review or judging was repeated. H29 A remains individually frozen and B remains partial/ineligible after compaction, with zero complete pairs or reconciliations.

Provider balance immediately before this PR regression was USD 68.25 ([read-only receipt](balance-before-push.json)). This is standing-authorized bounded PR regression, not E7 programme admission. The earlier two automatically denied guard-removal proofs remain unresolved; no retry or release waiver is implied.
