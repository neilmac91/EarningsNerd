# Verify "pure move" refactors with an AST-normalized per-symbol diff, not by eyeballing the diff

Date: 2026-07-05   Area: test

**Context**: The S2 split of `openai_service.py` (3,060 lines → a façade over
`app/services/ai/`) moved ±2,100 lines. No human review of a diff that size can guarantee
nothing changed in flight. A ~40-line script parsed both the base file and the new package
with `ast`, ran `ast.unparse` on every function and constant to normalize formatting, and
diffed per symbol name. Result: zero missing symbols, and the only token-level deltas were
exactly the four disclosed fix-functions — the "pure move" claim became a proof instead of
an assertion. The same idea (per-export content hash / import-only line classification)
verified the F3 and F3.1 frontend mass moves: every changed line proven to be an
import-path edit.

**Rule**: Any PR claiming "pure move" / "behavior-preserving relocation" must carry a
mechanical proof: AST-normalize (Python: `ast.parse` + `ast.unparse` per
function/constant; TS: per-export content hash or a changed-lines-are-imports-only
classification) and diff old vs new per symbol. Zero undisclosed deltas or the claim is
false. Reviewers re-run the proof; they do not re-read the move.

**Evidence**: PR #550 (S2 façade — AST diff found only the 4 disclosed fixes);
PR #559 / #561 (F3/F3.1 — 184 and 50 changed lines, all proven import-path edits,
including the tsc-invisible `vi.mock()`/`next/dynamic` string paths).
