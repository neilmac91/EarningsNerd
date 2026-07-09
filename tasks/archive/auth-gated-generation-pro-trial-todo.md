# Auth-gated generation + 7-day card-required Pro trial

**STATUS: implemented; backend gate green (ruff + bandit + 1612 pytest); frontend gate green
(eslint --max-warnings 0, tsc, 397 vitest, build, DS legacy-color grep clean); adversarial
review pass run before push (findings triaged below in PR).**

**Goal:** (1) an account is required to generate any NEW filing summary (no anonymous generation);
(2) free accounts generate until the existing 5/month quota; (3) Pro monthly checkout carries a
7-day card-required Stripe trial (card upfront, cancel anytime ≤7d at no charge, auto-charged day 8).

**Owner decisions (2026-07-09, via AskUserQuestion):**
- Trial = **card-required Stripe trial** on Pro **monthly only** (supersedes the documented no-card
  reverse-trial strategy in `docs/RESEARCH_SYNTHESIS.md` / `docs/IMPLEMENTATION_PLAN.md` Q3;
  `REVERSE_TRIAL_ENABLED` stays off, code stays dormant).
- **Cached summaries stay publicly viewable** (SEO + homepage example); only NEW generation gates.
- Funnel = **register → login → back** via `?redirect=` threading; email verification stays
  required only for checkout (unchanged).
- Free quota stays **5/month** (already built; no entitlements change).

**Rule #6 contract change (pre-approved via this plan check-in; document in PR body):**
`test_summary_stream_contract.py` drives `generate-stream` anonymously. Requiring auth is a
deliberate SSE-contract change — the test is re-seated to an authenticated caller in the same PR.
`test_guest_quota_route.py` is rewritten to assert the new behavior (anon → 401).

## Load-bearing facts (from 8-agent investigation, cross-verified by hand)

1. **One anonymous LLM surface.** `POST /api/summaries/filing/{id}/generate-stream`
   (`summaries.py:124`, dep `get_current_user_optional` at :131, docstring "guests allowed").
   All other LLM surfaces (copilot ask-stream, analysis stream, force-regen) are already gated.
2. **Quota gate lives in the single orchestrator** and is skipped for guests:
   `summary_pipeline.py:260` `if current_user:` → `check_usage_limit` (5/mo via entitlements);
   `:279-280` logs "Guest user access" and proceeds unmetered. Fix at the ROUTER boundary only —
   `stream_filing_summary`'s `current_user=None` branch must survive for the cron/admin drain
   (`generate_summary_background`) per non-negotiable rule #1.
3. **Cached-view path is already public and separate.** `GET /api/summaries/filing/{id}`
   (`summaries.py:445`, no auth dep) serves cached reads; the frontend only POSTs generate-stream
   when `!hasSummaryContent` (`useSummaryGeneration.ts:208-223`). Gating the POST does not hide
   cached content.
4. **Frontend has a guest-retry that would defeat the gate:** on 401, `generateSummaryStream`
   re-POSTs with `credentials:'omit'` (`summaries-api.ts:267-278`) — must delete.
   Plus an auth race: auto-generate fires before `/me` resolves; the hook gets only
   `Boolean(currentUser)`, not the query's settled state (`page-client.tsx:46-51`).
5. **Checkout trial trap (confirmed):** `payment_method_collection="if_required"`
   (`subscriptions.py:180`) + a trial ($0 due now) ⇒ Stripe collects NO card (this pairing is what
   the $0 beta path relies on — `week8-go-live-runbook.md:171-172`). Trial cohort needs
   `payment_method_collection="always"` + `subscription_data.trial_period_days` +
   `trial_settings.end_behavior.missing_payment_method="cancel"`.
6. **Webhook/entitlements lifecycle already trial-correct.** `trialing ∈ ACTIVE_STATUSES` grants
   Pro with `trial_end` expiry backstop (`entitlements.py:42,125-144`); `subscription.updated`
   flips trialing→active on day-8 invoice (no `invoice.paid` handler needed);
   `subscription.deleted` mid-trial downgrades cleanly; `trial_will_end` is analytics-only (fine).
   `apply_checkout_completed` hardcodes `status="active"` (`subscription_sync.py:101`) — brief
   wrong-status window for trial checkouts that converges on the next `subscription.created`
   event; NOT changed this PR (that test IS rule-#6-locked; converging behavior is acceptable).
7. **`test_checkout_session.py` is NOT contract-locked** (a checkout test, not a webhook test),
   but `test_payment_method_collection_is_if_required` asserts `if_required` on every session —
   update to cohort-aware.
8. **`?redirect=` exists on /login only** (`app/login/page.tsx:62-67`, with safe-internal-path
   checks); `/register` reads only `?invite` and routes to `/check-email` with no redirect.
9. **Marketing copy contradicts the target:** hero (`app/page.tsx:143`) + `CtaBanner` say
   "Your first summary is free. No signup needed." Paywall moment today = generic "Generation
   interrupted" + Retry (`StreamingSummaryDisplay.tsx:338-353`); only analytics fire.
10. **Trial abuse:** no repeat-trial ledger exists (security-audit-week7 I1 requires one before
    enabling the *reverse* trial — which stays off). Card requirement + Stripe Radar is the
    accepted deterrent for the card trial; revisit if abuse appears.

## Plan

### Backend — require account to generate
- [x] `summaries.py` `generate_summary_stream`: dep `get_current_user_optional` →
      `get_current_user`; delete the guest daily-quota block (:225-247); simplify
      `rate_limit_key` (:149) and telemetry `distinct_id` (:256-258) to per-user forms.
      Keep the force-regen Pro check (now on a guaranteed user). Do NOT touch the pipeline.
- [x] Remove dead guest machinery: `app/services/guest_quota.py`, `GuestDailyUsage` model +
      its writes, `ENABLE_GUEST_DAILY_QUOTA` / `GUEST_DAILY_SUMMARY_LIMIT` settings, and the
      `guest_daily_usage` migration stays as-is (idempotent, table simply goes unused — no
      destructive migration). Sweep for other importers first.
- [x] Rule #6 contract change: re-seat `test_summary_stream_contract.py` to an authenticated
      caller (drop `_guest_headers`/`current_user=None` seams); document in PR body.
- [x] Rule #12 gates: (a) test anonymous POST generate-stream → 401; (b) test Free user is served
      until `FREE_TIER_SUMMARY_LIMIT` then gets the paywall SSE error (extend/keep the existing
      expired-trial gating spec); rewrite `test_guest_quota_route.py` accordingly.
- [x] Audit `test_funnel_telemetry.py`, `summary_stream_harness.py`, performance suite for
      guest assumptions.

### Backend — 7-day card trial on Pro monthly
- [x] `config.py`: add `PRO_TRIAL_DAYS: int = 7` (0 disables; document in
      `docs/CONFIGURATION.md`). Do NOT reuse `REVERSE_TRIAL_DAYS`.
- [x] `create_checkout_session`: for the MONTHLY price and non-beta cohort with
      `PRO_TRIAL_DAYS > 0`: `subscription_data={"trial_period_days": ...,
      "trial_settings": {"end_behavior": {"missing_payment_method": "cancel"}}}` and
      `payment_method_collection="always"`. Beta $0 path keeps `if_required` + no trial.
      Yearly: no trial.
- [x] Update `test_checkout_session.py` (not locked): cohort-aware `payment_method_collection`
      + trial kwargs assertions (monthly trial / yearly no-trial / beta unchanged).
- [x] No webhook or entitlements changes (lifecycle verified trial-correct; see fact 6).

### Frontend — signup gate + funnel
- [x] Delete the guest-retry-on-401 block (`summaries-api.ts:267-278`); classify 401 as
      non-retryable auth error (already matched by `isNonRetryableStreamError`).
- [x] Thread auth-resolved state: `page-client.tsx` passes the `/me` query's settled state into
      `useSummaryGeneration`; auto-generate only when `authResolved && isAuthenticated`.
      Remove the `NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY` POC flag entirely (auth is now always
      required — flag removal IS the structural gate; sweep `.env.local.example`, Vercel docs).
- [x] Signup gate UI: when `!hasSummaryContent && authResolved && !isAuthenticated`, render a
      DS-compliant "Create a free account to read this analysis" card (5 free/month + 7-day Pro
      trial enticement) with CTAs `/register?redirect=/filing/{id}` and login link. Cached
      summaries keep rendering for guests (branch order: cached view FIRST).
- [x] `?redirect=` threading: `/register` captures it (same safe-internal-path validation as
      login) → `/check-email` → `/verify-email` → `/login?redirect=…` → back to the filing.
- [x] Paywall moment: branch `StreamingSummaryDisplay` on `isPaywallStreamError` → upgrade card
      ("You've used your 5 free summaries this month — start your 7-day Pro trial") linking to
      `/pricing`, instead of the generic error+Retry.
- [x] Pricing page (monthly card): "7-day free trial" badge, CTA "Start 7-day free trial",
      "cancel anytime — you won't be charged" microcopy, FAQ entry (card required, charged day 8).
      Keep beta/trialing/paid CTA branches.
- [x] Copy sweep: hero + `CtaBanner` "no signup needed" → signup-first + trial framing; register
      subhead keeps "5 free AI summaries a month" (still true) + trial mention.
- [x] Tests: hook-level spec (`summaryAuthGate.spec.tsx`: guest + no cache ⇒ no generate call;
      unresolved auth ⇒ no fire; authed ⇒ fires; direct guest call refused). The planned
      guest-sees-gate e2e was consciously DROPPED: CI e2e runs with no backend, the filing query
      never resolves, and the spec would unconditionally skip — zero signal; the hook gate is the
      machine enforcement. Confirmed `prod-smoke.spec.ts` (cached `/filing/3`) and
      `filing-page-renders.spec.ts` (asserts h1/no-tabs only) stay green under the gate.

### Verify (before done)
- [x] Backend gate: `ruff check . && bandit -r app -ll && python -m pytest`.
- [x] Frontend gate: `npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run &&
      npm run build`; DESIGN_SYSTEM legacy-color grep returns nothing.
- [x] Manual Stripe test-mode checklist for the owner (documented in PR body): monthly checkout
      collects card + shows trial, sub lands `trialing`, portal cancel ≤7d → no charge +
      downgrade, day-8 charge → `active` (clock advance).

**Out of scope (deliberate):** trial-abuse ledger (card requirement is the deterrent; revisit on
abuse), `trial_will_end` reminder email (Phase-2 notification system), dunning emails,
`apply_checkout_completed` trial-awareness (locked test; converging behavior acceptable),
dropping the `guest_daily_usage` table.
