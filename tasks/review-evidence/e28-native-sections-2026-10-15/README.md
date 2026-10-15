# E28: native summary sections have been dead since early October (2026-10-15)

Open item E28 asked for the production hit rate of the `USE_EDGARTOOLS_SECTIONS` summary-section
path (`backend/app/services/edgar/xbrl_sections.py::_extract_sections_sync`, edgartools
`Filing.obj()`). The answer is zero. Since early October every 10-K, 10-Q and 20-F summary excerpt
has come from the regex extractor, while the configuration says native sections are on. In CI's
summary evaluation, mean citation fidelity fell from 0.9737 to 0.84 when native sections stopped.
No paid run and no production access were used for this record.

## The cause

`_extract_sections_sync` resolves the filing and calls `obj()`. Inside it, edgartools loads the
filing's index page from `Filing.homepage_url`. edgartools 5.58.0, the pinned version, builds that
URL without the accession folder: `.../edgar/data/320193/0000320193-25-000079-index.html`. SEC
answers that form with 403, and serves the same page inside the folder (`.../data/320193/000032019325000079/0000320193-25-000079-index.html`)
with 200 ([`index_url_status.txt`](index_url_status.txt)). Without the index page the primary document
resolves to None, every section lookup fails with `'NoneType' object has no attribute 'download'`,
and the function returns None ([`probe_sections_output.txt`](probe_sections_output.txt), from
[`probe_sections.py.txt`](probe_sections.py.txt), run on main `1062046`). The pipeline then takes the
regex extractor, as designed for a missing section.

Upstream tracked the 403 as edgartools issue #1421, opened on 2026-10-05 ("currently persistent")
and fixed on 2026-10-06 by building the index URL inside the accession folder. The fix shipped in
5.61.0, so 5.61.1 and 5.62.0 carry it.

## When it stopped, and what it changed

CI's `eval-baseline` job runs the real summary pipeline over the 35-filing golden set (two runs each)
against live SEC, and its report records each excerpt's source. Three of those reports are still
downloadable ([`eval_excerpt_sources.txt`](eval_excerpt_sources.txt)):

| run | when | native-section excerpts (10-K, 10-Q, 20-F) | citation fidelity | mean prompt tokens |
|---|---|---|---|---|
| 37152414706 | 2026-10-03 20:51Z | 62 of 64 | 0.9737 | 39,365 |
| 37700182145 | 2026-10-07 23:14Z | 0 of 64 | 0.8413 | 56,785 |
| 37978755392 | 2026-10-09 19:24Z | 0 of 64 | 0.8350 | 56,785 |

In the two later runs every eligible filing reports `supplied_sections: []`. Every primary document
was still fetched live from `www.sec.gov` and XBRL grounding was present, so the runs had SEC access.
The two native-section misses on October 3 are ASML's 20-F (both runs), which yields no sections in the
local parse below either. The pinned baseline (2026-09-19, flag on) has citation fidelity 0.9648 and mean
prompt tokens 39,368, which matches the native-section state.

No other change between October 3 and October 7 touched the summary prompt or excerpt. The summary-path
commits in that window are #1111 (Copilot only), the security hardening `c39bb92` (metering at
provider start) and #1122 (thread ownership for background work). The excerpt switch is the one
change that lines up with the drop. Citation fidelity is a WARN dimension in
`backend/evals/regression_gate.py` (tolerance 0.05), so every run since has printed a warning and
passed. The refactor closeout recorded 0.81 to 0.86 as a retained advisory without naming a cause.

The other dimensions held. Numeric accuracy, coverage and currency consistency stayed at 1.0 and
financial depth at about 0.78. Untraceable dollar figures were 2.1 on October 3 and 1.5 and 1.33 after, and mean latency rose by
about 0.6 s with the larger prompts.

## What the dead path still costs production

Each eligible summary generation that misses the content cache still makes the attempt. It resolves the
filing, downloads the filing's whole submission file, then requests the refused index page. All of these go through edgartools' own HTTP client: paced by `EDGAR_RATE_LIMIT_PER_SEC`, but
outside the app's limiter, breaker and diagnostics (`lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md`).
The submission file is large: 59 MB for Prologis's 10-K. Measured on main with edgartools 5.58.0
([`dead_path_results.jsonl`](dead_path_results.jsonl), from [`dead_path_one.py.txt`](dead_path_one.py.txt)):

| filing | result | time | peak process memory (after imports: about 164 MB) |
|---|---|---|---|
| AAPL 10-K | None | 1.14 s | 221 MB |
| PLD 10-K | None | 1.85 s | 325 MB |
| JPM 10-K | None | 2.31 s | 344 MB |
| NVDA 10-Q | None | 1.21 s | 195 MB |
| BABA 20-F | None | 1.72 s | 295 MB |

## The held edgartools bump would revive the path silently

The hold record for #1285 says in finding 6 that 5.61.0's `Filing.homepage_url` fix does not reach `app/`.
It does: `xbrl_sections.py` calls `Filing.obj()`, and `obj()` reaches the index page through
`homepage_url`. With edgartools 5.62.0 first on the import path, the same app call returns all three
sections live for AAPL's 10-K and NVDA's 10-Q ([`bump_5620_results.jsonl`](bump_5620_results.jsonl)).
Taking the bump would therefore switch every eligible excerpt back to native sections inside a
dependency change. The hold record carries an addendum
([`../edgartools-5.61.1-hold-2026-10-13/README.md`](../edgartools-5.61.1-hold-2026-10-13/README.md#addendum-2026-10-15-finding-6-corrected-e28)),
and the tripwire `backend/tests/unit/test_edgartools_sections_revival_tripwire.py` now fails such a
bump until E28's decision has landed.

## Reviving native sections without edgartools' HTTP client, measured offline

The pipeline already downloads the primary document's HTML through the app's SEC transport
(`summary_stages/fetch.py`, `run.filing_text`). E28 proposed parsing sections from that HTML with
edgartools' `HTMLParser`, the way `filing_section_service.parse_item_1a` parses Item 1A. That makes no
SEC request of its own. [`fetch_docs.py.txt`](fetch_docs.py.txt) fetched the 32 eligible golden-set
primary documents once at about 1 request per second. [`parse_one.py.txt`](parse_one.py.txt) parsed each in its own process
with the same section keys the dead path uses, then built the excerpt with the app's
`assemble_excerpt_from_sections` ([`parse_results.jsonl`](parse_results.jsonl)):

- Sections for the summary were found in 31 of 32 filings, and all 31 excerpts clear the 8,000-character
  floor. ASML's 20-F (24.9 MB) yields none and would keep the regex excerpt.
- Parse time: median about 1 s; JPMorgan's 10-K 5.7 s; ASML's 20-F 10.9 s.
- Peak process memory, with Python and the app imported (about 210 MB): 220 to 410 MB for most
  filings, 503 MB for JPMorgan and 713 MB for ASML. The API service has 1 GiB.

Against the dead path's cost on the same filings, the local parse is cheaper for typical filings and
dearer for the largest. It makes no SEC request at all.

## The decision (founder, E28 in `tasks/todo.md`)

1. **Revive from the fetched HTML (recommended).** Parse the sections in the pipeline from
   `run.filing_text`, mirror it in `evals/runner.py` and `evals/copilot_bootstrap.py`, adapt the
   acceptance harness (sections come from the bound primary document, not from a source call), retire
   `obj()` and its allow-list entry, and delete the tripwire with it. This restores the state the
   baseline was pinned in. The PR needs paid `eval-baseline` runs (about USD 0.30 each) to show
   citation fidelity back near 0.97, and a `copilot-eval` draw when it is marked ready. Its merge changes model
   inputs and deploys the backend.
2. **Retire the path.** Remove the dead attempt and its requests, keep the regex excerpt and today's
   scores, and delete the tripwire. Also a model-input decision, since it fixes today's lower citation
   fidelity in place.
3. **Take an edgartools bump once #1063 clears.** This revives `obj()` with its edgartools HTTP
   (the whole submission file and the index page per summary) and stays outside the app's limiter.
   The tripwire blocks it until the code no longer calls `obj()` for sections.

Production confirmation is one log query. The API logs `Excerpt provenance: {...}` with a `source`
field for every excerpt it builds. Counting `edgartools` against `regex_fallback` by day since
2026-10-01 would show the switch in production. The CODE RED chief's `logs-probe` route can read it;
this record did not, since it has no production access.

## Files

- [`probe_sections.py.txt`](probe_sections.py.txt), [`probe_sections_output.txt`](probe_sections_output.txt):
  the local reproduction on main with edgartools 5.58.0.
- [`index_url_status.txt`](index_url_status.txt): the two index URL forms and SEC's answers.
- [`eval_excerpt_sources.txt`](eval_excerpt_sources.txt): excerpt sources and scores per CI run, read
  from the runs' `eval-report-*` artifacts (kept 14 days).
- [`dead_path_one.py.txt`](dead_path_one.py.txt), [`dead_path_results.jsonl`](dead_path_results.jsonl),
  [`bump_5620_results.jsonl`](bump_5620_results.jsonl): the app's section call on 5.58.0 and on 5.62.0.
- [`fetch_docs.py.txt`](fetch_docs.py.txt), [`parse_one.py.txt`](parse_one.py.txt),
  [`parse_results.jsonl`](parse_results.jsonl): the offline revival measurement.
