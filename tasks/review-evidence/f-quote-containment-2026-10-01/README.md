# Prose-quotation containment: offline study (item F, 2026-10-01)

This is the offline replay that decision F requires before any implementation or paid run (PR #1029, comment 5925688598). It ran at zero spend. Nothing here is in production: `candidate.diff` is a sketch against main `0032bca8` and has not been applied to the repository.

## Candidate rule

`unsupported_prose_quotations(answer, normalized_source)` runs on the final published prose. It uses the production `normalize_for_match`, as citation verification does.

- **What it checks.**
  - Double-quoted spans in `"`, `“`, `”` or `„`, of at least `_MIN_VERIFIABLE_LEN` = 24 normalized characters. This is the existing citation constant, so no new threshold is introduced.
  - Any quoted span containing an internal ellipsis, whatever its length.
- **What passes.** A span passes only if it is contiguous in the source.
- **Before matching.**
  - Citation markers are stripped, but the literal span is tried first, so a source bracket such as "Note [7]" still passes.
  - Edge punctuation and whitespace are trimmed.
- **What fails closed.** Unbalanced quote marks and missing source text both fail.
- **Failure codes.** There are four, all fixed strings: `quotation_not_in_source`, `elided_quotation`, `unbalanced_quotation` and `quotation_source_unavailable`.
- **What happens on failure.** The answer is withheld through the existing `_UnpublishableAnswer` / `_PUBLICATION_ERROR` path. It is never repaired or paraphrased, and the log carries only the code.

## Replay over 12 retained runs (216 rows, 213 published)

**Against the retained audit (`../pr1021-qualification-2026-10-01/audits/`):**

| | Audit flagged | Audit not flagged |
| --- | --- | --- |
| Rule flagged | **20** | 0 |
| Rule not flagged | 0 | 193 |

- **No false positives.** None of the 23 rows whose quotes really are in the source is flagged.
- **Every flag is a real composition**, checked against the source tables:
  - ASML `"Total net sales 32,667.3"` joins a row label to a cell two columns away.
  - BABA `"Revenue ... 996,347"` skips four cells.
- **Withheld rate on main's code:** 3 of 108 rows (2.78%; Wilson 95% interval 0.95–7.85%), one row in each of 3 of the 6 runs. On the old prompt the rate is 17 of 105.
- **Known span-level limit** (pinned by a test): a short composition below the 24-character floor, such as `"Net income 9,609.4"`, still publishes. In this evidence, every row containing one was also withheld for a longer span.
- **Synthetic controls:** 41 cases on the real sources, all as expected. See `controls-results.json`.

## Candidate verification (scratch exports; not committed)

**Test suite.**

| | Copilot tests | Full backend suite |
| --- | --- | --- |
| Main | 435 passed | 4693 passed / 5 failed |
| With the candidate | 459 passed | 4719 passed / 5 failed |

The same 5 failures appear in both. They are E8 tests that need a git checkout, which an archive export is not. Ruff and Bandit are clean.

**Mutation proofs.** There is one mutation per guarded boundary: wiring, floor, ellipsis, normalizer, missing source, unbalanced marks, edge strip, marker strip, quote marks, and literal-first. Every one is killed by a named test (`mutation-results.json`).

**Tests touched.**
- One existing non-locked test reverses on purpose: `test_copilot_citation_repair.py::test_unsupported_claim_shapes_abstain[quotation]` currently publishes a quote that is absent from its source. The candidate replaces it with an in-source quotation case.
- The locked contract anchors are untouched.

## Open points before implementation (raised on #1029)

1. **Eval effect.** A withheld answer is an error row in `copilot_runner`, so any run with a composed quote reports `accepted=false`. At the observed rate that is about 40% of runs, both in F's three predeclared measurement runs and in every later backend PR's copilot-eval. Those runs already fail the #1021 audit policy, so the run-level verdict does not change, but the CI check gets redder.
2. **The floor of 24 has no margin.** At 25, two of the three main-code catches are lost, because `"Total net sales 32,667.3"` is exactly 24 characters. The recommendation is to keep 24.
3. **Gaps not covered:**
   - single-quoted spans and `«»`;
   - not-disclosed answers;
   - a stray inch mark withholds the whole answer;
   - source words split across lines.
