# Turn a review-time rule into a structural test so it can't silently drift

**Area:** testing · **Date:** 2026-07-06

A rule enforced only in review (or in prose/docstrings) decays. Encode it as a test that fails the moment the invariant breaks and points the author at the fix. Field-tested three times this refactor: the `components/` = ui+chrome allowlist (vitest reads the dir, asserts against a checked-in list); the query-key eslint rule; and the naive-`datetime.utcnow()` allowlist (an AST test asserting the set of (file, function) call sites equals exactly the 6 sanctioned OAuthState/RefreshToken sites — the machine-checked replacement for the plan's 'rg → 0').

**Rule:** when you establish an invariant that a future change could silently violate (a directory's contents, a registry's completeness, a bounded exception list), write the structural test in the same PR — grep/AST/readdir the reality and assert it equals the allow-list, with a failure message naming the fix. Prefer this over a comment or a review checklist.
