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

## Frontend (DONE — added to #304)
- [x] notifications-api client (get/update preferences)
- [x] NotificationPreferencesForm in settings (10-K/10-Q/8-K/realtime/digest, auto-save, Pro-locked toggles)
- [x] WatchlistAddSearch on the watchlist page (debounced autocomplete → addToWatchlist) + empty-state CTA
- [x] Frontend lint + typecheck + 45 vitest + build green

## Infra increment (DONE — new PR)
- [x] CI: `Update filing-scan job image` step in deploy-backend (existence-guarded so CD never fails)
- [x] Token-gated `POST /internal/jobs/filing-scan` + `/filing-digest` (`app/routers/internal.py`,
      `INTERNAL_JOB_TOKEN` config) + tests (503 unset / 401 wrong / 202 + triggers)
- [x] DEPLOYMENT.md: one-time job + scheduler setup, internal-endpoint alternative, **Phase 2
      column-migration requirement** called out
- [x] Backend 408 pytest + ruff + bandit green

## Ops still required (manual, prod)
- Apply `backend/migrations/20260618_phase2_alerts.sql` to prod (new columns; create_all won't add them)
- One-time `gcloud run jobs create earningsnerd-filing-scan` + Cloud Scheduler triggers (or set
  `INTERNAL_JOB_TOKEN` + point Scheduler at the internal endpoints)

## Review fixes applied (Gemini, all 6 resolved)
- _write_log SAVEPOINT (isolate dup rollback) + regression test
- tz-safe `now` normalisation in scan + digest
- digest N+1 removed (one bulk query, tz-safe Python window filter)
- HTML-escape EDGAR fields in alert/digest emails

## Verify
- [x] backend `pytest` (403 passed) + ruff + bandit green (fresh-DB run)
- [x] commit + push + open Phase 2 PR (#304, draft)
- [ ] CI green on #304 (running) → then ready for review/merge

## Status
First cut complete and pushed as PR #304 (draft). All 7 first-cut tasks done:
models+migration, notification_service, filing_scan_service, email templates, prefs API,
job entrypoint, tests. Next increments: frontend (NotificationPreferencesForm + WatchlistAddSearch),
then infra (Cloud Run job + scheduler in ci.yml).
