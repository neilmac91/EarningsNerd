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
   `1 failed, 7085 passed, 39 skipped`; those figures are from that job's log), with the same
   assertion, captured from the offline run in `pytest-5.61.1.txt`:
   `'Adjusted EBIT (a)$8.5 - $10.5 billion' in block`.
2. **Regression 1 persists: no break between prose and a following table.** The three seams the
   5.59.1 evidence found glued are still glued (`probe_table_seams.txt`): in MD&A
   `…with the SEC.` runs straight into `2026 Guidance`, and in Item 1 the first occurrence of each
   `(in millions):` seam runs into its table header (the second occurrence of each keeps its blank
   line, as the probe shows). 5.58.0 separates all three with a blank line.
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
   5.59.1 README (`Adjusted EBIT \(a\)[ \t]*\$8\.5 - \$10\.5 billion`) matches on both versions
   (`outlook_block.txt` records the lengths and the three checks).
5. **Other sections.** Items 3 and 4 and Part II Items 1 and 5 are byte-identical. Part II Item 2
   differs in whitespace only (5.60.0 collapses whitespace runs inside a text node, per its release
   notes). Item 1 keeps the same character multiset, nothing lost or gained, but not the same
   order, because its tables now render cell by cell through `render_table`; this is the 5.59.1
   figure too. Part II Item 6 loses about 280 non-whitespace characters and gains none; at 5.59.1
   that was its heading and signature block, which upstream drops deliberately, and we do not use
   that section.
6. **What 5.60.0–5.61.1 change, and whether it reaches us.** None of the three release notes
   mentions the affix or seam behaviour. 5.61.1 is a security release: the MCP server's HTTP
   transport now binds `127.0.0.1` (we do not run that server) and six dependency floors rise
   (pyarrow 23.0.1, lxml 6.1.0, orjson 3.11.6, pydantic 2.4.0, jinja2 3.1.6, tqdm 4.66.3); our lock
   already pins past every one (pyarrow 24.0.0, lxml 6.1.3, orjson 3.11.9, pydantic 2.13.5, jinja2
   3.1.6, tqdm 4.68.2), so no advisory is closed by taking the bump. 5.61.0 fixes
   `Filing.homepage_url` / `Filing.html()` against SEC's new 403 on the short index URL; `app/`
   has no call to either (all SEC fetches go through `app/services/edgar/` and `app/utils/sec_urls.py`).
   **Correction (2026-10-15):** `app/` reaches both indirectly. `xbrl_sections._extract_sections_sync`
   reads `obj["Item 1A"]` and `obj.sections`, and edgartools' report objects call `Filing.html()`, which
   reads an inline-XBRL document through the homepage. So the 403 broke every 10-K/10-Q/20-F section
   parse from about 2026-10-06, and the summary excerpt and the eval fell back to regex. The fix is
   backported without the upgrade, so this hold stands:
   [`../edgartools-homepage-403-2026-10-15/`](../edgartools-homepage-403-2026-10-15/README.md).

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

`dump_sections.py.txt` parses the retained fixture (`tests/fixtures/outlook/ford-2026q1.html.gz`;
SHA-256 of the decompressed HTML `8f7a1ade…`, the value the test asserts) with `HTMLParser(ParserConfig(form="10-Q"))`, the same parser, config and
part-qualified selection the test and `_extract_sections_sync` use, and writes each section's
`text()`. It ran once in a Python 3.11.17 environment installed from main's `requirements.txt`
(edgartools 5.58.0) and once from #1285's (5.61.1). `compare_sections.py.txt` reads the two dumps and writes `content_compare.txt`, `roic-row.txt`,
`probe_table_seams.txt` and `outlook_block.txt`; `diff_outlook_block.txt` is `diff` of the two Outlook
blocks it writes. Each seam probe matches the marker occurrence adjacent to its table header, since
`with the SEC.` also occurs earlier in MD&A (Codex's review of this record).

## Addendum, 2026-10-14: head rebased, 5.62.0 replayed

- Dependabot force-updated #1285's head from `b802f5cb` to `74de260b` (commit authored
  2026-10-13T17:12:47Z, after the 14:46Z hold comment); the proposal is still 5.61.1, and CI on the
  new head failed the same Outlook assertion
  ([job 115432918060](https://github.com/neilmac91/EarningsNerd/actions/runs/38436836156/job/115432918060):
  `1 failed, 7085 passed, 39 skipped`).
- edgartools 5.62.0 (PyPI 2026-10-11T18:22Z, the only release after 5.61.1; the CHANGELOG's
  Unreleased section is empty and 6.0 is announced for 2026-11-09) was replayed with the method
  above: a Python 3.11.17 environment from main's `requirements.txt` plus `requirements-dev.txt`
  with edgartools raised to 5.62.0 (`pip-check-5.62.0.txt`: interpreter, version and `pip check`),
  `dump_sections.py.txt` under 5.58.0 and 5.62.0 on main `d69bc69`, then `compare_sections.py.txt`. Evidence in [`5.62.0/`](5.62.0/):
  `pytest-5.62.0.txt` (1 failed, 7 passed, the same assertion; 8 passed on 5.58.0 at `dc2d2d4`,
  `../pytest-5.58.0.txt`, and again on `d69bc69` in this replay's 5.58.0 environment),
  `content_compare.txt` (Part I Item 2 loses `{')': 1, '%': 2}` and gains nothing; Item 1 keeps its
  character multiset; Part II Item 6 loses the heading and signature block as before),
  `roic-row.txt` (`ROIC (a)  8.6  %  (12.5`), `probe_table_seams.txt` (all three seams glued at their first occurrence; Item 1's second
  occurrences keep their blank line, as in 5.61.1),
  `outlook_block.txt` and `diff_outlook_block.txt` (3,117 against 3,118 characters; the row regex
  and `Ford Energy` retained). Every figure equals the 5.61.1 one. In 5.62.0 `fast_table.py`'s
  `_AFFIX_CHARS` is still single characters only; its release notes touch Markdown header paths and
  some equity-table column placement, nothing on affix handling or the prose/table seam.
- Decision unchanged: hold, no replacement PR, no Dependabot ignore. Next revisit: 6.0, replayed on
  this fixture per #1063's acceptance list. Recorded on #1285 in
  [comment 6177627038](https://github.com/neilmac91/EarningsNerd/pull/1285#issuecomment-6177627038).

## Addendum, 2026-10-15: finding 6 corrected (E28)

- Finding 6 says that 5.61.0's fix of `Filing.homepage_url` and `Filing.html()` does not reach
  `app/`, because `app/` calls neither of them. It does reach `app/`, indirectly. The summary's
  section source, `app/services/edgar/xbrl_sections.py::_extract_sections_sync`, calls
  `Filing.obj()`. The report object that `obj()` returns reads its sections through `html()`.
- On 5.58.0, `html()` re-reads any primary document that opens with an XML declaration (inline XBRL)
  from the filing's index page. 5.58.0 builds that page's URL without the accession folder, and SEC
  has answered that form with 403 since early October. So the source returns None for every filing
  in every measured run (CI's evaluation and a local reproduction), and each 10-K, 10-Q and 20-F
  excerpt built since then comes from the regex extractor; production runs the same pin, so it is
  inferred to match, pending the log count in the E28 record.
- Upstream fixed this by two routes. 5.61.0 moved the index URL inside the folder. 5.62.0 also stopped
  sending an XML-declared document that already contains HTML to the index page. Each route revives
  the source on its own, and the 5.62.0 route works even with the folderless URL. Under 5.61.0, 5.61.1
  and 5.62.0 the same app call returns all three sections live for AAPL's 10-K, and under 5.62.0 for
  NVDA's 10-Q too
  ([`../e28-native-sections-2026-10-15/revive_probe_output.txt`](../e28-native-sections-2026-10-15/revive_probe_output.txt),
  [`../e28-native-sections-2026-10-15/bump_5620_results.jsonl`](../e28-native-sections-2026-10-15/bump_5620_results.jsonl),
  [`../e28-native-sections-2026-10-15/upstream_fixes.txt`](../e28-native-sections-2026-10-15/upstream_fixes.txt)).
- So any bump to 5.61.0 or later also brings native sections back for every eligible excerpt built
  after it. Stored excerpts are reused, so the October cohort keeps its regex excerpts. This is a
  model-input change, and `backend/evals/RUNBOOK.md` requires it to be measured. A requirements-only
  PR does not trigger `eval-baseline` on its own, so the measurement is a dispatched run, priced
  under the spend rule. In CI's evaluation, summary citation fidelity was 0.97 with native sections
  (2026-10-03 and 2026-10-04). Without them it read 0.818 to 0.841 in the four retained reports
  (2026-10-07 to 2026-10-15), and decision 3 of `tasks/pr-disposition-2026-10-07.md` recorded 0.818 to
  0.871 across eight runs on 7 October
  ([`../e28-native-sections-2026-10-15/README.md`](../e28-native-sections-2026-10-15/README.md)).
- The hold decision itself is unchanged; it rests on the Ford affix and seam regressions. The next
  replay (6.0) must also land E28's decision first. Until it does,
  `backend/tests/unit/test_edgartools_sections_revival_tripwire.py` fails any edgartools other than
  5.58.0 while the section source holds its `obj()` allow-list entry.

## Addendum, 2026-10-16: E28 landed (#1350, then PR #1347)

- #1350 (merged and deployed 2026-10-16, 04:10Z) backported 5.61.0's in-folder index URL in
  `app/services/edgar/edgartools_compat.py`, which revived the `obj()` path on 5.58.0; the inline
  correction to finding 6 above is its record.
- PR #1347 then moved the summary's section source off `obj()`: it parses the primary document the
  pipeline fetched, so neither 5.61.x's index-URL fix nor 5.62.0's `html()` change reaches it, and
  the tripwire and the allow-list entry are deleted. The backport stays for the remaining `obj()`
  sites; its own test says when an upgrade makes it redundant.
- A bump can still change section text through the HTML parser itself.
  `backend/tests/unit/test_summary_sections_parity.py` now fails such a change in the free
  `backend-tests` job, and the regression gate's native-section share fails a collapse in
  `eval-baseline`.
- The hold decision is unchanged: the Ford affix and seam regressions (decision D, #1063) stand. Any
  replay must pass the parity test and a dispatched `eval-baseline`.
