# edgartools filing-index 403: why section extraction fell back to regex (2026-10-15)

From about 2026-10-06, `xbrl_sections._extract_sections_sync` returned nothing for every 10-K, 10-Q and
20-F, without logging anything. Two consumers were affected:
- **The summary excerpt** (`summary_generation_service.get_or_cache_excerpt`) and the **eval harness**
  (`backend/evals/runner.py::_get_grounding`) both fell back to the legacy regex extractor.
- **Every eval-baseline run from 2026-10-07** reports `source=regex_fallback` for 35 of 35 filings, and
  `mean_citation_fidelity` fell from the pinned 0.9648: 0.818–0.871 across the eight runs of 7 October
  (the sweep's decision 3). One example is job
  [116662675807](https://github.com/neilmac91/EarningsNerd/actions/runs/38804779839/job/116662675807)
  on 2026-10-15: 35/35 regex, 0.8258. On 2026-10-03, job 111114994018 had 31 `source=edgartools`.

This record gives the cause, the fix, and section extraction for the golden set before and after. It
used no AI calls and made SEC requests only, throttled to 2 req/s.

## Cause

1. **SEC refuses the short index URL.** SEC's edge answers
   `https://www.sec.gov/Archives/edgar/data/<cik>/<accession>-index.html` with 403 "Access Denied". The
   same page inside the accession folder (`…/data/<cik>/<accession, no dashes>/<accession>-index.html`)
   answers 200 ([`sec-responses.txt`](sec-responses.txt)). The block is by path, not by network: the same
   client gets 200 for the folder URL and the full submission. The 403 itself was captured from this
   container. PR #1286's container saw the same AttributeError on 2026-10-12. Every eval job since
   2026-10-07 shows the symptom (the runners logged nothing more, because the error was swallowed). Cloud
   Run very likely shares it; this record could not read it.
2. **The pinned edgartools builds the short URL.** edgartools 5.58.0 (the pin, held under issue #1063)
   builds it in `Filing.homepage_url` (`edgar/_filings.py:2273`).
3. **Every section read goes through it.** An inline-XBRL primary document starts with an XML prolog. On
   that branch, `Filing.html()` re-reads the document through `self.homepage` (`_filings.py:1604-1632`)
   instead of returning the copy in the full submission. The homepage of a 403 page lists no documents,
   so `primary_html_document` is None. `TenK.document` calls `Filing.html()` (`company_reports/ten_k.py:226`),
   and `TenK.__getitem__` and `.sections` go through it (`:274`, `:609`). Every read then raises
   `AttributeError: 'NoneType' object has no attribute 'download'`. The 10-Q and 20-F objects do the same.
4. **Our code hid the error.** The 10-K branch caught it per label, and the 10-Q/20-F branches read
   `getattr(obj, "sections", None)`, whose default swallows an AttributeError raised inside the property.
   Nothing was logged at any level.

Upstream fixed it in edgartools **5.61.0** (released 2026-10-06T18:49Z): `homepage_url` moved into the
accession folder, citing GH #1421 ([`upstream-edgartools.txt`](upstream-edgartools.txt)). The upgrade
stays held. 5.61.1 and 5.62.0 still drop characters on the Ford fixture
([`../edgartools-5.61.1-hold-2026-10-13/`](../edgartools-5.61.1-hold-2026-10-13/README.md)), so the fix is
backported instead.

## Fix

- **`backend/app/services/edgar/edgartools_compat.py`** backports upstream's `homepage_url`, applied when
  the edgar client module loads.
  - It probes the installed release first (building a `Filing` makes no request) and does nothing if the
    release already builds the in-folder URL. Taking the upgrade therefore leaves it inert.
  - `test_the_pinned_release_still_needs_the_backport` then fails, as the reminder to delete it. With
    edgartools 5.61.0 on the path, that test fails with its message and the other three pass.
- **`backend/app/services/edgar/xbrl_sections.py`** keeps the first read error and logs
  `Section parse found nothing for <accession> (<form>): <error>` as a warning when no section parses.
  - The 10-Q/20-F sections property is read in a `try`, so its error is kept.
  - The duplicated 10-Q/20-F reads become one helper. Parse results are unchanged. The tests pin each
    part key, the 20-F order Item 18, then Item 17, then Item 8, the 200-character minimum, and which
    error is logged. A differential run of the old and new function over 83,386 synthetic cases (the
    review's correctness lens) found one intended difference: a non-AttributeError raised by
    `obj.sections` is now caught and logged. Its caller already caught it and returned None.
  - The file stays within its 96-line size budget.

No new SEC transport and no new `sec.gov` literal: edgartools still makes the requests through its own
client and limiter, and only the URL it builds changes.

## Section extraction on the golden set, before and after

`golden_sections.py.txt` ran `_extract_sections_sync` on every golden filing that is not a 6-K (32 of 35)
at main `1062046e` and with the backport, sequentially, against live SEC. Raw lines:
[`sections-before-main-1062046e.jsonl`](sections-before-main-1062046e.jsonl) and
[`sections-after-backport.jsonl`](sections-after-backport.jsonl). Figures are characters per section.

**Before: 0 of 32 with any section. After: 31 of 32.** Neither run raised. ASML's 20-F parses to no
section on either side, as it did before the 403 (2026-10-03: 31 of 35 were edgartools, the other four
being the three 6-Ks and one more).

| Filing | Before | After |
| --- | --- | --- |
| PLD 10-K | none | risk 52,847, mda 67,507, financials 984 |
| NEE 10-Q | none | financials 130,616, mda 54,295, risk 1,196 |
| PGR 10-K | none | risk 72,573, mda 243, financials 251 |
| FIGS 10-Q | none | financials 44,455, mda 42,767, risk 210,468 |
| GPRO 10-K | none | risk 100,619, mda 97,278, financials 122,471 |
| AAPL 10-K | none | risk 68,163, mda 18,018, financials 60,874 |
| MSFT 10-K | none | risk 68,824, mda 49,534, financials 128,086 |
| NVDA 10-Q | none | financials 48,091, mda 28,905, risk 43,097 |
| JPM 10-K | none | risk 112,862, mda 414,433, financials 567,675 |
| KO 10-Q | none | financials 80,218, mda 58,473, risk 641 |
| TSLA 10-K | none | risk 83,678, mda 55,405, financials 171,280 |
| AMZN 10-K | none | risk 60,660, mda 46,296, financials 121,717 |
| BRK.B 10-K | none | risk 21,888, mda 127,344, financials 228,436 |
| XOM 10-K | none | risk 35,671, mda 130,464, financials 162,817 |
| PFE 10-Q | none | financials 170,651, mda 476, risk 388 |
| F 10-Q | none | financials 75,539, mda 87,806 |
| WMT 10-K | none | risk 93,314, mda 58,168, financials 108,237 |
| COST 10-Q | none | financials 33,718, mda 34,454, risk 383 |
| BA 10-K | none | risk 57,151, mda 89,675, financials 199,092 |
| INTC 10-Q | none | financials 58,238, risk 871 |
| PLTR 10-Q | none | financials 51,398, mda 41,640, risk 304,170 |
| RIVN 10-K | none | risk 6,645, mda 52,606, financials 137,955 |
| COIN 10-Q | none | financials 67,141, mda 40,039, risk 943 |
| BYND 10-Q | none | mda 44,884, risk 2,828 |
| BABA 20-F | none | risk 410,872, mda 139,430, financials 761 |
| ASML 20-F | none | none |
| TSM 20-F | none | risk 62,160, mda 37,151, financials 4,603 |
| JD 20-F | none | risk 361,721, mda 77,469, financials 200 |
| SE 20-F | none | risk 222,751, mda 93,170, financials 9,353 |
| NVO 20-F | none | risk 6,897, mda 22,484, financials 11,371 |
| PDD 20-F | none | risk 366,184, mda 51,093, financials 209 |
| MELI 10-K | none | risk 131,636, mda 98,636, financials 341 |

The excerpt still applies its own minimum (`_EDGARTOOLS_EXCERPT_MIN`) and falls back to regex below it.
The PR's eval-baseline run is the measurement of what the summaries gain.

## Tests and mutation proofs

`tests/unit/test_edgartools_compat.py` (4 tests) and `tests/unit/test_xbrl_sections_errors.py`
(10 tests) run offline. Each mutation below ran on the committed head in a separate worktree, serially
(`-n0`), and was restored with `git checkout`. Every one fails at least one test:

| Mutation | Result |
| --- | --- |
| M1: the backport is not applied (`client.py` call removed) | 3 failed, 11 passed |
| M2: `getattr(obj, "sections", None)` restored | 2 failed, 12 passed |
| M3: the 10-K branch drops the caught error | 1 failed, 13 passed |
| M4: the backport builds a wrong URL | 3 failed, 11 passed |
| M5: the 10-Q risk key mistyped (`part_i_item_1a`) | 1 failed, 13 passed |
| M6: the 20-F Item 18 and Item 17 order swapped | 1 failed, 13 passed |
| M7: the 20-F Item 8 fallback dropped | 1 failed, 13 passed |
| M8: the last read error logged instead of the first | 1 failed, 13 passed |
| M9: the part-keyed minimum off by one (`>` for `>=`) | 1 failed, 13 passed |
| M10: the warning also fires on a partial parse | 1 failed, 13 passed |
| Restored | 14 passed |

`test_the_pinned_release_still_needs_the_backport` fails with its "delete the backport" message when
edgartools 5.61.0 is first on the path; the other three backport tests pass there.

## Production impact and what remains

- **Probably affected since about 2026-10-06.** Production calls the same function: the summary
  pipeline's section extraction feeds `get_or_cache_excerpt`. Its log line `Excerpt provenance: {…}`
  carries `source`. This record had no access to production logs, so the production rate is
  unconfirmed; E28 in `tasks/todo.md` reads it after the deploy.
- **Cached excerpts outlive the fix.** `filing_content_cache.critical_excerpt` caches the excerpt per
  filing and is reused as `legacy_cached_excerpt`. A filing first excerpted between about 2026-10-06 and
  the deploy keeps its regex excerpt until that row is cleared. The `force` path in
  `precompute_service.py` clears it per filing.
- **Clearing those rows is a founder decision.** Whether to clear the rows written in that window and
  regenerate those summaries costs provider spend.
- **Corrected records.** This corrects four records that met the same failure:
  - finding 6 of the 5.61.1 hold record ("`app/` has no call to either");
  - the context of `lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md` ("in the
    build environment"), and the docstring of its gate `test_edgartools_obj_allowlist.py`;
  - E28's premise;
  - decision 3 of `tasks/pr-disposition-2026-10-07.md`, which put the silence in the eval runner.

  The new lesson is `lessons/sec-run-our-entry-point-before-ruling-an-upstream-fix-out.md`.
