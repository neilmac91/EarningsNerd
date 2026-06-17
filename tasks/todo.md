# Phase 1 — Billing to production + entitlement system (foundation)

Branch: `claude/zen-newton-upsnh9` · PR #303
Goal: Stripe works in production, entitlements are first-class & N-tier-ready, server-side
gating is centralised, a reverse trial exists. (See `docs/IMPLEMENTATION_PLAN.md` §Phase 1.)

## 1A. Data model
- [x] New `subscriptions` table (`app/models/subscription.py`, auto-created by `create_all`)
- [x] New `stripe_events` table (webhook idempotency)
- [x] `User.subscription` relationship; keep `User.is_pro` as denormalised mirror
- [x] Dated backfill SQL: `migrations/20260617_create_subscriptions_and_stripe_events.sql`

## 1B. Backend
- [x] `entitlements.py`: source of truth = subscription status ∈ {active, trialing} (+ trial not
      expired); `is_pro` mirror as fallback. New flags: realtime_alerts, eightk_coverage,
      history_retention_days, priority_model. Free watchlist → unlimited.
- [x] `require_pro` / `require_entitlement(flag)` FastAPI dependencies (`app/dependencies.py`,
      lazy auth import to avoid the routers↔dependencies cycle)
- [x] Centralise gates: `summaries.py` export (PDF/CSV) + `compare.py` via entitlements
- [x] `subscription_sync.py`: idempotency + upsert Subscription from Stripe objects + is_pro mirror
- [x] Webhook hardening: idempotency; checkout.session.completed,
      customer.subscription.created/updated/deleted, invoice.payment_failed,
      customer.subscription.trial_will_end. Webhook = sole entitlement source.
- [x] Fix checkout price-id mismatch (`_resolve_price_id` maps monthly/yearly → configured ids)
- [x] Extend `GET /api/subscriptions/subscription` → plan/status/trial_end/current_period_end/cancel_at_period_end
- [x] Reverse trial: `start_reverse_trial()` + `REVERSE_TRIAL_ENABLED` flag (default off), wired into register
- [x] Config/deploy_check: live-mode key/price assertions

## 1C. Frontend
- [x] Pricing → $14/mo · $140/yr, default annual, "2 months free" badge, refreshed Pro features
- [x] Extend `SubscriptionStatus` type with new fields
- [x] Paywall primitives: `PeekLocked`, `UpgradeModal`, `TrialBanner` (TrialBanner wired into dashboard)

## 1D. Tests
- [x] Entitlements derivation (free/pro/trialing/active/canceled/expired/naive-dt/is_pro fallback)
- [x] `require_entitlement` dependency (free=403 / pro=200 / shared-cap pass-through)
- [x] Webhook idempotency (duplicate delivery = no-op) + Subscription upsert + downgrade + is_pro mirror

## Verify
- [x] `pytest` green (backend) — 383 passed; ruff + bandit clean
- [x] `npm run lint` + `typecheck` + 45 vitest + `build` green (frontend)
- [ ] Commit + push + update PR #303

## Review (what shipped)
- Entitlements are now derived from a real `subscriptions` row, with `is_pro` kept as a
  back-compat mirror — so the webhook is the single writer of paid state and the checkout success
  redirect never grants Pro.
- Webhook is idempotent (the `stripe_events` ledger) and handles the full lifecycle incl. dunning
  and trial-ending. `invoice.payment_failed` deliberately does NOT revoke — the authoritative
  status transition arrives via `customer.subscription.updated/deleted`.
- Found + fixed a latent production checkout bug: the frontend sent placeholder price ids
  (`price_pro_monthly`) that could never match real Stripe ids; the backend now resolves logical
  tokens → configured price ids.
- Paywall primitives added; only TrialBanner is wired in (renders nothing while the trial flag is
  off). `PeekLocked`/`UpgradeModal` are ready for Phase 2/3 consumers.

## Remaining ops (runtime, not code — out of scope for this PR)
- Create the $14 / $140 Products+Prices in Stripe; set live `STRIPE_*` ids/keys + webhook secret in
  Secret Manager; flip Stripe test→live once 1D acceptance passes on a staging webhook.
- Decide when to enable `REVERSE_TRIAL_ENABLED` (default off per staged rollout).

## Notes / decisions
- Trial defaults OFF (`REVERSE_TRIAL_ENABLED=false`) per rollout strategy (flags default off).
- DB in tests is SQLite → models kept SQLite-compatible (String, not PG enums); tz-safe datetime compares.
- Stripe live flip + price-ID creation in Stripe dashboard remain a runtime/ops step (documented).
- Webhook is the **sole** entitlement source; checkout success redirect never grants Pro.
