# Withhold qualified income deltas when source scope is unowned

Date: 2026-10-03 · Area: financial source integrity

**Context:** A separately reviewed WMT handback identified rounded display arithmetic replacing authored parent income growth with a different percentage. Consolidated income and parent-attributable income have separate operands; a matching semantic slot or displayed amount does not prove attribution and entity ownership.

**Rule:** An unsupported qualified total-net-income/loss label must not borrow the generic net-income pair or fall back to a new computed percentage from display strings. Apply withholding before stored code-owned fields as well as display parsing. Preserve original authored data, the existing whole-label mapping, operating-income exact binding and distinct whole per-share labels. Do not add entity metadata or source concepts to manufacture ownership.

**Evidence:** `backend/tests/unit/test_income_delta_scope.py` retains all nine authorized handback controls and separates synthetic conflicts. It exercises binding, stored fields, read-time enrichment and shared web/Markdown/CSV/PDF rendering. Its committed mutation proof removes the withholding decision and fails the same gate. This is a bounded engineering abstention rule; native source ownership, financial acceptance and candidate freeze remain separate.

Review correction: withholding must recognize income/earnings/loss presentation punctuation without treating it as a source-concept alias. Parse the existing units once before the guard; two successfully parsed percentages retain percentage-point arithmetic, while missing/mixed units cannot exempt a qualified amount or stale field. Preserve the whole per-share exception for those same presentation variants and the original generic cached-field contract. The existing gate collects both review defects in one synthetic comparison; a separate successor mutation reverts only this correction to the previous service bytes and must reveal both findings together. Original mutation evidence remains unchanged.
