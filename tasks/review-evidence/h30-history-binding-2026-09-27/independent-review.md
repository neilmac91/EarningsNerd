# H30 history binding independent review — 27 September 2026

Root reviewed the implementation, legacy manifest, immutable ledger and two technical settlements. This is structural evidence custody review, not a filing-quality verdict or programme admission.

## Findings and disposition

1. The original six-context closure omitted both zero-issue technical attempts. B2 had already read 8,192 source-reader bytes; absence of issues does not establish absence of exposure. Corrected to retain both settlement chains and all eight known source contexts. Counterarguments rejected: zero issues does not mean zero bytes read; a successful successor does not erase the earlier context.
2. Checking declared child hashes only bound the manifest, not retained artifact bytes. Corrected to resolve and verify all nine manifest children, four origin artifacts and both technical attempts’ child artifacts. Counterarguments rejected: the manifest hash cannot establish the availability/integrity of its children; ledger origin hashes alone do not read those bytes.
3. Self-declared row count and identity-set hash could be recomputed after omitting a row. Corrected to derive issue IDs and disagreement-index IDs from each byte-bound origin, then compare the full ledger set and declared manifest counts. Counterarguments rejected: sealing only detects later changes, not an incomplete initial submission; ensuring every origin appears does not ensure every issue appears.
4. A global identity set did not bind each identity to its particular origin context/hash. Corrected to require the derived identity-to-origin mapping per row. Counterarguments rejected: global set membership is insufficient; matching a selected origin hash does not prove the selected identity belongs to it.

The existing invariant gate must exercise coherent mutations without incidental rejection: delete a financial reconciliation row while preserving another row from that origin and reseal count/hash; swap two rows’ origin contexts and hashes while preserving the global set and every used origin. One original identity-binding mutation proof and restored gate are required before release.

Runtime-only history remains unresolved with a null typed filing locator and explicit evidence limitation. The same-context partial A3 artifact is retired history; the later current A3 source-only brief is retained. Every source-exposed context is excluded from blind downstream roles. No frozen artifact may be rewritten. No-history inventories must remain identical. Final full-suite, actual-artifact smoke and hosted review receipts remain separate from this review.

## Final bounded review additions

5. Technical attempts were permitted to declare positive issue counts even though they do not contribute ledger identities. Require exactly zero plus an empty `material_issues` array in the bound draft; attempts with findings need the origin/ledger route. Counterarguments rejected: retaining raw child bytes alone does not reconcile their findings; the actual zero-count H30 attempts do not justify accepting a positive generic input.
6. The wrapper could move the unresolved runtime hold to another history identity while coherently changing statuses/targets. Bind the hold set to the exact disagreements marked unresolved in their retained origin bytes, preserving unresolved status and null target. Counterarguments rejected: the immutable global identity set did not fix the hold classification; null-target checks only protected whichever identity the declaration selected.

The last rule is deliberately bounded. Structural validation preserves identity and status; it cannot prove from `unresolved` alone that a dispute is operational rather than financial. H30's runtime classification is independently retained in its source reconciliation/custody audit. This wrapper must not be used to turn an unresolved financial dispute into a nonfinancial limitation. No free-text heuristic classifier or financial re-judgment is introduced. Final documentation must state that limitation without claiming automatic semantic rejection.

## Final independent code disposition

Independent second review is clear on committed code `be913d718ee01c95fc7fb2a6a9e6239cae4fba57`, tree `5b31bed1be03f801adaa85082f9afd701250b156`, parent `e39b475e13a0599d037303aacc75a82d51b053b8`. Protocol SHA-256 `7acfdea9b77f1ce5b5dd7d2e44a38cc5a0fe5061a12ca8bdb4b7afc8f4160ae0`; test SHA-256 `d3d02c12a73a1b82e6bd1abe8a0c28d24662c0740f299d6f8f0723b42205a6c2`; guide SHA-256 `e9ae1ec30e463c7c530fbfebafb1d65fc85b72021f636464ea8b09968fdd6927`. The actual artifact smoke retains 52 rows (51 filing / one runtime), four origins, two technical attempts, all eight contexts, nine manifest children and six technical children, with no provider call or programme admission. Full gate and hosted release checks are recorded separately.
