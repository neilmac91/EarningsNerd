# Clear nothing before a forced refresh runs; replace stored state only with what the run brings back

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

**Rule.** A forced refresh clears nothing before its run. It regenerates in place through the one
orchestrator (`force_regenerate=True`, where keep-better decides) and replaces each stored piece only
with what the run actually got: the summary row through finalize's keep-better UPDATE, the XBRL
snapshot only when fresh XBRL arrived (`refresh_xbrl`, which only the Pro route sets; the drains read
the snapshot), and an excerpt cleared so the run rebuilds it goes back when the stored summary stays.
A refused, failed, cancelled or lower-ranked run leaves every stored piece as it was. Report a
refresh's outcome from what the run did (replaced, kept or failed), never from whether a row exists
afterwards.

**Gate.** Partly gated: `backend/tests/unit/test_summary_delete_sites_allowlist.py` fails a new place
that deletes summaries rows, a refresh that deletes the row included; `test_force_regenerate_keeps_xbrl.py`
and the forced-precompute cases in `test_precompute_service.py` pin the two sites. An up-front clear
of another column is review-checked.

**Evidence.** `backend/app/routers/summaries.py` (the `elif force:` branch of `generate_summary_stream`),
`backend/app/services/summary_stages/enrichment.py::start_enrichment_tasks`,
`backend/app/services/edgar/xbrl_service.py::EdgarXBRLService.get_xbrl_data` (`refresh`),
`backend/app/services/precompute_service.py::precompute_one`.
