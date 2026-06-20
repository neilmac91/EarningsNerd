# SEC Data Expansion — Remediation Pass (data trust & honesty)

Driven by the audit of parallel-built P1/P3/P4 work against `tasks/sec-data-expansion-strategy.md`.
User decisions (2026-06-20): focus = **data trust & honesty**; recon depth = **local invariants + UI flag**;
population = **schedule + deepen current backfill**; 5.37 bump = **yes, isolated PR + tests**.

Each item below is a focused PR off `main`, driven to green CI + merge before the next.

---

## PR-A — P0: bump edgartools 5.36 → 5.37 (isolated)
- [ ] `backend/requirements.txt`: `edgartools==5.36.0` → `5.37.0`
- [ ] Verify via CI backend-tests (sandbox lacks edgartools/network; CI is the regression signal)
- [ ] Note: live Form-4 shape recheck = `scripts/verify_insider_extraction.py` post-deploy
- [ ] (cheap P0 rider) silence the noisy `edgar` logger in `logging_service.py`

## PR-B — Reconciliation gate (local invariants) + honesty surfacing  ← core deliverable
Backend — `facts_service.py`:
- [ ] Pure gate fn over a per-filing fact batch + prior-value lookup; returns reconciled + reason
  - revenue ≥ 0 (hard reject negative); zero-where-prior-nonzero → flag
  - sign(EPS) == sign(net_income)
  - diluted EPS ≤ basic EPS
  - magnitude vs prior within ~1 order of magnitude (scale-bug catch)
  - period_end aligns with filing period_of_report (period correctness)
- [ ] Set `reconciled` on write per gate outcome (replace hard-coded False)
- [ ] Expose `reconciled` (+ coverage/quality summary) through peers + fundamentals schemas
- [ ] Unit tests for the gate (pure, sandbox-verifiable) covering each invariant + edge cases
Frontend — honesty + UX:
- [ ] Quality badge on peers + fundamentals (extend `ENABLE_QUALITY_BADGE`) when data is unreconciled
- [ ] Fix `FundamentalsTrendChart` post-load collapse → no layout shift

## PR-C — Facts population: schedule + deepen
- [ ] Extend normalizer to consume the full multi-period `series` (not just `current`)
- [ ] Wire `backfill-facts` to the weekly cron / Cloud Scheduler (currently manual-trigger only)
- [ ] Add `Filing.processed_facts_at` tracking column (§3.1) + set it on normalize
- [ ] Tests for multi-period normalization

---

## Explicitly deferred (not in this pass; logged for later)
- Full §3.5 live cross-check vs `data.sec.gov/companyconcept` (chose invariants-only for v1)
- Frames API cross-company primitive for peer breadth (peers stay corpus-bounded for now)
- FSDS bulk backfill loader (broad coverage) — bigger effort
- P1 search: ⌘K trigger, highlighted snippets (needs backend EftsHit change), date-range filter UI
- 13F / institutional signals (never built)
- `EDGAR_LOCAL_DATA_DIR`, Retry-After on 429 (remaining P0 hygiene)

## Review log
- (filled in as PRs land)
