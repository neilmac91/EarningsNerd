# Authored guidance unit correction — local verification

Final committed head `21c72a120395fb3640d3343b3593b1ca53159302` has the reviewed backend tree and incorporates docs-only main `8dd880d977dd8484acb50466dacbe1fcc9e62052`. Both ledger parent histories are preserved. Ruff and Bandit passed; the full committed gate included performance and all four PostgreSQL lanes using a dedicated local database. Exit status 0; worktree clean.

```text
2927 passed, 29 warnings in 98.75s (0:01:38)
```

One mutation of the shared insertion proved the new source-to-final-and-preview invariant. Mutation `c510be6605f9c5617279db22c4d7049f9b53d319` and restoration `7125e8aef331628088b448033ac08ddbb3170b58` used fresh Python caches:

```text
Mutation: 3 failed, 18 passed, 14 deselected, 2 warnings in 4.83s
Restoration: 21 passed, 14 deselected, 2 warnings in 4.69s
```

The original quote-association and historical-trust proofs were not repeated. The only test-file delta against main is the ordinary source-unit test file; all eleven locked anchors remain byte-identical.

A separate copy-only check of the retained #823 corpus examined 52 outcomes. Exactly the two supported COST guidance strings gained ` million`; every other section byte remained identical, and repeating the correction was idempotent. The checker initially failed at import because its mock Settings environment was absent; it completed after supplying existing test-only settings. This was not a partial gate pass. No source/provider calls were made. Retained transformation evidence is `work/authored-guidance-retained-evidence.json`; it does not establish fresh model acceptance or general paraphrase equivalence.

Log checksums:

- `authored-guidance-mutation-red.log`: `089ceeb33e6009cdca50f389dcbf787efeea011c55a5b282f0bef18484e5664f`
- `authored-guidance-restored-green.log`: `c27123c687c3d0b6e2bf0bf7c20de67542b88f01487285f3a53b8183f3014ed8`
- `authored-units-final-gate.log`: `c393447bbc5b44fb7d6393e4face4de1aa30ff4faf3e3a082ff719b5aaf842fc`
