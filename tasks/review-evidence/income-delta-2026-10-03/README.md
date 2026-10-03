# Qualified income delta correction: engineering verification

The source-ownership handback authorizes withholding application-computed percentages for unsupported qualified total-income scope. The code changes no whole-label concept mapping or prompt. It rejects unsupported scope before accepting stored code fields or parsing rounded display amounts. Native entity ownership remains unavailable; this is withholding, not financial clearance.

Verified implementation commit: `7b25f98150d22e6cba519a0fa9599b7b4fa5d0eb`. Base: `70282ddee1d5602fc56e323e8ebcdd5bd6dc05f4`. This evidence-only follow-up does not change tested backend bytes.

The one new regression gate retains all nine approved WMT handback controls, plus separately identified synthetic scope conflicts. It checks source binding, cached code fields, read-time enrichment and shared web/Markdown/CSV/PDF projection. Generic exact net income and operating income retain the existing mapping; the approved basic/diluted per-share controls retain their separate display calculation. The one changed existing assertion is the unlocked `test_summary_sections_model.py` adjusted-income cell, now an em dash.

Focused command, using root's pinned Python3.11 environment and a fresh bytecode prefix each run:

```text
python -m pytest tests/unit/test_income_delta_scope.py tests/unit/test_metric_delta_service.py tests/unit/test_summary_sections_model.py -q
23 passed, 9 warnings in 5.20s
```

Exactly one mutation was applied to that committed clean implementation: remove the two-line early `_has_unsupported_income_scope` rejection from `delta_for_row`. No fixture or expectation was changed.

```text
assert deltas.row_delta_fields(originals[index]) == {}
E AssertionError: assert {'change_display': '+12.9%', 'change_direction': 'up', 'change_tone': 'gain'} == {}
FAILED tests/unit/test_income_delta_scope.py::test_qualified_income_abstains_without_borrowing_operands_or_rounded_fallback
1 failed, 2 warnings in 3.86s
```

Restored the exact committed service bytes, then reran the same focused three-file suite:

```text
23 passed, 9 warnings in 4.34s
```

Restored service SHA-256: `1e6a1850eea3903f688d5a0059476c3e6773ff7988af83ba753e7e6b8558abcd`. The worktree was clean after restoration. Scoped Ruff passed. Full backend gate is deferred to root's once-only integrated pre-push gate after the security base settles; no full suite, push, deployment, source acquisition or provider call was performed here. New DeepSeek spend: USD0.

The original exact-display parent row's authored change stays intact in raw data, but its computed cell is withheld too because display precision does not establish native entity ownership. No newly source-verified +12.6% parent or +10.5% consolidated result is claimed. Unrecognized alternate per-share spellings may conservatively withhold; the approved whole per-share labels are preserved. Financial disposition, runtime parity, source custody and candidate freeze holds remain separate.
