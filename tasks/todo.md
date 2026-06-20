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

## Deferred-items pass (2026-06-20) — picked up after the remediation pass
- [x] **Retry-After on 429** (#336) + polish/NaN-guard (#337)
- [x] **Live companyfacts cross-check** (#338) — authoritative §3.5 step 2 (corrects headline scale/sign bugs)
- [x] **P1 search date-range filter UI** (#339)

## Still deferred — needs infra / a product call / live validation (not buildable-or-verifiable here)
- **FSDS bulk backfill loader** — multi-GB quarterly TSV ingestion + `COPY`; infra-heavy, can't verify in sandbox.
- **13F / institutional holders of a company** — an inverse lookup; needs full 13F ingestion + a
  CUSIP→ticker index (same class of work as FSDS). Not a clean live-endpoint like P4 insider.
- **Frames API peer breadth** — re-evaluated as marginal: Frames gives values for the whole filer
  universe but NOT their SIC, so same-SIC filtering still depends on our own corpus' SIC knowledge
  unless we build a CIK→SIC index (infra). Facts backfill already broadens coverage; revisit if a
  CIK→SIC source is added.
- **⌘K command palette for full-text search** — a UX/product call (conflicts with the existing ⌘K
  bound to company search); needs a deliberate decision, not a unilateral change.
- **Highlighted snippets** in search results — needs a backend `EftsHit` change AND live
  confirmation EFTS returns highlight data (a verify-script task; unverifiable in the sandbox).
- **`EDGAR_LOCAL_DATA_DIR`** — only helps with a persistent volume (Cloud Run fs is ephemeral); infra.

## Review log
- **#331** (P0): edgartools 5.37 + edgar logger silence. CI green with 5.37.
- **#332** (gate): Gemini flagged the gate wasn't period-aware (cross-concept + prior cutoff over
  multi-period batches) — fixed by grouping per period and chaining in-batch priors (handles a case
  the reviewer's per-group suggestion missed). All 3 review comments resolved.
- **#333** (badge): Gemini flagged my `null`-while-loading change as a guaranteed CLS on success;
  reverted to the strategy's reserve-skeleton, kept the badge.
- **#334** (PR-C): multi-period depth + scheduled/incremental backfill + processed_facts_at.
- **#336/#337** (Retry-After): honor SEC Retry-After on 429 (capped); review caught + fixed a NaN
  crash path (`float("nan")` → `asyncio.sleep(nan)`).
- **#338** (cross-check): companyfacts authoritative tier; review tightened the annual-duration band
  (120→30d, excludes 9-month YTD), fixed an N+1 (joinedload), restatement tie-break (`<=`).
- **#339** (search dates): date-range UI; review caught + fixed firing a request on an inverted range.
- Net result: peers/fundamentals write+serve a real `reconciled` flag (was always False), headline
  figures are corrected against SEC companyfacts, untrusted values are flagged not hidden, the facts
  table populates weekly with multi-year history, full-text search has form + date filters, the SEC
  rate limiter honors Retry-After, and P4 insider parsing runs on the edgartools 5.37 it targets.
  Remaining deferred items all need infra / a product call / live validation (see section above).
