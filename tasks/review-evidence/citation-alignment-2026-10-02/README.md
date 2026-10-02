# Copilot citation alignment: offline evidence

Founder approval: "Go with your recommendation on all open points. Please proceed to close out this effort." (2026-10-02 13:10Z), recorded in [`tasks/pr-disposition-2026-09-30.md`](../../pr-disposition-2026-09-30.md): the log entry "13:10Z — Founder" and decision items 3 (scorer repoint) and 4 (`section_ref` mark set). The recommendation, from the close-out research, has two parts:

- the `section_ref` rule uses decision F's single quote-mark set;
- the Copilot eval's CITATION scorer uses the product's whole-excerpt verifier and the same label rule.

This resolves the two open items in [the citation-fix evidence](../citation-excerpt-fix-2026-10-02/README.md) (its lines 44 and 46): the scorer should-fix and the `section_ref` mark-set nit.

Branch `claude/citation-alignment`, on main `06ad809a`; main `a541c3c8` (#1036) was merged in cleanly afterwards (`4a02063d`). Everything here is offline: no provider calls and no spend.

| Commit | Content |
| --- | --- |
| `d6d1428d` | product rule: `section_label_is_quoted` reads F's one `_QUOTE_MARK_RE`; `_SECTION_REF_QUOTE_MARKS` deleted; `_QUOTE_HINT_RE` built from `_QUOTE_MARK_RE.pattern` |
| `9cedbce1` | scorer: `verify_whole_excerpt_in_text` plus `section_label_is_quoted`, with the product's label key (`section`, else `section_ref`) |
| review round (after merge `4a02063d`) | per-mark withhold cases trimmed to the three marks the existing cases lacked; the parity gate feeds the scorer the dict `_verify_citations` returns; scorer docstrings and the evals README name the label rule; this README's corrections |

## What changed

- **Label marks.** A citation whose label holds any of `"` `＂` `“` `”` `„` `‟` is unverified (was `"` `“` `”`). `‘’`, `«»` and `″` stay outside, as in F's decided scope. The `_QUOTE_HINT_RE` pattern string is byte-identical to the old literal (visible in the diff: the old literal's first alternative is `_QUOTE_MARK_RE`'s pattern).
- **Scorer.** `score_citation_faithfulness` fails a text citation when `not verify_whole_excerpt_in_text(excerpt, source)` or `section_label_is_quoted(label)`. Both names come from modules the scorer already imported, so no import edge is added. The gate message is now `(absent, too short, or quoted section label)`; `test_copilot_live_regressions.py` asserts it exactly and was updated (not a locked test).
- **Gates** (existing owners):
  - `test_copilot.py::test_section_ref_rule_withholds_exactly_decision_f_marks`: one `_verify_citations` call over every BMP code point as a label; the withheld set equals `_QUOTE_MARK_RE`'s matches and an independently written six-mark literal.
  - `test_copilot_evals.py::test_citation_faithfulness_matches_copilot_publication`: four shapes where scorer verdict == real `_verify_citations` verdict == pinned value; the scorer reads the citation dict `_verify_citations` returns, with `verified` pinned True as on every published citation, so a scorer that trusts the flag instead of checking the excerpt and label fails the gate.
  - Per-mark withhold cases through the real service path for the three marks the existing `"` `“` `”` cases lacked (ids `U+FF02`, `U+201E`, `U+201F`), and `‘’`, `«»`, `″` labels that still publish.
- **RUNBOOK** Excerpt-verification row: lists the six marks, names the one definition, and states that the CITATION gate re-checks with the same verifier and label predicate.

## Replay: 15 retained copilot-eval runs ([`replay_scorer_alignment.py`](replay_scorer_alignment.py))

Output: [`replay-scorer-alignment.json`](replay-scorer-alignment.json), [`replay-scorer-alignment.stdout`](replay-scorer-alignment.stdout). Run against this branch's code. `old` is main's scorer, re-implemented; it reproduces the retained `citation_faithfulness` and `unverified_excerpts` on all 262 scored rows (0 mismatches). `new` and `product` are this branch's functions, called directly.

| Run | Source SHA | Text citations | XBRL citations | Withheld rows | Verdict changes |
| --- | --- | --- | --- | --- | --- |
| 36777581481 | `956244b2` | 3 | 28 | 0 | 0 |
| 36798834277 | `f3624856` | 0 | 30 | 0 | 0 |
| 36800236360 | `46e1fc5e` | 3 | 30 | 0 | 0 |
| 36809122540 | `2ec46bec` | 1 | 30 | 0 | 0 |
| 36870677818 | `7feb73c7` | 2 | 30 | 0 | 0 |
| 36963789557 | `f80e288d` | 0 | 30 | 0 | 0 |
| 36964503116 | `f80e288d` | 0 | 28 | 0 | 0 |
| 36965303868 | `f80e288d` | 0 | 30 | 0 | 0 |
| 36994753645 | `fdbea0fb` | 0 | 30 | 0 | 0 |
| 36997852891 | `86c8bcb4` | 1 | 30 | 0 | 0 |
| 37000691174 | `736dab2a` | 0 | 30 | 0 | 0 |
| 37003942265 | `f70ea0fd` | 2 | 28 | 1 | 0 |
| 37004589548 | `50e0c2c7` | 6 | 23 | 4 | 0 |
| 37005114216 | `f70ea0fd` | 1 | 30 | 0 | 0 |
| 37005546506 | `50e0c2c7` | 6 | 25 | 3 | 0 |
| **Total** | | **25** | **432** | **8** | **0** |

- **Published text citations:** 25 of 25 are True under `old`, `new` and `product`. 0 verdict changes, 0 scorer/product disagreements.
- **Withheld rows:** 7 declarations rebuilt with the product's parser are True under all three; 1 array is rejected by the parser (`Invalid citation declaration`, 37004589548 BABA/native-revenue-2026/r2). None of the 8 withholdings comes from excerpt or label verification.
- **Label scan:** 914 `section`/`section_ref` values (10 distinct) plus 7 declared labels in withheld rows (2 distinct). None holds a mark from main's set or F's set, and `section_label_is_quoted` is False for all. The only non-ASCII characters are U+00B7 and U+2014. The wider mark set changes no retained outcome.
- The retained data has no quote mark in any excerpt or label, so it shows only that nothing regresses. The divergent shapes are probed below.

## Probe shapes ([`probe_shapes.py`](probe_shapes.py))

Output: [`probe-shapes.json`](probe-shapes.json), [`probe-shapes.stdout`](probe-shapes.stdout).

| Shape | Old scorer | New scorer | Product |
| --- | --- | --- | --- |
| `(“fiscal 2027”)` inner span under the floor | F | T | T |
| `'…'`, `‘…’`, mixed `"…'` wrappers | F | T | T |
| outer pair plus inner quotes, all in source | F | T | T |
| `"…"` wrapper (control); plain verbatim | T | T | T |
| #1052 prefix: `We said "<real sentence>"` | T | F | F |
| real quoted sentence plus an invented suffix | T | F | F |
| 23-character needle in a wrapper (floor) | F | F | F |
| verbatim excerpt, label with `"` `＂` `“` `”` `„` or `‟` (one row each) | T | F | F |
| verbatim excerpt, label with `‘` `«` or `″` (F's decided limit) | T | T | T |
| verbatim excerpt, label with `&quot;` (displayed literally) | T | T | T |

Differential fuzz, 200,000 cases (seed 1052), excerpts as in the research probe plus random labels drawn from every F mark and several that are not: **0** new-scorer/product disagreements; 11,469 old False to new True and 25,730 old True to new False.

The old scorer passed the #1052 prefix and suffix shapes and the quoted-label shapes for all six marks (`probe-shapes.stdout`), all of which the product withholds (old T, product F). So the earlier claim that the CITATION gate was "stricter than the product, never more lenient" ([the citation-fix evidence](../citation-excerpt-fix-2026-10-02/README.md) line 44, repeated in ledger item 3) held only for published output: an answer that references such a citation is withheld, so the scorer never sees it.

## Mutations ([`run_mutations.py`](run_mutations.py), [`mutations.txt`](mutations.txt))

Each mutation runs `test_copilot.py`, `test_copilot_evals.py`, `test_copilot_live_regressions.py` and `test_copilot_prose_quotations.py`, then restores the file with `git checkout --`.

| Mutation | Named gate | Failed |
| --- | --- | --- |
| M1: scorer back on `verify_excerpt_in_text` | `test_citation_faithfulness_matches_copilot_publication` | 3 (fiscal-2027, single-quote wrapper, #1052 prefix) |
| M2: scorer drops the label clause | `test_citation_faithfulness_matches_copilot_publication` | 1 (quoted label) |
| M3: `section_label_is_quoted` narrowed back to `"` `“` `”` | `test_section_ref_rule_withholds_exactly_decision_f_marks` | 4 (the gate, plus the U+FF02, U+201E and U+201F withhold cases) |
| M4: the predicate on its own six-mark literal while `_QUOTE_MARK_RE` gains U+2033 | `test_section_ref_rule_withholds_exactly_decision_f_marks` | 2 (the gate, plus the `″` case of `test_other_quotation_forms_are_a_decided_limit`, since F itself widened) |

Unmutated and restored runs: 953 passed. `git status` of `backend/` is clean after the restore.

## Gate

Full gate on the review-round code, after merging main `a541c3c8`, provider keys unset: `ruff check .` and `bandit -q -r app -ll` clean, **5549 passed**, 39 skipped, 2 deselected (code commit `9cedbce1` before the review round: 5552 passed). Collection shows 11 new tests over main (`test_copilot.py` + `test_copilot_evals.py`: 171 to 182; #1036 adds none): 7 for the mark set (3 per-mark withhold cases, the BMP sweep gate, 3 labels that still publish) and 4 for the scorer parity gate.
