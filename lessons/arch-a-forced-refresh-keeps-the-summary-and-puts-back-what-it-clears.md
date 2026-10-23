# A forced refresh never deletes the stored summary, and puts back what it clears when that summary stays

Date: 2026-10-22 · Area: arch / summary pipeline

**Context.** Two forced refreshes cleared stored state before the one orchestrator had admitted or
finished the run. The Pro "Regenerate" route wrote `Filing.xbrl_data = None` and committed before
admission, so that the run would re-fetch XBRL. A run the fair-use ceiling refused, or one whose SEC
document fetch failed (release cancels the XBRL task before it persists), left the filing with no
snapshot while its stored summary was still served, and that summary lost the source verification
`GET /api/summaries/filing/{id}` derives from the snapshot. The operator's forced precompute
(`scripts/pregenerate_examples.py --force`) DELETEd the summary row before generating: a provider
error left the filing with no summary, an AI-timeout fallback replaced a full summary under a new id,
and a bookmarked summary was orphaned (SQLite) or the DELETE raised on `saved_summaries`' foreign key
(PostgreSQL). Findings 6 and 7 of the 2026-10-15 backend bug hunt, fixed in P11.

**Rule.** A forced refresh never deletes the stored summary before its run, and clears nothing that
summary is served with except a piece the run can rebuild only once it is gone, which it puts back
whenever the summary stays. It regenerates in place through the one orchestrator
(`force_regenerate=True`, where keep-better decides), so the summary row changes only through
finalize's keep-better UPDATE. Stored data the run re-fetches stays until a replacement arrives: the
XBRL snapshot is replaced only by fresh XBRL (`refresh_xbrl`, which only the Pro route sets; the
drains read the snapshot), and as soon as it arrives, even when the run then fails or keep-better
keeps the stored summary, since it is the same filing's data. The one piece cleared up front is the
excerpt a forced precompute clears so the current extraction runs (the excerpt builder returns any
stored one); its stored value goes back in a `finally` whenever the stored summary stays, a raise or
a cancellation included, and none goes back as none: a summary stored beside no excerpt is verified
against the cache's other text, and the run's new excerpt would change what its quotes are read
against. Report a refresh's outcome from what the run did (replaced, kept or failed), never from
whether a row exists afterwards.

**Limits, stated.** The cleared excerpt is missing while the run is in flight (readers fall back to the
cached document), and a killed process skips the put-back. A filing with no cache row before the run
keeps the row the run creates: its stored summary had no cached source, so no quote loses its
verification. The progress row is still deleted before admission: no reader shows it beside a
summary. A fresh XBRL fetch that comes back empty in the enrichment window leaves the run on the
stored snapshot; one still running when the enrichment join times out is cancelled, and the run
generates without XBRL, as the force path always has (the snapshot stays).

**Gate.** Partly gated: `backend/tests/unit/test_summary_delete_sites_allowlist.py` fails a new place
it can see that deletes summaries rows, a refresh that deletes the row included;
`test_force_regenerate_keeps_xbrl.py` and the forced-precompute cases in `test_precompute_service.py`
pin the two sites, the excerpt's put-back on a raise or a cancellation included, from a stored
excerpt and from none. A new up-front clear of another column is review-checked.

**Evidence.** `backend/app/routers/summaries.py` (the `elif force:` branch of `generate_summary_stream`),
`backend/app/services/summary_stages/enrichment.py::start_enrichment_tasks`,
`backend/app/services/edgar/xbrl_service.py::EdgarXBRLService.get_xbrl_data` (`refresh`),
`backend/app/services/precompute_service.py::precompute_one`.
