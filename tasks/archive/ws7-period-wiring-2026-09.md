# Prospective reporting-date wiring — implementation archive

Archived 2026-09-05 after [PR #704](https://github.com/neilmac91/EarningsNerd/pull/704) merged and its deployment was verified.
Final local backend gate: `2354 passed, 2 deselected, 72 warnings in 52.71s`; Ruff and Bandit passed. 8 intended mutation failures; 58 focused tests. Current-period mismatch, comparative exemption, missing dates, authoritative cross-check and existing-identity skip were verified. Deployment does not repair historical flags.

See the [current evidence ledger](../wave2-ledger-2026-09.md) for merge SHAs, actual CI and deployment links,
and [active handover](../handover-wave2-2026-09.md) for unmet programme conditions.
The original plan below is historical: unchecked implementation boxes record its pre-execution
state, not a request to repeat completed work. Explicit readout, broader-coverage and founder
residuals remain open in the active todo. No wave-completion claim is made.

---

## WS-7 reporting-date wiring — prospective reconciliation correction

Base: #703 merged and its backend deployment is verified healthy. The persisted Filing model
has period_end_date; the per-filing fact writer reads nonexistent period_of_report, so its
existing local current-period mismatch check receives None. This predates this remediation wave.

- [ ] Backend Developer (plan_correctness): pass the actual reporting calendar date into the
  existing reconciliation gate, preserving missing metadata and all source values/identities.
- [ ] Backend Developer: add real persisted ORM integration controls for matching, mismatching,
  missing dates, comparative rows, shared backfill and unchanged existing-row skip behavior;
  prove every new test with intended-assertion mutations and exact restoration.
- [ ] Backend Developer: correct stale writer/backfill and architecture documentation. Describe
  prospective inserts, optional companyfacts cross-check policy, and lack of general historical
  flag repair; do not imply deployment or existing backfill repairs old identities.
- [ ] Chief engineer: run exact pinned full backend gates. Database/data-integrity (plan_rules),
  integration/eval (plan_gates), and root independently review; use two refuters per serious finding.
- [ ] Chief engineer: record the already verified Copilot checkpoint in its owning RUNBOOK now;
  its backend path otherwise causes an avoidable extra deployment during final docs synchronization.
- [ ] Chief engineer: inspect required actual CI and eval artifacts, merge using freshly read
  head SHA, then verify migrations, traffic and detailed production health before another merge.

No migration, extraction change, period_start inference, threshold change, baseline re-pin,
production backfill or founder operation is included. Closing docs follow the verified deployment.
