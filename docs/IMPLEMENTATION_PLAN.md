# EarningsNerd — Implementation Plan: Freemium Dashboard / Watchlist / Settings

**Date:** 2026-06-17 · **Owner:** (you) · **Status:** Draft for review — *no feature code written yet.*
**Companion docs:** `docs/AUTH_INVESTIGATION.md` (Phase 0), `docs/RESEARCH_SYNTHESIS.md` (value thesis & Free/Pro philosophy).

> **Decisions locked (2026-06-17):** (1) **Phase 0 auth fix applied** in full on this branch (PR #303). (2) Build order after auth+billing: **Watchlist + alerts first** (retention engine). (3) Pricing: **Pro $14/mo · $140/yr** with a **7-day no-card reverse trial**. (4) Alerts v1: **email-first — 10-K/10-Q delayed for Free, real-time + 8-K for Pro.** These resolve open questions Q1–Q4 and Q7 in §7.
>
> **Reality check that reshapes this plan:** Dashboard, Watchlist, and Settings are **NOT empty scaffolds.** They are substantially built and wired (React Query + real APIs). So this is **"complete, deepen, and monetise,"** not green-field. Likewise the backend already has an `entitlements.py` abstraction, a Stripe router (checkout + portal + signature-verified webhook), watchlist CRUD + insights, and usage metering. The work is to **finish billing for production, formalise entitlements, add the new-filing alert loop, and deepen the three sections** — not to rebuild.

---

## 0. Current state (verified) — what exists vs what's missing

| Area | Already built | Missing / broken |
|---|---|---|
| **Auth** | Custom JWT + refresh cookies, Google + Apple OIDC, silent refresh, middleware gate | `COOKIE_DOMAIN` unset → redirect loop (Phase 0); middleware gates on 30-min token |
| **Billing** | `subscriptions.py`: checkout, portal, **signature-verified** webhook (3 events); `is_pro` + stripe ids on `User` | No `Subscription` table (status/period/trial unknown); **no webhook idempotency**; no trial/dunning; price IDs default `""`; test↔live key handling undocumented |
| **Entitlements** | `entitlements.py` (`Entitlements` dataclass, `get_entitlements`); export/compare/summary-quota gated | Ad-hoc `if not is_pro` (no `require_pro` dependency); watchlist limit defined but **not enforced**; flags missing (alerts, 8-K, history, priority model) |
| **Dashboard** | `dashboard/page.tsx`: subscription + usage + saved summaries + watchlist cards | No "what changed" feed, no new-filings feed, no calendar |
| **Watchlist** | model (user/company), CRUD, `/insights`, compare route | **No new-filing detection, no alerts, no notification prefs**, no at-a-glance metrics |
| **Settings** | account info, ConnectedAccounts (OAuth/sessions), GDPR export + delete | No notification prefs, no profile edit, no password change/set, thin billing panel |
| **Infra** | Cloud Run + Cloud SQL; **weekly Cloud Scheduler → Cloud Run job** (`earningsnerd-pregenerate`) | No general alert/cron framework (but the pregenerate pattern is reusable) |
| **Design system** | Tailwind `mint` brand + light/dark tokens; custom components (no shadcn); React Query; lucide; PostHog | — (new UI must match these tokens) |

**Migration mechanism:** schema is `Base.metadata.create_all()` at startup (creates **missing tables** only) + manual SQL in `backend/migrations/`. **New tables** auto-create; **new columns on existing tables** need a hand-written migration file. No Alembic.

---

## 1. Phase sequencing (recommended)

```
Phase 0  Auth fix .......................... CRITICAL PATH — blocks all verification (1 PR, ~0.5 day)
Phase 1  Billing→prod + entitlements ....... FOUNDATION — must land before any paid feature (~4–6 days)
Phase 2  Watchlist + new-filing alerts ..... RETENTION ENGINE — drives the north-star metric (~6–8 days)
Phase 3  Dashboard (personalised home) ..... SURFACES the loop; "value obvious in seconds" (~4–6 days)
Phase 4  Settings (prefs/billing/profile) .. POLISH + the controls Phases 2–3 imply (~3–5 days)
```

**Why this order (vs the brief's Dashboard-first listing):** the value thesis + YC filter say **retention before acquisition**, and our north-star ("users return *for the content* when a watched company files") is produced by the **Watchlist alert loop**, not by a pretty home screen. Notification *preferences* (a Settings surface) are a hard dependency of alerts, so a slice of Settings rides along in Phase 2. Phase 3's Dashboard then *surfaces* the loop the user already values.
**Open decision (Q2):** confirm the v1 must-have section. If you want Dashboard first for demo impact, Phases 2 and 3 swap, with the new-filing **detection job** still landing in Phase 2 (the feed needs it).

---

## Phase 0 — Auth fix (critical path)
Full detail in `docs/AUTH_INVESTIGATION.md`. Summary:
- **Fix 1:** `COOKIE_DOMAIN=.earningsnerd.io` (Cloud Run env → CI `--update-env-vars` + `DEPLOYMENT.md`). Stops the loop.
- **Fix 2:** durable `en_session` presence cookie; middleware reads it (kills the 30-min recurrence / the whole "server can't see the session" bug class).
- **Fix 3:** consume `?redirect=` after login.
- **Tests:** backend cookie-domain test; Vitest `middleware` test; cookie-name contract test.
- **Acceptance:** sign in → `/dashboard`, `/dashboard/watchlist`, `/dashboard/settings` all load on apex **and** www; deleting the access cookie still loads (silent refresh); regression tests pass in CI.

---

## Phase 1 — Billing to production + entitlement system (foundation)

**Goal:** Stripe works in production, entitlements are first-class and N-tier-ready, server-side gating is centralised, and a reverse trial exists.

### 1A. Data model
- **New `subscriptions` table** (auto-created by `create_all`):
  `id, user_id (FK, unique), plan (enum: free|pro), status (active|trialing|past_due|canceled|incomplete), stripe_customer_id, stripe_subscription_id, stripe_price_id, current_period_end, trial_end, cancel_at_period_end (bool), created_at, updated_at`.
  Keep `User.is_pro` as a **denormalised mirror** updated by the webhook (back-compat for existing reads), but make `entitlements.get_entitlements()` the single source of truth, derived from `subscriptions.status ∈ {active, trialing}`.
- **New `stripe_events` table** (idempotency): `event_id (PK, Stripe id), type, processed_at`.
- **Migration notes:** new tables auto-create. Backfill: one-off SQL inserting a `subscriptions` row per existing user from `User.is_pro/stripe_*`. Add to `backend/migrations/` with a dated filename; document in PR.

### 1B. Backend
- **Webhook hardening** (`subscriptions.py`): idempotency via `stripe_events` (skip if seen); handle `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.payment_failed` (dunning/`past_due`), `customer.subscription.trial_will_end` (T-3 email). **Webhook is the source of truth for entitlements** — never grant Pro from the checkout success redirect.
- **Reverse trial:** on first checkout (or on signup, see Q3) create a `trialing` subscription with `trial_end = now + 7d`, no card (Stripe trial w/o payment method, or app-level trial flag if not using Stripe trials). Entitlements treat `trialing` as Pro.
- **`require_pro` / `require_entitlement(flag)` FastAPI dependency** — replace ad-hoc `if not current_user.is_pro` in `summaries.py` (export), `compare.py`. Centralised, auditable, tier-ready.
- **Extend `entitlements.py`** with named flags: `monthly_summary_limit, can_export, can_compare, watchlist_limit (→ None/unlimited free), realtime_alerts, eightk_coverage, history_retention_days, priority_model`.
- **Extend `GET /api/subscriptions`** to return `{plan, status, trial_end, current_period_end, cancel_at_period_end}`.
- **Config/secrets:** verify **live** `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY_ID`, `STRIPE_PRICE_YEARLY_ID` in Secret Manager; add a `deploy_check.py` assertion that they're set + key/price livemode match `ENVIRONMENT`.

### 1C. Frontend
- Pricing page already does checkout + an A/B at $19/$29 → set **$14/mo, $140/yr**, default annual toggle, add "2 months free" badge, reverse-trial CTA copy.
- **Trial banner** (days remaining) + **billing panel** (plan, renew/cancel date, manage via portal) — partly in Dashboard/Settings today; consolidate.
- **Paywall primitives:** `UpgradeModal`, `PeekLocked` wrapper (greyed feature + "Pro" pill), reuse usage meter. Contextual triggers (limit reached, export click, 8-K toggle).

### 1D. Acceptance criteria
- Real card completes checkout in **live** mode; webhook flips entitlement; refresh persists Pro.
- Duplicate webhook delivery is a no-op (idempotency test).
- Cancel via portal → `cancel_at_period_end` shown; access remains until `current_period_end`, then downgrades (verified by webhook).
- Trial grants Pro for 7 days then auto-downgrades; T-3 email sent.
- Export/compare gated via `require_pro`; unit tests cover free=403 / pro=200.

**Effort:** ~4–6 dev-days. **Deps:** Phase 0 (must verify behind working auth). **Risks:** double-charge (idempotency), test/live mixups (config guard) — see register.

---

## Phase 2 — Watchlist + new-filing alerts (retention engine)

**Job-to-be-done:** *"Tell me when a company I care about files, and what changed — so I come back."* This produces the north-star metric.

### 2A. Data model
- **`Watchlist` additions** (manual column migration): `last_alerted_accession (str, nullable)`, `last_alerted_at (datetime, nullable)` — what we've already notified on per (user, company).
- **New `notification_preferences`** (one row per user): `user_id (unique), notify_10k, notify_10q, notify_8k (bool), channel (email|in_app), digest (immediate|daily|weekly), realtime (bool, Pro-gated)`. Defaults: 10-K/10-Q on, 8-K off, email, daily digest, realtime off.
- **New `notification_log`** (dedup + audit): `id, user_id, filing_id, channel, status (sent|failed|skipped), created_at`. Unique `(user_id, filing_id, channel)` prevents double-send.
- **Company tracking:** `Company.last_filings_check_at` (or a small `filing_scan_state` table) for the detector.

### 2B. New-filing detection + delivery (reuse the cron pattern)
- A **Cloud Run job + Cloud Scheduler** (mirror `earningsnerd-pregenerate`), e.g. `earningsnerd-filing-scan`, running ~hourly:
  1. Distinct set of watched companies (cheap query).
  2. For each, via existing EDGAR client (SEC rate limiter + circuit breaker), fetch latest 10-K/10-Q/8-K; upsert `Filing` rows.
  3. For each watcher whose prefs match the form type and whose `last_alerted_accession` differs → enqueue alert; write `notification_log`.
  4. **Free = delayed** (batched into the next daily digest); **Pro = real-time** (sent on this run). Implemented as a delivery-time gate keyed on `notification_preferences.realtime` + entitlement.
- **LLM cost control (important):** alerts **link to on-demand generation**, they do **not** auto-generate summaries for free users. Optionally pre-generate (premium model) only for **Pro** watchers or already-"hot" filings, behind a flag. (Decision Q5.)
- **Email:** new Resend templates (`new_filing_alert`, `daily_digest`) via `email_service.py`. Plain, public filing info only (no PII).
- **In-app:** a lightweight `GET /api/notifications` (unread feed) + bell indicator (optional v1; email is the v1 channel).

### 2C. Watchlist UI deepening
- Add-from-search (autocomplete) directly on the page; current add is from company pages only.
- Per-row at-a-glance: latest filing type/date, summary status (exists), "what changed" link, **alert toggles** (per company override optional; v1 = global prefs).
- **Compare** entry (2–5 filings; Pro) — route exists.
- Empty/over-limit states (free watchlist stays **unlimited** per the value thesis → no cap UI).

### 2D. Acceptance criteria
- A test company filing a new 10-Q triggers exactly one alert per eligible watcher (dedup verified); Pro gets it in real time, Free in the daily digest.
- Toggling 8-K on (Pro) starts including 8-Ks; off excludes them.
- Alert email links to the filing → summary; click tracked.
- No alert is ever sent twice (notification_log unique constraint).
- Detector respects SEC rate limits (no circuit-breaker trips under normal load).

**Effort:** ~6–8 dev-days. **Deps:** Phase 0; entitlements from Phase 1 (realtime/8-K gating); notification prefs (built here). **Risks:** EDGAR load, alert spam, email deliverability, LLM cost — see register.

---

## Phase 3 — Dashboard (personalised home)

**Job-to-be-done:** *"In seconds, show me what's new and worth my attention across what I track."*

### 3A. Scope (v1)
- **"What changed" / new-filings feed:** recent 10-K/10-Q/(8-K) for watched companies, newest first, each with a one-line "what changed vs last filing" (from the compare/diff engine) and a CTA to the summary. *This is the centrepiece.*
- **Saved summaries** (exists) + **quick search** (exists elsewhere; add prominent search).
- **Earnings/filing calendar:** upcoming earnings/filing dates for watched companies (reuse `earnings_whispers` / `fmp` integrations).
- **Usage + plan + trial** state (exists) — keep as a compact strip, not the hero.

### 3B. Backend
- `GET /api/dashboard/feed?limit=` — composes watched companies' latest filings + summary-existence + a short diff headline (cache-friendly; reuse `/watchlist/insights` logic + compare engine). Paginated.
- `GET /api/calendar/upcoming` — earnings/filing dates for watched companies.
- (The "what changed" headline can start as a cheap, deterministic XBRL delta — revenue/EPS up/down — and only call the LLM for a richer diff on click. Cost-aware. When extracting this financial ground truth, enforce **hard invariants** — e.g. revenue ≥ 0 and `sign(EPS) == sign(net income)` — and drop/flag rows that violate them, so corrupt or misaligned XBRL never poisons the feed or any eval set. *(per PR review.)*)

### 3C. Frontend
- `FilingFeed` + `WhatChangedCard`, `EarningsCalendar`, prominent `QuickSearch`. Reuse `StateCard`, `SecondaryHeader`, mint tokens, skeleton loaders.
- Empty-state for users with no watchlist → guided "add your first company" (activation).

### 3D. Acceptance criteria
- A user with ≥1 watched company sees their latest filings + a "what changed" line within one screen; click → summary.
- New watcher sees a guided empty state, not a blank page.
- Feed loads < 1s p50 (cached); no N+1 to EDGAR on render.

**Effort:** ~4–6 dev-days. **Deps:** Phase 2 (detection + filings populated); compare engine.

---

## Phase 4 — Settings (preferences, billing, profile)

### 4A. Scope (v1) — build only what's used
- **Notification preferences** UI (the prefs from Phase 2): form bound to `GET/PUT /api/users/me/notification-preferences`. Real-time toggle is `PeekLocked` for free.
- **Billing panel:** plan, usage, trial countdown, renew/cancel date, "Manage billing" (portal), cancel CTA. (Consolidate the bits currently split across Dashboard.)
- **Profile:** edit display name (`PATCH /api/users/me`).
- **Password:** set/change (`POST /api/auth/change-password`) — currently only "Set/Not set" status is shown; OAuth-only users can set a password to unlock email login.
- **Keep** existing ConnectedAccounts (OAuth/sessions) + GDPR export/delete.
- **Cut for v1** (YC filter — unused-toggle risk): 2FA, granular data-retention config, per-device session list. Revisit if requested.

### 4B. Acceptance criteria
- Changing notification prefs persists and changes alert behaviour (end-to-end with Phase 2).
- Name edit + password set/change work; OAuth-only user can subsequently log in with email/password.
- Billing panel reflects live Stripe state (trial/active/cancel-at-period-end).

**Effort:** ~3–5 dev-days. **Deps:** Phases 1–2.

---

## 2. Backend endpoints (net-new / changed)

| Method | Path | Phase | Purpose |
|---|---|---|---|
| — | `require_pro` / `require_entitlement(flag)` dependency | 1 | Centralised gating |
| GET | `/api/subscriptions` (extend) | 1 | Add status/trial/period/cancel fields |
| POST | `/api/subscriptions/webhook` (harden) | 1 | Idempotency + more events |
| GET/PUT | `/api/users/me/notification-preferences` | 2/4 | Alert prefs |
| GET | `/api/notifications` (optional) | 2 | In-app unread feed |
| GET | `/api/dashboard/feed` | 3 | Personalised filings feed + "what changed" |
| GET | `/api/calendar/upcoming` | 3 | Earnings/filing calendar |
| PATCH | `/api/users/me` | 4 | Edit profile (name) |
| POST | `/api/auth/change-password` | 4 | Set/change password |
| POST | `/internal/jobs/filing-scan` (token) or job entrypoint | 2 | Cron new-filing detection |

## 3. Frontend routes/components (net-new)

- Components: `FilingFeed`, `WhatChangedCard`, `EarningsCalendar`, `QuickSearch`, `WatchlistRow` (deepened), `NotificationPreferencesForm`, `BillingPanel`, `ProfileForm`, `ChangePasswordForm`, `TrialBanner`, `UpgradeModal`, `PeekLocked`.
- **Auth-state handling rule (so the Phase-0 bug class can't recur), document in a short `frontend/features/auth/README`:**
  1. **Server gate** = middleware on the **durable `en_session`** cookie only (never the 30-min access token).
  2. **Client gate** = React Query `['user']` via `getCurrentUserSafe()`; render a **skeleton** while loading, **never** redirect before hydration.
  3. **API** = `withCredentials` + silent refresh handles token rotation transparently.
  4. Cross-cutting: cookies always `Domain=.earningsnerd.io`; cookie-name contract pinned by a test.

## 4. Telemetry (define up front — PostHog already integrated)

- **Activation:** `signup_completed`, `first_summary_generated`, `watchlist_first_add`, `trial_started`.
- **Retention (north-star inputs):** `summary_viewed {source: self|alert|feed}`, `alert_email_sent`, `alert_email_clicked`, `dashboard_feed_clicked`, `watchlist_return` (session entered via an alert), `weekly_active`.
- **Conversion:** `paywall_viewed {context}`, `upgrade_clicked`, `checkout_started`, `checkout_completed`, `trial_converted`, `subscription_canceled`, `portal_opened`.
- **North-star (derived):** weekly returning users who viewed ≥1 `summary_viewed {source ∈ alert|feed}`. Build a PostHog dashboard for activation→retention→conversion before Phase 2 ships.

## 5. Rollout strategy

- **Feature flags** (`lib/featureFlags.ts` + PostHog): `alerts`, `eightk_coverage`, `realtime_alerts`, `dashboard_feed`, `calendar`, `reverse_trial`, `new_pricing`. Default off; enable per-environment.
- **Staged:** internal users → 10% → 50% → GA per feature. **Stripe stays in test mode** until 1D acceptance passes on a staging webhook, then flip live.
- **Rollback:** flags off (instant); Stripe live→test; `COOKIE_DOMAIN`/`en_session` are additive and individually revertable; new tables are additive (no destructive migrations). Keep `User.is_pro` mirror so a rollback of the `subscriptions` table doesn't strip access.

## 6. Risk register

| Risk | L | Impact | Mitigation |
|---|---|---|---|
| Auth regression returns | M | Critical | Phase-0 regression tests in CI; startup warning if `COOKIE_DOMAIN` unset in prod |
| Stripe webhook double-processing → double-charge / wrong entitlement | M | High | `stripe_events` idempotency; webhook = sole entitlement source; tests for duplicate delivery |
| Test/live key or price-id mismatch | M | High | Secret Manager live values; `deploy_check.py` livemode assertion |
| EDGAR rate-limit / load from scanner | M | Med | Existing SEC rate limiter + circuit breaker; hourly batch; per-company `last_check`; backoff |
| Alert spam / duplicate emails | M | High (trust) | `notification_log` unique `(user,filing,channel)`; digest batching for free |
| LLM cost blowout from auto-summarising alerts | M | High | Alerts link to on-demand gen; pre-gen only Pro/hot behind flag; two-model split (cheap default, premium = Pro) |
| Email deliverability | L | Med | Resend verified domain (already enforced in config); monitor bounces via webhook |
| Migration on live data (no Alembic) | M | High | Additive columns/tables only; dated SQL in `migrations/`; backfill scripts; test on staging dump first |
| Privacy/PII leakage in alerts/logs | L | High | Public filing data only; no PII/secrets in logs (existing structured-logging discipline) |
| Free watchlist unlimited → scan cost grows | L | Med | Scan is per-distinct-company, not per-watch; cache; revisit a soft cap only if abused |
| Building unused Settings/Dashboard widgets | M | Med (waste) | YC decision filter; instrument; cut anything <2% used |

## 7. Open questions & assumptions

**Assumptions (proceeding unless corrected):** Pro = $14/mo, $140/yr; 7-day no-card reverse trial; free watchlist stays unlimited; free summary cap stays ~5/mo; alerts are email-first; real-time alerts + 8-K + premium-model summaries are Pro; sections are "complete & deepen," not rebuild; custom auth stays (no migration to NextAuth/Clerk).

**Load-bearing questions:**
- **Q1 — Auth/provider:** ✅ RESOLVED — keep custom JWT+OIDC; Phase 0 applied.
- **Q2 — v1 sequencing:** ✅ RESOLVED — **Watchlist + alerts first.**
- **Q3 — Trial trigger:** ✅ RESOLVED (pricing) — 7-day **no-card reverse trial**. *Sub-question still open:* fire it on **signup** (max reveal) vs **first checkout intent** (less abuse) — assuming **signup** unless you say otherwise.
- **Q4 — Alert channels & 8-K:** ✅ RESOLVED — **email-first; 8-K = Pro; real-time = Pro.** *Sub-question:* in-app bell deferred past v1 unless you want it now.
- **Q5 — Auto-generation on alert:** OPEN — for Pro watchers, pre-generate the summary (premium model, cost) so the alert is "ready to read," or always on-demand? (Assuming on-demand; pre-gen behind a flag.)
- **Q6 — Data freshness:** OPEN — scan cadence (hourly assumed) and any EDGAR/XBRL constraints to respect.
- **Q7 — Pricing lock:** ✅ RESOLVED — **$14/mo · $140/yr**, reverse trial.
- **Q8 — Design constraints:** OPEN — assuming new UI matches the existing `mint` Tailwind system (no new component library); confirm.

---

## 8. Free vs Pro feature matrix (v1)

| Capability | Free | Pro ($14/mo · $140/yr) | Enforcement |
|---|---|---|---|
| Search, company & filing pages | ✅ | ✅ | — |
| AI filing summaries | ✅ **~5 / month** | ✅ **Unlimited** | `monthly_summary_limit` (built) |
| Summary depth / model | Standard (cheap model) | **Deepest + premium model** | `priority_model` flag (new) |
| Reverse trial (full Pro, 7 days, no card) | ✅ on signup | — | `subscriptions.status=trialing` |
| Watchlist size | ✅ **Unlimited** | ✅ Unlimited | none (drop the 20 cap) |
| New-filing email alerts (10-K/10-Q) | ✅ **Delayed (daily digest)** | ✅ **Real-time** | `realtime_alerts` flag |
| 8-K coverage | ✕ | ✅ | `eightk_coverage` flag |
| "What changed" dashboard feed | ✅ basic | ✅ full diff | flag/depth |
| Saved summaries | ✅ | ✅ | built |
| Exports (PDF / CSV) | ✕ | ✅ | `can_export` (built) |
| Multi-filing comparison | Basic / limited | ✅ Full (2–5) | `can_compare` (built; tune free allowance) |
| History retention | Recent | Full | `history_retention_days` (new) |
| Portfolio / multi-filing digest | ✕ | ✅ | new (post-v1 ok) |
| Rate limits | Standard | Relaxed | partial (guest quota flag) |

**Where the line sits & why:** free is everything that drives discovery, habit, and word-of-mouth (search, unlimited watchlist, a meaningful summary cap, delayed alerts) so a free user can fully feel — and evangelize — the value; Pro captures *volume, depth, speed (real-time), breadth (8-K), and output (export)* — each a demonstrated willingness-to-pay signal that appears only **after** the user has hit value. Premium-model inference is a paid entitlement, aligning our largest marginal cost with revenue.
</content>
