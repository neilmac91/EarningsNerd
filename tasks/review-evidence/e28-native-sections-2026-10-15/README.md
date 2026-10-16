# E28: native summary sections have been dead since early October (2026-10-15)

Open item E28 asked for the production hit rate of the `USE_EDGARTOOLS_SECTIONS` summary-section
path (`backend/app/services/edgar/xbrl_sections.py::_extract_sections_sync`, edgartools
`Filing.obj()`). Since early October the path has returned nothing in every measured run: CI's
summary evaluation against live SEC and a local reproduction. Production runs the same pinned
edgartools against the same SEC URL, so its rate is inferred to be zero too. Each 10-K, 10-Q and 20-F
excerpt built there since then would come from the regex extractor, while the configuration says
native sections are on. The `Excerpt provenance` log count at the end of this record would confirm it;
it has not been run.

CI's evaluation builds its excerpts fresh on every run. There, mean citation fidelity fell from 0.97
to between 0.818 and 0.871 when native sections stopped: the four retained post-switch reports read
0.818 to 0.841, and decision 3 of `tasks/pr-disposition-2026-10-07.md` recorded 0.818 to 0.871 across
eight runs on 7 October. No paid run and no production access were used for this record.

## The cause

`_extract_sections_sync` resolves the filing, calls `obj()` and looks up each section on the report
object it returns (`TenK`, `TenQ`, `TwentyF`). Those lookups read the primary document through
`Filing.html()`. On edgartools 5.58.0, the pinned version, `html()` sends any primary document that
starts with an XML declaration to the filing's index page instead (`edgar/_filings.py`,
`if html.startswith("<?xml"):` then `self.homepage.primary_html_document.download()`). All 32 of the
golden set's 10-K, 10-Q and 20-F primary documents start that way, as inline XBRL commonly does
([`xml_declaration_check.txt`](xml_declaration_check.txt), from
[`xml_declaration_check.py.txt`](xml_declaration_check.py.txt)).

5.58.0 builds the index URL without the accession folder:
`.../edgar/data/320193/0000320193-25-000079-index.html`. SEC answers that form with 403. It serves
the same page inside the folder (`.../data/320193/000032019325000079/0000320193-25-000079-index.html`)
with 200 ([`index_url_status.txt`](index_url_status.txt)). Without the index page the primary
document resolves to None, and every section lookup fails with
`'NoneType' object has no attribute 'download'`. The function then returns None
([`probe_sections_output.txt`](probe_sections_output.txt), from
[`probe_sections.py.txt`](probe_sections.py.txt), run on main `1062046`). The pipeline falls back to
the regex extractor, as it is designed to when a section is missing.

Upstream fixed it twice; 5.62.0's source cites the issue as GH #1421 (dgunning/edgartools#1421)
([`upstream_fixes.txt`](upstream_fixes.txt), read from the published wheels):

- 5.61.0 (on PyPI 2026-10-06) builds the index URL inside the accession folder.
- 5.62.0 (2026-10-11) treats an XML-declared primary document that contains HTML as the HTML
  itself, so the section lookups no longer load the index page.

Either fix alone revives the path, measured with the app's own section call on AAPL's 10-K
([`revive_probe_output.txt`](revive_probe_output.txt), from [`revive_probe.py.txt`](revive_probe.py.txt)):

- Under 5.61.0 and 5.61.1 as shipped, the call returns all three sections. It requests the
  submissions file, the submission file, the foldered index page (200) and the primary document again.
- Under 5.62.0 with the folderless 5.58.0 URL patched back in, it returns the same three sections and
  makes only the submissions and submission-file requests, with no index-page request.

## When it stopped, and what it changed

CI's `eval-baseline` job grounds each golden filing the way the product does. `evals/runner.py::_get_grounding`
fetches the primary document through the app's SEC service, makes the same sections call, and builds
the excerpt with the same assembly or regex fallback; the runner then passes that grounding to
`summarize_filing`. Its report records each excerpt's source. [`eval_excerpt_sources.txt`](eval_excerpt_sources.txt), from
[`eval_excerpt_sources.py.txt`](eval_excerpt_sources.py.txt), reads six of those reports (each run
covers 35 filings twice):

| run | report time | native-section excerpts (10-K, 10-Q, 20-F) | citation fidelity | mean prompt tokens |
|---|---|---|---|---|
| 37152414706 | 2026-10-03 20:51Z | 62 of 64 | 0.9737 | 39,365 |
| 37191767215 | 2026-10-04 09:29Z | 62 of 64 | 0.9717 | 39,365 |
| 37670654728 | 2026-10-07 19:06Z | 0 of 64 | 0.8182 | 56,785 |
| 37700182145 | 2026-10-07 23:14Z | 0 of 64 | 0.8413 | 56,785 |
| 37978755392 | 2026-10-09 19:24Z | 0 of 64 | 0.8350 | 56,785 |
| 38804779839 | 2026-10-15 20:57Z | 0 of 64 | 0.8258 | 56,785 |

The switch falls between October 4 09:29Z and October 7 19:06Z. Every run since October 7 reports
`supplied_sections: []` for every eligible filing. Every primary document was still fetched live from
`www.sec.gov` and XBRL grounding was present, so those runs had SEC access. The two native-section
misses before the switch are ASML's 20-F (both runs). The local parse below finds no sections in that
document either. The pinned baseline (2026-09-19, flag on) has citation fidelity 0.9648 and mean
prompt tokens 39,368, which matches the native-section state. The 6-K excerpts are byte-identical in
all six reports, which confirms that the switch did not touch the 6-K path.

The other dimensions held. Numeric accuracy stayed at 1.0 in all six reports. Currency consistency
read 0.9998 to 1.0 and coverage 0.9971 to 1.0. Financial depth stayed between 0.77 and 0.80.
Untraceable dollar figures read 2.1 and 2.14 before the switch and 1.13 to 1.5 after it. Mean latency
read 12.8 and 13.4 s before and 13.4 to 15.0 s after (pinned baseline 13.19 s).

Citation fidelity is a WARN dimension in `backend/evals/regression_gate.py` (tolerance 0.05), so
every run since the switch has printed a warning and passed.

The drop was seen on 7 October. Decision 3 of `tasks/pr-disposition-2026-10-07.md` records the
35-of-35 regex fallback against 31 of 35 native on 2 to 4 October, and fidelity at 0.818 to 0.871
across 8 runs. It also records that `_get_grounding` swallows the exception, and calls the drop
"worth a diagnosis PR". `tasks/review-evidence/deps-minor-2026-10-07/README.md` queued it as a
follow-up. It never became an open item, so the edgartools hold review of 13 October did not connect
it to the bump.

## Which production excerpts this reached

A built excerpt is stored and reused, so the switch reached only the excerpts first built after it:

- `summary_generation_service.get_or_cache_excerpt` returns any stored `critical_excerpt` before
  building one, logging it as `legacy_cached_excerpt`.
- `content_cache.py` never overwrites a stored excerpt.
- Only precompute's `force` path (`precompute_service.py`) and the admin filing reset
  (`admin_filing_service.py`) clear one.

So in production, by the code above and the CI measurement (the log count below would confirm it):

- Excerpts stored before the switch are still native.
- Excerpts first built since early October are regex and stay regex.
- Copilot grounds on the stored excerpt as well (`copilot/prompt.py::_select_source_text`).
- A revival by any route reaches only filings that have no stored excerpt yet.
- Restoring the October cohort means clearing its excerpts and regenerating its summaries, one paid
  model call per filing.

The eval builds every excerpt fresh, so it shows the full switch and the full revival. It does not
show production's mix.

## What the dead path still costs production

The pipeline starts the sections task whenever the cache is not fresh: either no stored excerpt
exists, or the stored one is more than 24 hours old (`summary_stages/admission.py`,
`summary_stages/enrichment.py`). In the second case the stored excerpt is reused anyway. Each such
attempt resolves the filing, downloads the filing's whole submission file, and then requests the
refused index page. All of these requests go through edgartools' own HTTP client. That client is
paced by `EDGAR_RATE_LIMIT_PER_SEC`, but the app's limiter, breaker and diagnostics do not see it
(`lessons/sec-parse-app-fetched-html-not-edgartools-filing-objects.md`).

The submission files run from 7.5 MB (NVDA's 10-Q) to 65 MB (JPM's 10-K); see
[`submission_sizes.txt`](submission_sizes.txt). The measurements below were taken on main with
edgartools 5.58.0 ([`dead_path_results.jsonl`](dead_path_results.jsonl), from
[`dead_path_one.py.txt`](dead_path_one.py.txt)):

| filing | submission file | result | time | peak process memory (after imports: about 164 MB) |
|---|---|---|---|---|
| AAPL 10-K | 9.4 MB | None | 1.14 s | 221 MB |
| PLD 10-K | 59.1 MB | None | 1.85 s | 325 MB |
| JPM 10-K | 64.9 MB | None | 2.31 s | 344 MB |
| NVDA 10-Q | 7.5 MB | None | 1.21 s | 195 MB |
| BABA 20-F | 50.2 MB | None | 1.72 s | 295 MB |

## The held edgartools bump would revive the path silently

Finding 6 of the hold record for #1285 says that 5.61.0's `Filing.homepage_url` fix does not reach
`app/`. It does: the section source reaches the index page through `obj()` and `html()`. Under
5.61.0 and 5.61.1 the app's call returns all three sections for AAPL's 10-K. 5.62.0 adds a second
route: its `html()` no longer sends inline XBRL to the index page, so it revives the path even without
the URL fix ([`revive_probe_output.txt`](revive_probe_output.txt)). With 5.62.0 first on the import
path, the same app call returns all three sections live for AAPL's 10-K and NVDA's 10-Q
([`bump_5620_results.jsonl`](bump_5620_results.jsonl)). Taking any of these versions would switch
every newly built eligible excerpt back to native sections inside a dependency change.

The hold record now carries an addendum
([`../edgartools-5.61.1-hold-2026-10-13/README.md`](../edgartools-5.61.1-hold-2026-10-13/README.md#addendum-2026-10-15-finding-6-corrected-e28)).
While this record was a records-only PR, its branch carried a tripwire,
`backend/tests/unit/test_edgartools_sections_revival_tripwire.py`, keyed on the installed edgartools
version rather than one URL or code path. It held the version at 5.58.0, the version measured dead,
for as long as `test_edgartools_obj_allowlist.py` carried the section source's `obj()` entry. The
tripwire never reached main: the same PR moved the source off `obj()` and deleted it (see "Outcome").

## Reviving native sections without edgartools' HTTP client, measured offline

The pipeline already downloads the primary document's HTML through the app's SEC transport
(`summary_stages/fetch.py`, `run.filing_text`). E28 proposed parsing sections from that HTML with
edgartools' `HTMLParser`, the way `filing_section_service.parse_item_1a` parses Item 1A. That parse
makes no SEC request of its own.

[`fetch_docs.py.txt`](fetch_docs.py.txt) fetched the 32 eligible golden-set primary documents once,
at about 1 request per second. [`parse_one.py.txt`](parse_one.py.txt) parsed each in its own process
with the same section keys the dead path uses. It then built the excerpt with the app's
`assemble_excerpt_from_sections` ([`parse_results.jsonl`](parse_results.jsonl)):

- Sections for the summary were found in 31 of 32 filings, and all 31 excerpts clear the
  8,000-character floor. ASML's 20-F (24.9 MB) yields none and would keep the regex excerpt.
- Parse time: median 1.1 s; JPMorgan's 10-K 5.7 s; ASML's 20-F 10.9 s.
- Peak process memory, Python and the app included: 205 to 411 MB for 29 of
  32 filings, 443 MB for TSMC's 20-F, 503 MB for JPMorgan's 10-K and 713 MB for ASML's 20-F.

The streaming path runs on the API service: 1 GiB, shared by up to 40 concurrent requests. Durable
background work, when enabled, runs on the task worker: 2 GiB, one request at a time. A revival
should therefore bound or skip the largest documents on the API service, for example by size, or by
leaving the 20-F to the worker. This measurement shows that the parse is feasible. It does not show
that the parse is cheaper than the dead attempt.

## The decision (founder, E28 in `tasks/todo.md`)

1. **Revive from the fetched HTML (recommended).** The work in the PR:
   - Parse the sections in the pipeline from `run.filing_text`, and bound the largest documents.
   - Mirror the parse in `evals/runner.py` and `evals/copilot_bootstrap.py`.
   - Adapt the acceptance harness, since sections will come from the bound primary document and not
     from a source call.
   - Retire `obj()` and its allow-list entry, and delete the tripwire.
   - Gate the native-section share in `evals/regression_gate.py`, and correct
     `backend/evals/RUNBOOK.md` and the `config.py` comment.

   This restores the state the baseline was pinned in, for every excerpt built afterwards. The
   October cohort needs a separate clear-and-regenerate, sized from the log count below.

   The PR touches `backend/app/` and `backend/evals/`, so each push runs the paid `eval-baseline`
   job. The plan's spend rule reserves USD 0.73 per push (`tasks/refactor-plan-2026-10.md`). Measured
   runs cost USD 0.175 off-peak (runs D1 and D3 of `tasks/pr-disposition-2026-10-07.md`) to 0.36
   (record 18, quoted in the refactor plan). It also needs a `copilot-eval` draw when it is marked
   ready (reserve USD 0.06). Read the balance
   with the `.github/workflows/deepseek-balance.yml` dispatch first. The last recorded balance is
   USD 7.36 (2026-10-14 12:55Z) against the USD 5 floor. The merge changes model inputs and deploys
   the backend.
2. **Retire the path.** Remove the dead attempt and its requests, keep the regex excerpt and today's
   scores, and delete the tripwire. This is also a model-input decision, since it fixes today's lower
   citation fidelity in place.
An edgartools bump is not a third option. It would revive `obj()` with its edgartools HTTP (the
whole submission file per attempt, plus the index page and the primary document again on 5.61.x),
outside the app's limiter, so it is a revival without the measurement. The tripwire blocks any bump
until the allow-list entry is gone, so the bump follows whichever decision lands.

Production confirmation is one log query. `get_or_cache_excerpt` logs `Excerpt provenance: {...}`,
with a `source` and the `accession`, for every excerpt it builds and for every stored excerpt it
reuses after the 24-hour freshness window. A reuse inside that window skips the function and logs
nothing. A daily count since 2026-10-01 shows the switch and sizes the October cohort:

- `edgartools` against `regex_fallback` shows the switch.
- The cohort is the distinct accessions logged as `regex_fallback` since 2026-10-04, joined to
  `Filing.filing_type` to keep 10-K, 10-Q and 20-F. It also counts filings that fall back with
  native sections on (ASML's 20-F did before the switch); those keep a regex excerpt either way.
- `legacy_cached_excerpt` counts only the stale-cache reuses, so it is a lower bound on reuse.

The CODE RED chief's `logs-probe` route can read these logs. This record did not, because it has no
production access.

## Outcome (2026-10-16, #1350 and PR #1347)

First, #1350 (merged and deployed 2026-10-16, 04:10Z, from another session) backported 5.61.0's
in-folder index URL in `app/services/edgar/edgartools_compat.py`. That revived the `obj()` path on
5.58.0; its record is
[`../edgartools-homepage-403-2026-10-15/`](../edgartools-homepage-403-2026-10-15/README.md). Each
summary generation then reads its sections through edgartools' own client again, outside the app's
limiter and breaker. As measured under 5.61.x, whose URL the backport copies, that means the
submissions file, the whole submission file (7.5 to 65 MB), the foldered index page and the primary
document a second time ([`revive_probe_output.txt`](revive_probe_output.txt)). The founder chose
option 1, and PR #1347 moves the source off `obj()`. What it lands:

- **The section source.** `backend/app/services/edgar/xbrl_sections.py::_sections_from_html` parses
  the primary document the pipeline fetched: `HTMLParser(ParserConfig(form=base_form)).parse(html)`,
  the old section keys, and for a 10-K the lookup order of `TenK.__getitem__` (canonical part key,
  combined-items heading, "Item X" key, friendly name, then the Cross Reference Index). It makes no
  SEC request and calls no `obj()`. Documents over 16,000,000 characters are not parsed.
- **The seam.** `xbrl_service.get_filing_sections(accession, filing_type, *, html)`. The pipeline
  starts the parse once the document is fetched (`summary_stages/enrichment.py::start_section_parse`,
  request-owned) and awaits it before building the excerpt, as before E28, under the seam's own
  30 s bound (40 s for a 20-F; a parse that runs out returns None and the regex excerpt is built);
  the excerpt build and XBRL then share the usual fresh 18 s join. Before, the parse started with
  the fetch, so the same bound ran from the fetch's start. The eval runner, the Copilot bootstrap and the acceptance harness pass the same fetched HTML.
- **Parity.** The 31 native golden excerpts built through the revived seam match the pre-switch CI
  reports by sha256 and by each section's supplied length; ASML's 20-F has no sections, as before
  ([`revival_parity.txt`](revival_parity.txt), from [`seam_parity_one.py.txt`](seam_parity_one.py.txt)
  and [`revival_parity_compare.py.txt`](revival_parity_compare.py.txt);
  [`seam_parity_results.jsonl`](seam_parity_results.jsonl)). All 32 golden documents are inline XBRL
  that opens with an XML declaration, so a primary without one is not measured. The sections and
  excerpts for all six Copilot sources, two of them outside the golden set, match #1350's
  `copilot-eval` run of the backported `obj()` path byte for byte ([`copilot_sources_parity.txt`](copilot_sources_parity.txt), from
  [`compare_copilot_sources.py.txt`](compare_copilot_sources.py.txt)).
  `backend/tests/unit/test_summary_sections_parity.py` pins three golden filings in CI (FIGS's 10-Q,
  MercadoLibre's 10-K and Sea's 20-F) from fixtures already in the repository.
- **Size cap.** Documents over 16,000,000 characters are not parsed, an input change against the
  `obj()` path, which parsed any size within 30 s (40 s for a 20-F). The only golden document over
  the cap, ASML's, has no sections either way; production's others log `Section parse skipped`.
- **The gate.** `backend/evals/regression_gate.py` checks the native-section share: HARD below
  0.90, WARN below 0.95, absolute, from `results`. No re-pin.
- **Retired.** The tripwire and the `obj()` allow-list entry are deleted, and so is #1350's
  `test_xbrl_sections_errors.py`, which tested the deleted `obj()` reader; its rule, a warning when a
  read error leaves no section, moved into the seam (the parser re-raises the read error and the
  service logs it with the accession) and its X0.2 cases. E25 closes in the same PR.
- **Runtime.** Parses run one at a time on their own worker, off the four-thread SEC pool, and a
  filing with a stored excerpt is not parsed at all (`get_or_cache_excerpt` would return the stored
  one). Measured on one pinned CPU in [`runtime_limits.md`](runtime_limits.md).
- **Cost.** The `obj()` requests are gone: before #1350 the whole-submission download and the
  refused index-page request, and with its backport the index page and a second primary-document
  fetch as well.
  The parse itself took 0.4 to 6.4 s per document, peaking at 196 to 415 MB of process memory with
  the app imported (about 182 to 205 MB before the parse); ASML's 24.9 MB 20-F is skipped by the cap
  ([`seam_parity_results.jsonl`](seam_parity_results.jsonl)).
- **Remaining** (E28 in `tasks/todo.md`): confirm the source in production from the `Excerpt
  provenance` logs, and size and regenerate the October cohort (excerpts first built between
  2026-10-04 09:29Z, CI's last native report, and #1350's deploy) on the founder's go.

The PR's own `eval-baseline` run is recorded in the PR body: every push to the PR starts a paid
run, so recording it here would start another.

## Files

- [`probe_sections.py.txt`](probe_sections.py.txt), [`probe_sections_output.txt`](probe_sections_output.txt):
  the local reproduction on main with edgartools 5.58.0.
- [`index_url_status.txt`](index_url_status.txt): the two index URL forms and SEC's answers.
- [`upstream_fixes.txt`](upstream_fixes.txt): the index URL and the `html()` branch in 5.58.0,
  5.61.0, 5.61.1 and 5.62.0, with PyPI upload times.
- [`revive_probe.py.txt`](revive_probe.py.txt), [`revive_probe_output.txt`](revive_probe_output.txt):
  5.61.0 and 5.61.1 revive the path through the foldered index page; 5.62.0 revives it even with
  5.58.0's folderless index URL.
- [`xml_declaration_check.py.txt`](xml_declaration_check.py.txt), [`xml_declaration_check.txt`](xml_declaration_check.txt):
  all 32 golden 10-K, 10-Q and 20-F primary documents open with an XML declaration.
- [`eval_excerpt_sources.py.txt`](eval_excerpt_sources.py.txt), [`eval_excerpt_sources.txt`](eval_excerpt_sources.txt):
  excerpt sources, scores and 6-K excerpt hashes per CI run, read from the runs' `eval-report-*`
  artifacts (kept 14 days).
- [`submission_sizes.txt`](submission_sizes.txt): the submission-file sizes of the five measured
  filings.
- [`dead_path_one.py.txt`](dead_path_one.py.txt), [`dead_path_results.jsonl`](dead_path_results.jsonl),
  [`bump_5620_results.jsonl`](bump_5620_results.jsonl): the app's section call on 5.58.0 and on 5.62.0.
- [`fetch_docs.py.txt`](fetch_docs.py.txt), [`parse_one.py.txt`](parse_one.py.txt),
  [`parse_results.jsonl`](parse_results.jsonl): the offline revival measurement.
- [`seam_parity_one.py.txt`](seam_parity_one.py.txt), [`seam_parity_results.jsonl`](seam_parity_results.jsonl),
  [`revival_parity_compare.py.txt`](revival_parity_compare.py.txt), [`revival_parity.txt`](revival_parity.txt):
  the revived seam's excerpts against the pre-switch reports, filing by filing.
- [`runtime_limits.md`](runtime_limits.md), [`burst_through_seam.py.txt`](burst_through_seam.py.txt),
  [`burst_results.jsonl`](burst_results.jsonl): the parse's time, memory and SEC-pool effect under a
  burst, single worker against the shared pool; [`excerpt_build_times.py.txt`](excerpt_build_times.py.txt),
  [`excerpt_build_times.jsonl`](excerpt_build_times.jsonl): the excerpt build that follows a parse.
- [`burst_end_to_end.py.txt`](burst_end_to_end.py.txt), [`burst_end_to_end.jsonl`](burst_end_to_end.jsonl):
  whole summary generations several at once on one CPU, this PR's design against the superseded
  bounded-wait designs; [`burst_up_to_six.py.txt`](burst_up_to_six.py.txt),
  [`burst_up_to_six.jsonl`](burst_up_to_six.jsonl): the final review's independent harness, up to
  six at once, with origin/main's scheduling emulated.
- [`compare_copilot_sources.py.txt`](compare_copilot_sources.py.txt),
  [`copilot_sources_parity.txt`](copilot_sources_parity.txt): the seam's sections for the six Copilot
  sources against #1350's `copilot-eval` run 38817393205 (its retained artifact, read offline).
- [`mutate.py.txt`](mutate.py.txt), [`mutation_proofs.jsonl`](mutation_proofs.jsonl): the mutation
  proofs on 5814f9b (49 of 49 killed), each mutant applied to the committed tree in a detached worktree.
