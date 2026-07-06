# Prove a large 'pure move' with an AST-normalized per-symbol diff — don't rely on reviewing the shuffle

**Area:** refactor · **Date:** 2026-07-05

S2 split the 3,060-line `openai_service.py` into a façade + `ai/` package — ±2,100 moved lines. No
eyeball review of a shuffle that large can credibly certify it is byte-for-byte behavior-preserving;
the per-step suite + ruff caught a real F821 near-miss (a splice end-anchor nearly swept up
`_TRACKED_STRUCTURED_SECTIONS`), but "tests pass" only proves the exercised lines. The plan author
closed the gap mechanically with a ~40-line script: parse the base module and the new façade + package
with `ast`, `ast.unparse` every function/constant to normalize formatting, and diff per symbol NAME.
Result: zero missing symbols, zero undisclosed changes — the residual delta was exactly the disclosed
fix-functions + the new `_numeric_sort_value` helper + `__all__`. Far stronger than reviewing the diff.

**Rule:** for any large mechanical / "pure move" refactor, PROVE it with an AST-normalized per-symbol
diff — unparse each function/constant and diff by name; the residual set MUST equal the disclosed
changes (empty for a true pure move). Don't rely on review of a multi-thousand-line shuffle, and don't
mistake a green suite for full coverage. TypeScript equivalent, to run on **F3** (`components/` →
`features/` mass move — the next big pure move, and exactly where an import-path rewrite hides an
accidental edit best): a per-export content hash before/after (a sorted-declaration or `tsc`-emit diff).
