# A forced refresh never deletes or clears what the stored summary is served with, and stores its own excerpt only with the summary it writes

Date: 2026-10-22, revised 2026-10-24 · Area: arch / summary pipeline

**Context.** Two forced refreshes cleared stored state before the one orchestrator had admitted or
finished the run. The Pro "Regenerate" route wrote `Filing.xbrl_data = None` and committed before
admission, so that the run would re-fetch XBRL. A run the fair-use ceiling refused, or one whose SEC
document fetch failed (release cancels the XBRL task before it persists), left the filing with no
snapshot while its stored summary was still served, and that summary lost the source verification
`GET /api/summaries/filing/{id}` derives from the snapshot. The operator's forced precompute
(`scripts/pregenerate_examples.py --force`) DELETEd the summary row before generating: a provider
error left the filing with no summary, an AI-timeout fallback replaced a full summary under a new id,
and a bookmarked summary was orphaned (SQLite) or the DELETE raised on `saved_summaries`' foreign key
(PostgreSQL). Findings 6 and 7 of the 2026-10-15 backend bug hunt, fixed in P11 (#1545). P11 then
cleared the cached `critical_excerpt` before a forced precompute so the current extraction ran, and
put it back in a `finally` when the summary stayed. Two forced precomputes of one filing that overlapped
broke that: the second captured the first run's new excerpt as "stored", and after keep-better kept the
summary it wrote the rejected run's excerpt back beside it (Codex 4365089688 on #1545, reproduced in
one process and across two). Any forced run also stored an excerpt it built for a summary that had
none, before keep-better decided.

**Rule.** A forced refresh never deletes the stored summary and clears nothing it is served with. It
regenerates in place through the one orchestrator (`force_regenerate=True`, where keep-better decides),
so the summary row changes only through finalize's keep-better UPDATE. A forced run keeps the excerpt
it builds to itself (`get_or_cache_excerpt(..., persist=False)`); finalize stores it in the same commit
as the summary it writes (`upsert_content_cache(..., replace_excerpt=True)`), and a run keep-better
keeps, or one that fails, raises or is cancelled, stores none. To rebuild with the current extraction,
ask the run (`rebuild_excerpt=True`, which only a forced precompute sets); never clear the stored
excerpt first. The XBRL snapshot is replaced only by fresh XBRL (`refresh_xbrl`, which only the Pro
route sets; the drains read the snapshot), and as soon as it arrives, even when the run then fails or
keep-better keeps the stored summary, since it is the same filing's data. Report a refresh's outcome
from what the run did (replaced, kept or failed), never from whether a row exists afterwards.

**Limits, stated.** The progress row is still deleted before admission: no reader shows it beside a
summary. A fresh XBRL fetch that comes back empty in the enrichment window leaves the run on the stored
snapshot; one still running when the enrichment join times out is cancelled, and the run generates
without XBRL, as the force path always has (the snapshot stays). An unforced first generation still
caches its excerpt when it builds it (no stored summary exists then), so an unforced run and a forced
run of one filing in two processes can still race on a filing with no summary. A replacing forced run
that finds no cache row creates one, so two replacing runs in two processes on a filing that has a
summary but no cache row fail one of them on the row's key; the other's summary and excerpt stand.

**Gate.** `backend/tests/unit/test_excerpt_writers_allowlist.py` holds the writes of
`critical_excerpt` it can see to its two owners; `test_summary_delete_sites_allowlist.py` fails a new
place it can see that deletes summaries rows; `test_force_regenerate_keeps_xbrl.py`, the
forced-precompute cases in `test_precompute_service.py` and `test_forced_run_excerpt_is_private.py` pin
the sites, two overlapping forced precomputes (one process and two) included. A new up-front clear of
another column is review-checked.

**Evidence.** `backend/app/routers/summaries.py` (the `elif force:` branch of `generate_summary_stream`),
`backend/app/services/summary_stages/enrichment.py::parse_and_enrich` (`extract_excerpt_sync`),
`backend/app/services/summary_stages/finalize.py::finalize` (`save_summary_sync`),
`backend/app/services/content_cache.py::upsert_content_cache` (`replace_excerpt`),
`backend/app/services/edgar/xbrl_service.py::EdgarXBRLService.get_xbrl_data` (`refresh`),
`backend/app/services/precompute_service.py::precompute_one`.
