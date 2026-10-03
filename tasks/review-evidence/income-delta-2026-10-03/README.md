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


## Required-review successor: presentation variants and ratio units

Implementation commit: `b3a71e1706a02d4ac1a23d89316285e72c3b149f`. This corrects two mechanical findings on predecessor `3e5f92adfb5739bf0a4eab1b43d8df29561c10e3`; the original gate/proof above remains historical and unchanged. No new filing evidence or financial judgment was introduced.

The withholding classifier recognizes income/earnings/loss and slash/parenthesis presentation variants. That normalization does not enter strict concept binding; only the original whole-label generic net-income exemption remains. Whole per-share labels admit the same presentation variants. Display values are parsed once before withholding or cached-field handling. Only two successfully parsed percentages exempt a ratio from this amount-scope withholding; mixed/missing values do not. Existing generic cached-field behavior remains unchanged.

The same machine gate now collects nine additional synthetic result pairs `(plain, cached-owned)` in one assertion, including the two cited defects, mixed/missing percentages, per-share variants, punctuation-not-alias and generic cached-field preservation.

```text
Focused committed successor: 23 passed, 9 warnings in 5.06s
```

Exactly one successor mutation replaced only `metric_delta_service.py` with the exact predecessor service bytes, leaving the successor gate unchanged. The single collected comparison exposed both findings:

```text
earnings_presentation_amount: ('+20.0%', '+99.0%') != (None, None)
loss_income_presentation_amount: ('+20.0%', '+99.0%') != (None, None)
presentation_ratio: (None, None) != ('+10.0 ppts', '+99.0%')
punctuation_is_not_generic_alias: ('+20.0%', '+99.0%') != (None, None)
1 failed, 2 warnings in 3.87s
```

The cached ratio value in this synthetic direct-call comparison preserves the existing application-owned-field contract; the real read-time binder already scrubs unmapped code fields before projection. This does not make model-authored stale fields trusted.

Restored exact committed successor bytes with a fresh bytecode prefix and reran the focused suite:

```text
23 passed, 9 warnings in 5.05s
```

Successor service SHA-256: `c0584962d391146cd8c6c0b5a9b524debb09ebd3e3ecec5bc8d16104805bbc16`. Scoped Ruff and `git diff --check` passed. This proof was a distinct correction-only mutation; the original mutation was not repeated. Full suite/push remain root-owned after integrated review, with no provider call or additional spend here.
