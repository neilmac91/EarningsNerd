# edgartools 5.61.1 hold: #1285 (2026-10-13)

Dependabot [#1285](https://github.com/neilmac91/EarningsNerd/pull/1285) (head `b802f5cb`) proposes
edgartools 5.58.0 → 5.61.1. [Issue #1063](https://github.com/neilmac91/EarningsNerd/issues/1063)
and decision D ([`pr-disposition-2026-09-30.md`](../../pr-disposition-2026-09-30.md)) hold
edgartools at 5.58.0 until the Ford affix and boundary regressions found in 5.59.1 are fixed
upstream. This record repeats the [5.59.1 comparison](../edgartools-5.59.1-hold-2026-10-01/README.md)
at 5.61.1, offline and with zero spend: no LLM call, no SEC fetch, network only to PyPI.

**Decision: keep edgartools 5.58.0 and hold #1285.** The test assertion stays unchanged, nothing is
added to Dependabot's ignore list, and the failing head gets no paid rerun. The PR stays open as
Dependabot's tracker, as #1034 did.

## Findings

1. **Reproduction.** On main `dc2d2d4`, `tests/unit/test_outlook_source_coverage.py` gives 8 passed
   on 5.58.0 and 1 failed, 7 passed on 5.61.1 (`pytest-5.58.0.txt`, `pytest-5.61.1.txt`). The
   failing test is the one CI failed on the Dependabot head
   ([job 115044568198](https://github.com/neilmac91/EarningsNerd/actions/runs/38319696913/job/115044568198):
   `1 failed, 7085 passed, 39 skipped`), with the same assertion:
   `'Adjusted EBIT (a)$8.5 - $10.5 billion' in block`.
2. **Regression 1 persists: no break between prose and a following table.** The three seams the
   5.59.1 evidence found glued are still glued (`probe_table_seams.txt`): in MD&A
   `…with the SEC.` runs straight into `2026 Guidance`, and in Item 1 both `(in millions):` seams
   run into their table headers. 5.58.0 separates each with a blank line.
3. **Regression 2 persists: characters are lost.** The MD&A ROIC row `ROIC (a)8.6%(12.5%)` still
   becomes `ROIC (a)  8.6  %  (12.5` (`roic-row.txt`); the per-section character comparison
   (`content_compare.txt`) shows Part I Item 2 losing `{')': 1, '%': 2}` and nothing gained, exactly
   the 5.59.1 figures. The cause is unchanged: `_AFFIX_CHARS` at
   `edgar/documents/renderers/fast_table.py:94` still lists single characters only, so a `%)` cell
   scores as spacing and its column is dropped. The only change to that file between 5.58.0 and
   5.61.1 is an `isalnum` content check for short cells (upstream `edgartools-wzgu`,
   `pkgdiff_documents_renderers_fast_table.py.diff`), which does not reach `%)`.
4. **Outlook block: nothing lost, representation changed** (`diff_outlook_block.txt`). As in 5.59.1,
   cells are separated by two spaces and the break before the table is gone; the block is 3,117
   characters against 3,118, `Ford Energy` is retained, and the row-preserving pattern from the
   5.59.1 README (`Adjusted EBIT \(a\)[ \t]*\$8\.5 - \$10\.5 billion`) matches on both versions.
5. **Other sections.** Items 3 and 4 and Part II Items 1 and 5 are byte-identical. Part II Item 2
   differs in whitespace only (5.60.0 collapses whitespace runs inside a text node, per its release
   notes). Item 1 keeps the same character multiset, nothing lost or gained, but not the same
   order, because its tables now render cell by cell through `render_table`; this is the 5.59.1
   figure too. Part II Item 6 loses its heading and signature block as it did at 5.59.1 (deliberate
   upstream; we do not use that section).
6. **What 5.60.0–5.61.1 change, and whether it reaches us.** None of the three release notes
   mentions the affix or seam behaviour. 5.61.1 is a security release: the MCP server's HTTP
   transport now binds `127.0.0.1` (we do not run that server) and six dependency floors rise
   (pyarrow 23.0.1, lxml 6.1.0, orjson 3.11.6, pydantic 2.4.0, jinja2 3.1.6, tqdm 4.66.3); our lock
   already pins past every one (pyarrow 24.0.0, lxml 6.1.3, orjson 3.11.9, pydantic 2.13.5, jinja2
   3.1.6, tqdm 4.68.2), so no advisory is closed by taking the bump. 5.61.0 fixes
   `Filing.homepage_url` / `Filing.html()` against SEC's new 403 on the short index URL; `app/`
   has no call to either (all SEC fetches go through `app/services/edgar/` and `app/utils/sec_urls.py`).

## Why no compatibility adaptation

Unchanged from the 5.59.1 record: no code in our extraction path reaches the failing assertion, so
there is nothing to adapt on our side, and re-gluing cells to match the old literal would restore
the `202626,550,000` corruption upstream fixed. Lost `%)` characters by themselves rule the upgrade
out under issue #1063 ("do not accept lost characters").

## What unblocks the upgrade

Issue #1063's acceptance list stands: a replay of this fixture at the proposed version with full
value, affix and boundary preservation; one new gate for the demonstrated affix and boundary loss
with a failing/restored mutation proof; the whitespace-compatible assertion only after that. The
first condition needs an upstream change to `fast_table.py`'s affix handling and to the seam between
prose and a rendered table; neither is in 5.61.1.

## Method

`dump_sections.py.txt` parses the retained fixture (`tests/fixtures/outlook/ford-2026q1.html.gz`,
SHA-256 `8f7a1ade…`) with `HTMLParser(ParserConfig(form="10-Q"))`, the same parser, config and
part-qualified selection the test and `_extract_sections_sync` use, and writes each section's
`text()`. It ran once in a Python 3.11.17 environment installed from main's `requirements.txt`
(edgartools 5.58.0) and once from #1285's (5.61.1). `compare_sections.py.txt` produced
`content_compare.txt`, the ROIC row and the Outlook block; the seam probe is reproduced in
`probe_table_seams.txt`.
