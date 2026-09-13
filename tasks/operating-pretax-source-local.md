# Pure operating-to-pretax source adapter

Base `cab4b78cc83b302f9f01d8053e409d889e256e68`. Implements only pure acquisition from already-provided original primary HTML, no transport/pipeline/render/schema/database changes. Root owns end-to-end integration. Runtime selection uses explicit nearby consolidated-statement title and USD unit declaration, annual year headers, operating/pretax endpoints and complete supported intervening rows. Actual source cells preserve positions, spans, lexical parentheses and exact scaled integers; arithmetic corroborates source row ordering rather than assigning classification from amounts.

One invariant: only an unambiguous, source-owned complete signed reported bridge is emitted. Original whole MELI/SE source fixtures and competing recast/segment/percentage tables exercise the actual layouts. Missing/unknown rows, broken signs/units/endpoints and duplicates abstain. Do not infer recurrence, adjusted earnings, causation, accounting basis or annual fact duration beyond the literal statement period label.

Interface: `extract_operating_to_pretax_source(source_html, *, accession, document_url, period_of_report) -> dict | None`. Descriptor carries source hash/URL/accession, title/unit/table paths, explicit USD scale, all labelled year columns and their raw cell bands, current/prior operating/components/pretax values and labels. No issuer names, table ordinals or desired values participate in runtime eligibility.


## 2026-09-13 verification and corrections

The first focused run exposed two real original-source details: the MELI unit heading contains a layout table, and SE preceding siblings include HTML comments. The adapter now admits exact title/unit layout nodes while still stopping at financial tables, ignores comments, and validates each emitted comparative date with the date constructor. Original-source and negative controls then passed.

Independent correctness review found that whitespace joining could merge two numeric subcolumns into an invented integer. Two refutations failed: integer grammar is checked after joining, and a split 1|10 + 2|20 = 3|30 can still reconcile as 110 + 220 = 330. The correction requires exactly one amount-bearing cell per year band and only supported currency/parenthesis punctuation in other cells. A full original MELI statement mutation proves the counterexample; original MELI and SE positives, including separate closing parentheses, remain green.

Local process correction: the first command after that fix ran from backend with backend-prefixed staging paths; git add and commit failed, but the following focused run started on uncommitted state. That result does not count. The issue was reported immediately to root. The corrected commit `fb20920dc92bda857bffbff5f78b3257f867a772` was gated again with the focused result below. Subsequent proof and verification commands use fail-fast shell setup and a clean-tree precondition.

Committed feature: `fb20920dc92bda857bffbff5f78b3257f867a772`.

```text
20 passed, 2 warnings in 5.98s
```

One source-qualified complete-bridge invariant, with its proof re-established after the review correction: removing numeric-cell qualification at `5bc60e8ea5a9aa67315c80f1c01786eb9dd7d971` exposes the false bridge through the real original-table extraction path.

```text
FAILED tests/unit/test_statement_relationship_source.py::test_original_statement_numeric_subcolumns_cannot_fuse_into_reconciled_values
1 failed, 19 passed, 2 warnings in 6.47s
```

Restored at `e7db28c348d3fc14f1975c1342e9a7f069503e56`; entire tree `0efb6bf260757b549592cc4e2d68fc1ee31b7ca3` equals the feature tree byte-for-byte.

```text
20 passed, 2 warnings in 6.30s
All checks passed!
```

Ruff covered both new Python files, and git diff --check passed. Full saved logs are outside the worktree in `outputs/operating-pretax-local/committed-cell-green.log`, `final-mutation-red.log`, and `final-restored-green.log`. Earlier qualification proof logs remain retained for the audit trail and are superseded by this final proof, not counted as a separate invariant. Root owns the full PostgreSQL 15 gate and end-to-end integration.

Coverage limits: the caller must bind the supplied accession/document URL to its selected primary bytes; this pure adapter hashes those bytes but does not independently establish the URL metadata. Only the two demonstrated integer-money consolidated annual table grammars are eligible; unknown rows, ambiguous candidates, decimals, percentages, malformed dates, unsupported spans and missing explicit USD ownership abstain. All available year columns must reconcile. The descriptor identifies reported row position, not recurrence, cause, adjusted earnings, or a selected XBRL fact's duration/basis. No pipeline or visible output changes are delivered in this source-only slice. No network, model, database, backfill, publication or paid action occurred; all locked anchors remain outside the diff.
