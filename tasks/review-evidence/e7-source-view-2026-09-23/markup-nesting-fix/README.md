# Unsupported nesting correction — 23 September 2026

[Exact-head review](https://github.com/neilmac91/EarningsNerd/pull/940#discussion_r4080128346) found that balanced nested anchors could give later text the wrong hidden ancestry. The explicit-close check alone could not detect this. Two fresh refutations reproduced both direct and intervening-descendant nesting.

The existing rejection boundary now covers nested anchors, buttons, forms, nobr and headings; unsupported select mode; stray table parts; and text or starts requiring table foster parenting. Table text uses HTML ASCII whitespace, so non-breaking-space entities cannot escape the check. Explicit nested cells/tables and script/style audit exclusions are retained. Nearest-table cell/caption state is constant-time, avoiding a repeated ancestry scan on ordinary elements. This is a conservative offline projection, not a complete HTML/CSS renderer; unsupported syntax holds the source for another review route instead of repairing it silently.

Measured commit `2f59c73be3568a69fb5454abf993b95d8c896dc1`: **3655 passed, 40 warnings in 160.73s (0:02:40)**, zero failures/errors/skips; all four PostgreSQL lanes and both performance cases, Ruff, Bandit and dependency checks passed. [Receipt](full-gate-receipt.json). The known interpreter-shutdown logging warning follows successful pytest completion.

The existing single invariant test was extended. The central rejection helper is AST-identical to the one whose committed-state mutation at `e50afcbd` failed once (**1 failed, 2 warnings in 1.00s**) and whose exact restoration passed (**1 passed, 2 warnings in 0.73s**). That [proof](../markup-closure-fix/mutation-proof.json) was not repeated; it establishes the rejection boundary, while the expanded fixture cases and full gate validate this extension. No spend, readiness or required-brief guard changed.

All six H29 views and 24 generated files remain byte-identical. [Equivalence](pilot-equivalence.json). The individually frozen A brief remains eligible; compacted B remains ineligible. No pair, reconciliation, E7 generation or Fable judgment was completed by this correction.

[Independent review](independent-review.md) records the final correction and its limits. The original source files and review artifacts remain authoritative. The two earlier denied proof holds remain unresolved. Fresh exact-head hosted checks are required after publication; local validation does not establish E7 acceptance or authorize deployment.

The [author receipt](author-findings.md) retains bounded reproduction and performance measurements. The read-only provider balance before the bounded PR regression was USD 66.89 ([receipt](balance-before-push.json)); no E7 programme allowance was used.
