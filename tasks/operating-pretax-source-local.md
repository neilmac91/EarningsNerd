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

## 2026-09-13 integration and preservation correction

The source-only scope above is superseded by this integration. The existing production pipeline snapshots `Filing.period_end_date` (a DateTime column, normalized to its calendar date), and passes a request-local descriptor only when the existing fetch already supplied primary HTML. Eval builds the same descriptor from its existing primary fetch. The actual inline DEI date uses the supported month-name transformation and its issuer context; it must agree with production's stored report period. Missing/ambiguous/qualified context, unsupported annual layout or unavailable primary text leaves legacy behavior. No additional resolver or SEC request is introduced.

The descriptor stays outside standardized XBRL, generator and recovery messages. A fresh source descriptor can legitimately coexist with an older cached model excerpt: it is independent application evidence identified by accession, document URL and decoded-source hash, never a claim that the model saw the preserved passages. The production fresh/stale/cache controls exercise caller transport and identity with the existing boundary harness; the unchanged actual cache-owner test `test_eval_measurement.py::test_excerpt_inventory_observes_returned_string_without_reextracting_cache` separately proves cached bytes are returned without re-extraction. All these controls passed together. The background path inherits the one pipeline; no second generation path exists.

Preview and final use one explicit source-owned earnings-quality projection, before final coverage/persistence/export diverge. Preview only projects a completed earnings-quality section. Both old prose aliases and forged model-owned fields are removed on the qualified path; the explicit outer integer envelope authorizes the new shared renderer. Legacy and unavailable requests retain their previous prose. Cash conversion and separate red flags remain under their existing owners. Raw source provenance is not dumped into the legacy management-discussion string.

The admitted operating section retains the complete signed source block, including actual provision/impairment rows; the full operating-to-pretax bridge is independently owned. All complete leaf paragraphs in the selected expense-change block survive until the actual styled next heading; a first matching sentence cannot silently drop a later caveat. Original SE preserves its 2024 class-action settlement disclosure and current/prior credit provision. Original MELI preserves provision amounts and the source originations explanation, the adjacent comparative presentation note, the complete audited Note 2 reclassification paragraphs, current/prior tax expense 845/521 million USD, deferred-tax benefit 469 million USD, and the full audited 21.4% to 29.7% effective-rate paragraph. Tax and presentation disclosures remain explicitly separate from operating classification; no recurrence or causal interpretation is invented.

The tax/policy parser was supplied by the independent source agent and integrated here. Review found that a continuation ending did not prove a subsection ended. The corrected parser requires the observed next recast-table boundary for Note 2 and the following deferred-tax-assets subsection boundary for the effective-rate paragraph, rejects extra intervening caveats, and checks unique incoming ownership of each continuation. Tax applicability is declared by the exact audited heading or one complete supported component table, never a concept vocabulary assembled across unrelated tables. A malformed supported source still fails closed. SE's different audited tax layout is explicitly `unsupported_layout`, and its policy note is `no_supported_subsection`; neither means the filing lacks taxes or accounting disclosures. This release is bounded to the demonstrated operating slot. Root must inspect any other eligible corpus issuer for lost valid disclosure before acceptance.

Integration failures were resolved against actual source: SE comment nodes do not support the usual `.get` default behavior; the database report period is DateTime rather than Date; generic expense definitions can cross page furniture and do not establish the supported period-change block; and a complete tax concept vocabulary across SE's long note chain did not establish one supported table. The corrected source path passes actual MELI and SE controls. Original current values, issuer identifiers and context dates remain source-read; no desired issuer numbers are encoded in runtime selection.

### One additional visible-ownership invariant

Feature `24e2f2f4d4b8b9f674d3b3df020e42180ba9e87c` passed the real stream/final/export and production/eval controls:

```text
15 passed, 9 warnings in 8.84s
```

Mutation `825fb4b62efd0c1775965d443700962d8297f524` bypassed the shared trusted projection. Both original-source cases failed at their visible final-output assertions, rather than merely at unused metadata checks:

```text
FAILED tests/unit/test_statement_relationship_integration.py::test_original_primary_to_real_stream_final_and_exports_owns_classification[meli]
FAILED tests/unit/test_statement_relationship_integration.py::test_original_primary_to_real_stream_final_and_exports_owns_classification[se]
2 failed, 13 passed, 9 warnings in 9.43s
```

Restoration `d85fccd1646d9206fcfb6955452844ce06272e69` has entire tree `0d8dd9a71dc809f0761593c0788a654f919b1121`, byte-identical to the feature. The combined source, disclosure, integration and existing eval-measurement controls then passed:

```text
114 passed, 9 warnings in 16.13s
All checks passed!
```

The final Ruff command covered every changed/new integration Python file; the source adapter's Ruff pass is recorded above. `git diff --check` passed. All eleven locked anchors remain byte-identical to base; hashes are saved outside the repository in `outputs/operating-pretax-local/locked-anchors.json`. No full gate is claimed here: root owns current-main integration, content version/RUNBOOK and the full PostgreSQL 15 gate.

Full logs: `outputs/operating-pretax-local/ownership-feature-green.log`, `ownership-mutation-red.log`, `ownership-restored-green.log`. Source acquisition's earlier independent proof remains the separately recorded source invariant; this is exactly one additional visible-ownership proof. The actual retained before/after and full descriptors are saved in the same output directory.

Optional judges receive a separately labelled complete source descriptor in addition to the unchanged generator excerpt; existing cap checks fail visibly rather than truncate. Final serialized descriptors are 19,100 characters (MELI) and 13,252 (SE). Combined with the actual first-PR837 excerpts and wrappers, MELI totals 249,920 characters and SE 122,963. The existing excerpt cap is 200,000; MELI's original excerpt alone was already 230,682. Its optional judge therefore reports incomplete coverage, while SE fits. The cap is unchanged, and no filing evidence is dropped to force a pass. Measurements live in `outputs/operating-pretax-local/judge-evidence-measurements.json`.

- [x] Pure source adapter and original-source controls.
- [x] Production/eval context transport without additional fetches.
- [x] Shared visible ownership and explicit legacy boundary.
- [x] Actual operating, settlement, tax, effective-rate and Note 2 preservation.
- [x] Committed focused gates and two distinct invariant proofs.
- [ ] Root's current-main integration, full gates and final independent review.
- [ ] Actual corpus assessment, other-issuer preservation review and serial release.

No publication, provider request, paid run, production database change, historical replay, flag change or backfill occurred in this subtask. Universe-wide pregeneration remains held.
