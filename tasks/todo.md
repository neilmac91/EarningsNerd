# Phase 2 — Watchlist + new-filing alerts (retention engine)

Branch: `claude/zen-newton-upsnh9` (synced to merged main @ 41fa724)
Goal: detect new filings for watched companies and alert watchers — Free=daily digest,
Pro=real-time + 8-K. This produces the north-star metric. See IMPLEMENTATION_PLAN §Phase 2.

Decisions taken (recommended defaults; flagged for confirmation):
- Pro-gated prefs (realtime, 8-K) for a Free user are **coerced to false + effective value returned**
  (not 403) so the UI can show a PeekLocked toggle.
- Hourly scan + once-daily digest. Alerts **link** to on-demand generation (no auto-LLM for free).
- Default prefs: backfill existing users + lazy get-or-create.
- Skipped the watchlist (user,company) unique-constraint change (avoid migration risk on live dupes).

## First cut (this PR) — backend alert engine + prefs API + tests (CI-testable, mocked EDGAR/email)
- [ ] Models: `NotificationPreferences`, `NotificationLog` (`app/models/notifications.py`);
      `Watchlist.last_alerted_accession/at`, `Company.last_filings_check_at`; cascade rels; exports
- [ ] Migration: `migrations/20260618_phase2_alerts.sql` (additive, idempotent, + prefs backfill)
- [ ] `notification_service.py`: get_or_create_preferences, evaluate_delivery, entitlement coercion
- [ ] `filing_scan_service.py`: upsert_filings helper, run_filing_scan (detector + realtime + dedup),
      run_daily_digest; EDGAR + email injected for testing; baseline high-water mark (no historical spam)
- [ ] Email: `render/send_new_filing_alert`, `render/send_daily_digest`; parameterised footer
- [ ] Prefs API: `GET/PUT /api/users/me/notification-preferences` (coercion via entitlements)
- [ ] Thin job entrypoint: `scripts/filing_scan.py` (mirrors pregenerate_examples.py)
- [ ] Tests: dedup (one alert/eligible watcher, never twice), gating (Pro realtime vs Free digest,
      8-K Pro-only, form-type prefs), no-historical-spam, prefs API coercion, email render no-PII

## Deferred to follow-up increments
- Frontend: NotificationPreferencesForm (settings) + WatchlistAddSearch + Pro toggles (PeekLocked)
- Infra: Cloud Run job + Scheduler wiring in ci.yml; optional token-gated POST /internal/jobs/filing-scan

## Verify
- [ ] backend `pytest` + ruff + bandit green
- [ ] commit + push + open Phase 2 PR
