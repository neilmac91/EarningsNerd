# Copilot citation whole-excerpt fix: offline evidence

This is the fix approved in #1029 comment 5947962998: the approach, the `section_ref` rule and the forward-quote read-time check. The diagnosis is in `../citation-excerpt-diagnosis-2026-10-02/`.

Branch `claude/citation-whole-excerpt` holds three code commits, on main `f6e79a50`:

| Commit | Content |
| --- | --- |
| `db854097` | the strict-xfail regression |
| `77f3f126` | the provenance helper and forward quotes |
| `a8a2d5a7` | Copilot citations and the `section_ref` rule |

Main was then merged in twice, `f896afbe` (B) and `0f4dffa9` (K). Neither overlaps the 7 files this fix touches. Everything here is offline: no provider calls and no spend.

## Author (`author/`)

- **Full gate on tree `a8a2d5a7`:** ruff and bandit clean, **5529 passed**, 39 skipped, 2 deselected.
- **Mutations M1–M8** (`mutate.py`, `mutations.log`, `mutations.json`): each one turns its named required test red, and the tree is restored clean afterwards.

  | Mutation | Failed |
  | --- | --- |
  | M1: back on `verify_excerpt_in_text` | 4 |
  | M2: no normalization | 94 |
  | M3: no wrap strip | 5 |
  | M4: inner span via `extract_quoted_span` | 7 |
  | M5: no floor | 4 |
  | M6: whole-excerpt applied globally (the provenance prefix-tolerance tests fail) | 3 |
  | M7: no `section_ref` guard | 3 |
  | M8: forward quotes back on plain `build_evidence` | 1 |

- **Replays.**
  - `replay_excerpt_boundaries.py`: 8 retained copilot-eval runs, 9 text citations. 9 of 9 verify, with 0 verdict changes and 0 quoted `section_ref`.
  - `replay_summary_surfaces.py`: 2 retained summary-eval artifacts. Forward quotes: 175 of 178 verified, the same as main, 0 presentation changes, and the enriched output equals `build_evidence` in 178 of 178.

## Independent exact-head review of `a8a2d5a7` (`review/`): APPROVE, no blocker

- **AST comparison** (`ast_compare.py`): `build_evidence`, `extract_quoted_span` and `verify_excerpt_in_text` are identical to main, and so is decision F's prose-quotation code.
- **Wrap-strip check** (`probe_strip_and_bypass.py`): a 200k-string differential fuzz shows `strip_wrapping_quotes` behaves identically after the move. The adversarial bypass probes all stay unverified, and a 50k-case property check confirms the verified needle covers everything displayed.
- **Replays.**
  - `replay_base_vs_head_enrich.py`: 140 of 140 summaries are byte-equal between base and head, across Risks, takeaways, commentary, footnotes and forward quotes. 178 of 178 forward-quote dicts equal main's.
  - `replay-results-cite-rev.json`: 9 of 9 Copilot citations are unchanged.
- **Mutations:** 16 of 16 killed (`run_mutations.sh`, `mutate.py`). Full gate: **5529** passed (`gate-*`).
  - **Retention:** the review's mutation run and the pytest count were read from stdout, not retained here. `gate-pytest-tail.txt` holds only the exit code, and the count is recorded on #1052.
- **Should-fix, outside the approved boundary:** `evals/copilot_scorers.py:65` still uses the prefix-tolerant helper. `probe_scorer_divergence.py` shows that the product can verify an excerpt the scorer marks unverified, which makes the CITATION gate stricter than the product, never more lenient. 0 of 9 retained citations are affected. Repointing the scorer needs founder approval, which is pending.
- **Nits:**
  - the `section_ref` mark set excludes `„ ‟ ＂`, F's wider set (`probe_section_ref.py`);
  - the fragment URL can miss a highlight in a narrow straight-versus-curly case;
  - the RUNBOOK "Publication admission" wording is ambiguous.

## Release head

The release head is `b3871db4`, which merges main `0f4dffa9` into the reviewed code. Its full gate result is recorded on the PR.
