# Own capital comparisons and attributed passages in code

Date: 2026-09-13 · Area: financial source integrity

Correct XBRL amounts did not prevent a model from describing two positive financing periods as a negative-to-positive transition. A separate correct cash-flow sentence left the contradiction visible. Parsed SDK dimensions also omitted scenario qualifiers, so an empty map could not establish source scope.

New financing comparisons preserve the existing selected source rows, confirm context/unit identity from already-cached instance XML, and use only current and immediate selected prior. Unknown evidence abstains. The new capital-allocation representation contains code-authored comparison plus source-matched passages; it has no unchecked sibling inference/highlight channel. Final and preview use the same owner, and only the explicit application envelope enables the new read/export representation. Legacy payloads remain legacy.

Verbatim extraction must preserve legitimate denomination. The first filter dropped Apple's valid $100 billion program combined with $0.25-to-$0.26 per-share dividend. Exact retained controls now preserve per-share amounts and calendar dates, while unscaled detached amounts remain unqualified.

Existing gates: `backend/tests/unit/test_financing_source.py` and `test_financing_comparison.py`. Two committed proofs separately substitute an older operand and admit unverified passages; both fail the integrated path and restore green. Full tails and real MELI source evidence are in `tasks/financing-comparison-2026-09-13.md`. These enforce this bounded ownership, not universal narrative correctness.
