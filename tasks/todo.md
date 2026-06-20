# SEC Data Expansion — Remediation Pass (data trust & honesty)

Driven by the audit of parallel-built P1/P3/P4 work against `tasks/sec-data-expansion-strategy.md`.
User decisions (2026-06-20): focus = **data trust & honesty**; recon depth = **local invariants + UI flag**;
population = **schedule + deepen current backfill**; 5.37 bump = **yes, isolated PR + tests**.

Each item below is a focused PR off `main`, driven to green CI + merge before the next.

---

## PR-A — P0: bump edgartools 5.36 → 5.37 (isolated) — MERGED #331
- [x] `backend/requirements.txt`: `edgartools==5.36.0` → `5.37.0`
- [x] Verified via CI backend-tests (green with 5.37 installed)
- [x] Live Form-4 shape recheck = `scripts/verify_insider_extraction.py` post-deploy (documented)
- [x] Silenced the noisy `edgar` logger in `logging_service.py`

## PR-B1 — Reconciliation gate (local invariants) backend — MERGED #332
- [x] `reconcile_facts()` pure gate, period-aware (groups by period_end, chains in-batch priors):
      revenue≥0 hard-reject; zero-where-prior-nonzero; magnitude vs prior; sign(EPS)=sign(NI);
      diluted≤basic; period_end vs period_of_report (latest period only)
- [x] `upsert_facts` persists computed `reconciled` (was hard-coded False) + drops rejects
- [x] Expose `reconciled` through peers + fundamentals schemas/services
- [x] 13 gate + DB tests (incl. multi-period, added in review)

## PR-B2 — Honesty surfacing frontend — MERGED #333
- [x] `UnverifiedBadge` on peers + fundamentals when a shown value is flagged
- [x] Kept reserve-skeleton loading (reverted the null-while-loading change per review → no CLS)

## PR-C — Facts population: schedule + deepen — THIS PR
- [x] Normalizer consumes the full multi-period `series` (one fact per reported period)
- [x] `scripts/backfill_facts.py` + `earningsnerd-backfill-facts` Cloud Run job (ci.yml image bump
      + DEPLOYMENT.md create/scheduler/smoke); weekly Cloud Scheduler trigger
- [x] `Filing.processed_facts_at` column + migration; set on normalize; `only_unprocessed` incremental
- [x] Tests: multi-period normalize, point-form override, processed stamp + incremental skip

---

## Explicitly deferred (not in this pass; logged for later)
- Full §3.5 live cross-check vs `data.sec.gov/companyconcept` (chose invariants-only for v1)
- Frames API cross-company primitive for peer breadth (peers stay corpus-bounded for now)
- FSDS bulk backfill loader (broad coverage) — bigger effort
- P1 search: ⌘K trigger, highlighted snippets (needs backend EftsHit change), date-range filter UI
- 13F / institutional signals (never built)
- `EDGAR_LOCAL_DATA_DIR`, Retry-After on 429 (remaining P0 hygiene)

## Review log
- **#331** (P0): edgartools 5.37 + edgar logger silence. CI green with 5.37.
- **#332** (gate): Gemini flagged the gate wasn't period-aware (cross-concept + prior cutoff over
  multi-period batches) — fixed by grouping per period and chaining in-batch priors (handles a case
  the reviewer's per-group suggestion missed). All 3 review comments resolved.
- **#333** (badge): Gemini flagged my `null`-while-loading change as a guaranteed CLS on success;
  reverted to the strategy's reserve-skeleton, kept the badge.
- **#NNN** (PR-C): multi-period depth + scheduled/incremental backfill + processed_facts_at.
- Net result: peers/fundamentals now write+serve a real `reconciled` flag (was always False),
  flag rather than hide untrusted values, the table populates on a weekly cron with multi-year
  history, and the just-merged P4 insider parsing runs on the edgartools 5.37 it was designed for.
  Still deferred (logged above): live companyconcept cross-check, Frames breadth, FSDS bulk, 13F,
  P1 search polish, remaining P0 hygiene.
