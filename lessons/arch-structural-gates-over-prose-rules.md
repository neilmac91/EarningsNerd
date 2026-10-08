# Encode every "never do X again" rule as a machine-checked gate, not prose

Date: 2026-07-06   Area: arch

**Context**: The refactor repeatedly found rules that were true on the day they were
written and had no way to stay true: "query keys come from the registry" (until someone
inlines one), "components/ holds only chrome" (until the next feature PR drops a file
there), "no naive datetime.utcnow() outside the 6 sanctioned token-expiry sites" (until a
7th appears). Each was converted from prose into an enforcing check, and each check is
bidirectional where it matters (a sanctioned exception being 'fixed' also fails, because
that reintroduces the original bug).

**Rule**: When a review or plan produces a "from now on" rule, land the enforcement in the
same PR: an ESLint `no-restricted-syntax` rule, a tiny spec asserting a directory listing
or AST-walk result equals a checked-in allowlist, or a CI grep that fails on hits. The rule
lives where CI runs, with a failure message that tells the author what to do instead. A
rule that only lives in CLAUDE.md or a review comment will rot.

**Evidence**: `frontend/eslint.config.mjs` (queryKey array-literal ban outside
`lib/queryKeys.ts`); `frontend/tests/unit/componentsAllowlist.spec.ts` (components/ =
ui/ + chrome allowlist); `backend/tests/unit/test_naive_utcnow_allowlist.py` (AST-based
6-site naive-utcnow allowlist, fails on additions AND on "fixing" a sanctioned site).


The read-only GET gate follows each handler into the module-level app functions it reaches,
transitively (2026-10-09, when the router ORM ratchet made services the only home for writes). A
write moved into a helper or a service therefore stays in view and keeps its documented exception;
the stale-entry check fires only once no reachable write remains, so a refactor cannot hide a
surviving OAuth state write and then remove its exception. Methods reached through an instance or a
class are still not followed. The database state is single-use; the signed browser cookie supplies
the separate browser binding.
