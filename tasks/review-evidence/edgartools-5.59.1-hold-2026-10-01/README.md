# edgartools 5.59.1 hold: #1034 (item D, 2026-10-01)

Item D of the delegated decision (PR #1029 comment 5925688598) asked for an offline comparison of the retained Ford 10-Q fixture at both edgartools versions. The comparison ran with zero spend: no LLM calls, no SEC fetch, and network access only to PyPI.

**Decision: keep edgartools 5.58.0 and hold #1034.** The test assertion stays unchanged, nothing is added to Dependabot's ignore list, and the failing head gets no paid rerun.

## Findings

1. **Reproduction.** On main `0032bca8`, the test file `test_outlook_source_coverage.py` gives 8 passed on 5.58.0 and 1 failed, 7 passed on 5.59.1. The failure is identical to CI run 36794025549. See `pytest-*.txt`.
2. **Outlook block: different representation, nothing lost** (`diff_outlook_block.txt`). The test calls edgartools directly, so none of our `app/` code runs before the assertion. In 5.59.1:
   - table cells are separated by two spaces instead of glued together: `Adjusted EBIT (a)  $8.5 - $10.5 billion` instead of `Adjusted EBIT (a)$8.5 - $10.5 billion`;
   - rows end with a single `\n`;
   - the break before the table is gone.

   The test asserts the 5.58.0 glued string.
3. **Two genuine 5.59.1 regressions** worth reporting upstream:
   - **Missing break before a rendered table.** Prose and table run together, as in `…with the SEC.2026 Guidance`. This happens at three seams in this filing (`probe_table_seams.txt`).
   - **Real loss of characters.** In the MD&A ROIC row, `ROIC (a)8.6%(12.5%)` becomes `ROIC (a)  8.6  %  (12.5` (`roic-row.txt`). The `%)` cell is dropped:
     - the affix list at `fast_table.py:94` has only single-character affixes;
     - the check at `:301` therefore scores `%)` as 0, and its column is dropped at `:357`;
     - this bug was already present in `doc.text()`, and 5.59.1 extends it to section text.

     The per-section character comparison is in `content_compare.txt`. Part II Item 6 also loses page "66" and the signature block, which upstream drops deliberately at signatures; we do not use that section.
4. **Upstream cause.** edgartools change `wzgu` makes section text render each `<table>` through `TextExtractor.render_table`:
   - `toc_section_extractor.py:942-953` and `:1016-1055` (`pkgdiff_…toc_section_extractor.py.diff`);
   - `text_extractor.py:221-230`.

   5.58.0 appended the raw text of each `tr` (`:814`, `:856-867`). That is why cells were glued, and why 5.58.0 itself produces strings like `March 31, 202626,550,000`.

## Why no compatibility adaptation

No code in our extraction path reaches the failing assertion, so there is no compatibility defect on our side to adapt (option a). Making the literal match again would mean re-gluing cells, which reintroduces the `202626,550,000` corruption that upstream fixed. Separately, 5.59.1 loses content (`%)`), which by itself rules the upgrade out.

## For a future upgrade (not done here; needs approval)

The literal assertion matches only 5.58.0's glued output, so it will block every edgartools version that fixes cell separation. A row-preserving pattern was probed in a throwaway copy of the test and not committed:

`re.compile(r"Adjusted EBIT \(a\)[ \t]*\$8\.5 - \$10\.5 billion")`

- It passes on both versions.
- It rejects four mutations on both versions: row removed, label and value split onto separate lines, value changed, label changed.

Because it edits an assertion, adopting it needs explicit approval. The sensible time to do so is when upstream fixes regression 1, and ideally regression 2.
