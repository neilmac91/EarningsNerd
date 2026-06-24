# EarningsNerd → Closed Beta: 12-Week Roadmap

> Roadmap to move EarningsNerd from pre-launch into an active, invite-only closed beta.
> Approach approved by the user (2026-06-23). Each week's work ships as its own reviewed PR off
> `main`; this document is the source-of-truth plan, updated as items complete.
>
> _(Supersedes the prior SEC Data Expansion remediation log — that work is complete and recorded in
> merged PRs #331–#339 + git history.)_

---

## Context

EarningsNerd is feature-complete but **pre-launch**. The goal is to move into an **active, closed
beta** for friends & family who get full **Pro** access **without a credit card**, while still being
routed through the **real production onboarding + Stripe flow** (so we exercise the exact path real
customers will take). The general public must stay out; only people holding our invite stay in.

Four locked product decisions (confirmed with the user before planning):
1. **Access delivery = magic invite link** — one per tester; passes the invite gate *and* pre-applies
   the 100%-off promo at checkout.
2. **Duration = forever coupon + manual revoke at GA** — no surprise mid-beta lockouts.
3. **Invite gate = `InviteCode` table + server-side `REGISTRATION_MODE` flag** — per-user, revocable.
4. **Feedback = new dedicated `/api/feedback` endpoint + table** — isolated from general contact.

### The finding that shapes everything
`WAITLIST_MODE` is enforced **only in the frontend** (`frontend/middleware.ts:52-67`). The backend
register endpoint (`backend/app/routers/auth.py:608-676`) is **completely open** — no allowlist, no
invite check. **Flipping `WAITLIST_MODE=false` would expose registration to the entire public.** The
invite gate therefore *must* be enforced server-side; that is the spine of this roadmap, not the
Stripe change.

---

## Architectural Summary — the "Beta-Pro" access flow

### What does NOT change (verified during recon)
- **Entitlements** (`backend/app/services/entitlements.py:104-136`): `get_plan()` grants Pro on
  subscription **status ∈ {active, trialing}** with **no amount/price floor**. A $0, 100%-off
  `active` subscription already resolves to **Pro**. **Zero changes.**
- **Webhook** (`backend/app/routers/subscriptions.py:247-289`): `apply_checkout_completed` /
  `apply_subscription_upsert` set `status='active'`, `plan='pro'` unconditionally — no amount checks.
  A $0 sub fires the identical event sequence. **Zero changes.**

### What changes (small, surgical)
1. **Stripe Checkout** — `create_checkout_session` (`subscriptions.py:148`):
   - Add `payment_method_collection="if_required"` → **no card collected when total is $0** (the crux
     of "no credit card").
   - Apply the promo **conditionally** — Stripe rejects both in one request (400 "you cannot specify
     both allow_promotion_codes and discounts"): the magic-link path sets
     `discounts=[{"promotion_code": <promo_id>}]`; the manual/self-serve path sets
     `allow_promotion_codes=True`. Never both in the same session.
   - Stripe Dashboard (test + live): a **Coupon** `percent_off=100, duration=forever` + a
     **Promotion Code** (e.g. `FRIENDS2026`), id stored in config as `STRIPE_BETA_PROMO_CODE_ID`.
2. **Invite gate** — new `InviteCode` model + migration; `REGISTRATION_MODE=invite_only|public` flag;
   a server-side check in `auth.register` before user creation; an admin endpoint to mint invites;
   a `send_invite_email()` reusing `resend_service`/`email_service` + the existing hashed-JWT
   magic-link pattern (mirrors email-verification at `auth.py:783-802`).
3. **Frontend onboarding** — `/register` accepts `?invite=<token>`; retire the `/`→`/waitlist`
   redirect in `middleware.ts`; chain magic-link → email-verify → checkout-with-promo-pre-applied.
4. **Feedback** — new `Feedback` model + **authenticated** `/api/feedback` endpoint protected by
   auth + the per-user/per-IP rate limiter (reused from `contact.py`). **No Turnstile** — the endpoint
   is logged-in only, so a CAPTCHA adds redundant security and dashboard layout-shift/friction for no
   gain. A feature-flagged `<FeedbackWidget/>` mounts in the dashboard.
5. **Monitoring** — PostHog beta-funnel events; Sentry release tag + `set_user()` + beta cohort tag.

### The friends-&-family experience
*Click magic link → set password → (email verify) → land in Checkout with promo pre-applied → $0,
no card → Pro.* Still the real production Stripe flow end-to-end.

Aligns with the `stripe-best-practices` skill: Checkout Sessions API, `mode='subscription'`,
signature-verified webhooks (present), idempotency via `StripeEvent` (present), test-mode first.

### Files touched (representative)
| Area | File(s) | Change |
|---|---|---|
| Stripe checkout | `backend/app/routers/subscriptions.py` | `payment_method_collection`, `discounts`/`allow_promotion_codes`, promo config |
| Config | `backend/app/config.py` | `REGISTRATION_MODE`, `STRIPE_BETA_PROMO_CODE_ID`, `INVITE_EXPIRY_HOURS`, `FEEDBACK_ENABLED` |
| Invite model | `backend/app/models/invite.py` (new) + `migrations/` | `InviteCode` table |
| Invite/register | `backend/app/routers/auth.py` | gate check ~648; accept-invite path |
| Invite admin | `backend/app/routers/admin.py` | mint/list/revoke invites |
| Invite email | `backend/app/services/email_service.py` | `send_invite_email()` |
| Feedback | `backend/app/models/feedback.py`, `backend/app/routers/feedback.py`, `backend/app/schemas/feedback.py` (new) | dedicated pipeline |
| PostHog | `backend/app/services/posthog_client.py`, `frontend/lib/analytics.ts` | beta-funnel events |
| Sentry | `backend/main.py`, `frontend/instrumentation*.ts` | release tag, user/cohort context |
| Register UI | `frontend/app/register/page.tsx`, `frontend/middleware.ts` | `?invite=`, retire waitlist redirect |
| Feedback UI | `frontend/components/FeedbackWidget.tsx` (new), `frontend/app/providers.tsx` | mount widget |

> All frontend work follows `frontend/DESIGN_SYSTEM.md` (sage/slate brand, theme-responsive pairs,
> explicit heading colors) and is verified in **both** themes.

---

## Agent Orchestration (keep the main context window clean)

Per CLAUDE.md, research/build is offloaded to `.claude/agents`, with `voltagent` specialists as
second-opinion/overflow. One focused task per subagent.

| Workstream | Primary (`.claude/agents`) | Support / `voltagent` overflow |
|---|---|---|
| Stripe checkout + entitlements | `engineering/backend-developer` | voltagent *Integration Specialist*, *Fintech Architect* (review) |
| Invite gate + DB migration | `engineering/database-specialist` + `engineering/backend-developer` | voltagent *Database Ops* |
| API shape/versioning | `engineering/api-architect` | voltagent *API Designer* |
| Register/invite + feedback UI | `engineering/frontend-developer` | `design/ui-designer`, `design/accessibility-champion`, `design/brand-guardian` |
| Feedback triage pipeline | `product/feedback-synthesizer` | — |
| Monitoring/instrumentation/env | `engineering/devops-automator` | voltagent *Monitoring Specialist*, *Incident Responder* |
| QA / verification | `testing/qa-engineer` + `testing/integration-tester` | voltagent *E2E Specialist*, *API Tester* |
| Security review | `testing/security-auditor` | voltagent *Penetration Tester* |
| Sequencing / dependencies | `project-management/sprint-coordinator` + `project-management/dependency-mapper` | — |

**Orchestration rule:** UI updates and backend DB migrations run as **separate parallel subagents**
in isolated worktrees so a frontend change never blocks a migration (and vice-versa); results are
merged by the sprint-coordinator. Each subagent brief links `frontend/DESIGN_SYSTEM.md` (UI) or the
relevant model/migration files (backend).

---

## 12-Week Timeline

### Phase 0 — Stripe + Invite-Gate foundations

#### Week 1 — Stripe 100%-off scaffolding (test mode) — code complete
- [ ] Create Stripe **test-mode** Coupon (`percent_off=100, duration=forever`) + Promotion Code; record ids.
      *(manual Stripe Dashboard step — then set `STRIPE_BETA_PROMO_CODE_ID` to the promo id.)*
- [x] Add config `STRIPE_BETA_PROMO_CODE_ID` + a Pydantic validator (must be a `promo_…` Promotion
      Code id, not a `co_…` coupon id). *(`REGISTRATION_MODE` / `INVITE_EXPIRY_HOURS` / `FEEDBACK_ENABLED`
      deferred to W2 / W5 to avoid dead config.)*
- [x] `subscriptions.py`: add `payment_method_collection="if_required"` (no-card lever; no change for
      paid checkouts). **Promo application deferred to Week 2**, gated on the user's invite/beta
      eligibility server-side — never a client param (closes a self-grant hole flagged in review).
- [x] Confirm $0 `active` sub → Pro via `entitlements` (status-only, no amount floor) — covered by test.
- [x] Unit tests: `tests/unit/test_checkout_session.py` asserts `if_required`, that no promo params
      are applied yet, the $0→Pro entitlement invariant, and the `promo_…` id validator.
- *Owner:* backend-developer. *Verify:* run the **local promo verification checklist** (below).

#### Week 2 — Invite gate (server-side) + magic-link issuance — code complete (backend)
- [x] `InviteCode` model (`models/invite.py`) + two idempotent SQL migrations (create table; add `is_beta`).
      Config: `REGISTRATION_MODE` (default `public`) + `INVITE_EXPIRY_HOURS`.
- [x] `auth.register` gate: when `invite_only`, require a valid/unexpired/unused invite (email-optional
      binding) → explicit `403` otherwise; runs before account work, rejects uniformly (not an
      enumeration vector); the email-existence opaque response is preserved on the valid-invite path.
- [x] `send_invite_email()` (Resend) + **hashed-token-in-DB** invite (SHA-256, mirrors email-verify;
      not JWT — invites are minted before a user exists). `invite_service.py` mint/validate/redeem.
- [x] Admin endpoints: `POST /api/admin/invites` (mint→link), `GET /api/admin/invites`, `POST
      /api/admin/invites/{id}/revoke`.
- [x] Checkout promo now gated on **server-set `User.is_beta`** (set at redemption, never a client
      param); pairs with the W1 `if_required` lever → $0, no card.
- [x] Tests: invite service (mint/validate/redeem + expiry/revoked/used/email-bound), invite gate
      (public/missing/invalid/single-use/email-match), admin endpoints, checkout discount gating.
      Local gate green: 607 unit+smoke pass, ruff, bandit `-ll`.
- *Owner:* database-specialist + backend-developer. *Support:* api-architect, security-auditor (review).
- *Note:* frontend `/register?invite=` wiring + retiring the `/`→`/waitlist` redirect is **Week 3**.

### Phase 1 — Onboarding flow end-to-end

#### Week 3 — Frontend invite + register UX — code complete (core)
- [x] `/register` reads `?invite=<token>` (Suspense + `useSearchParams`), routes invited users
      straight to the email flow and **hides social signup** (which bypasses the invite gate), shows a
      brand-tinted "you're invited" notice, and passes the token to `register()`. The backend enforces
      validity, so an invalid invite surfaces a clear error.
- [~] Retire `/`→`/waitlist` redirect: **no code change** — it's already env-gated
      (`WAITLIST_MODE !== 'false'`) and `/register` is already allowed, so an invited friend reaches
      it today. "Retiring" it is the deliberate `WAITLIST_MODE=false` env flip at launch (**Week 8**);
      doing it in code now would prematurely expose the marketing site.
- [~] Post-verify → checkout chain: **deferred to launch polish** — the promo auto-applies for
      `is_beta` at checkout (W2), so the explicit chain is optional. (Needs `is_beta` surfaced to the
      client; pairs with a "Claim your free Pro" CTA — Week 9.)
- [x] Design-system compliance: brand-tinted notice, theme-paired tokens, explicit heading colors;
      typecheck + lint + 173 unit tests + `next build` all green. Visual both-theme check on the Vercel
      preview is the final gate.
- *Owner:* frontend-developer. *Support:* ui-designer, accessibility-champion, brand-guardian.
- *Follow-up (backend gap):* in `invite_only` mode the gate is on `/api/auth/register` only — **OAuth
      (Google/Apple) signup bypasses it**, letting the public create free-tier accounts (no `is_beta`,
      so no free Pro). Decide: block new-account OAuth signup in `invite_only`, or accept it for beta.

#### Week 4 — Full path integration + verification
- [ ] Wire magic-link → invite-gate → email-verify → $0 Checkout → webhook → Pro, end to end.
- [ ] Edge cases: expired/used/wrong-email invite, already-registered email, checkout abandon/resume,
      webhook idempotency on the $0 sub.
- [ ] Stripe CLI webhook forwarding locally; assert `is_pro` flips and Copilot/export unlock.
- [ ] E2E test (Playwright) for the happy path + top 3 edge cases.
- *Owner:* integration-tester + frontend-developer. *Gate:* the **local promo verification checklist** passes.

### Phase 2 — Feedback loop & monitoring

#### Week 5 — Dedicated feedback pipeline
- [ ] `Feedback` model + migration; **authenticated** `/api/feedback` endpoint guarded by auth +
      the per-user/per-IP rate limiter from `contact.py` (**no Turnstile** — logged-in only); capture
      `user_id`, `type` (bug/feature/general), page url.
- [ ] `<FeedbackWidget/>` mounted in `providers.tsx`, feature-flagged via `FEEDBACK_ENABLED`,
      visible across the authenticated dashboard; success toast; design-system compliant.
- [ ] Admin/email notification on new feedback (reuse Resend); emit PostHog `feedback_submitted`.
- *Owner:* backend-developer + frontend-developer. *Support:* feedback-synthesizer.

#### Week 6 — PostHog beta funnel + Sentry attribution
- [ ] Add missing events: `signup_completed` (backend), `invite_redeemed`, `first_summary_generated`,
      `trial_started`, `feedback_submitted`; verify distinct-id stitching across signup→activation.
- [ ] PostHog **beta funnel dashboard**: invite_sent → invite_redeemed → signup_completed →
      first_summary_generated → copilot_question → feedback_submitted.
- [ ] Sentry: **release tagging** (git SHA), `set_user()` on auth, **beta cohort tag**, document
      `ENVIRONMENT`/release env vars in deploy config.
- *Owner:* devops-automator. *Support:* infrastructure-maintainer.

### Phase 3 — Hardening & QA

#### Week 7 — Security + full QA sweep
- [ ] Security audit: invite-token entropy/expiry/replay, promo-abuse (single-use binding), gate
      bypass attempts, rate limits, no PII in analytics, webhook signature paths.
- [ ] QA matrix: unit + integration + smoke + E2E green; `pytest tests/`, `npm run test`, `test:e2e`.
- [ ] Negative tests: public registration blocked in `invite_only`; revoked invite denied.
- *Owner:* security-auditor + qa-engineer. *Support:* voltagent Penetration Tester (overflow).

#### Week 8 — Production config + go-live readiness
- [ ] Create Stripe **live-mode** coupon/promo; set secrets in Google Secret Manager (Cloud Run).
- [ ] Set `REGISTRATION_MODE=invite_only`, `WAITLIST_MODE=false`, `FEEDBACK_ENABLED=true` in prod.
- [ ] `python3 scripts/deploy_check.py`; verify `/health/detailed`, `/metrics`, Sentry release,
      PostHog events flowing from staging.
- [ ] Beta runbook: how to mint/revoke invites, read the funnel, triage Sentry, rotate the promo.
- *Owner:* devops-automator. *Support:* knowledge-curator (runbook).

### Phase 4 — Closed beta launch & iterate

#### Week 9 — Soft launch (cohort 1: 5–10 people)
- [ ] Mint invites for the first cohort; send magic links; confirm each reaches Pro with no card.
- [ ] Daily triage from PostHog funnel + Sentry (per-user) + feedback inbox; log issues to `tasks/`.
- *Owner:* sprint-coordinator. *Support:* feedback-synthesizer.

#### Week 10 — Iterate on cohort-1 signal
- [ ] Fix top bugs (Sentry-ranked) and top feedback themes; ship fixes; expand to cohort 2.
- [ ] Track activation: % reaching first summary, copilot use, drop-off points.
- *Owner:* backend/frontend-developer as triaged. *Support:* feature-prioritizer (RICE).

#### Week 11 — Stabilize & deepen
- [ ] Address funnel drop-offs surfaced in W10; performance pass on hot paths (summary stream).
- [ ] Confirm monitoring catches regressions before testers report them (proactive > manual).
- *Owner:* qa-engineer + performance-tester.

#### Week 12 — Beta retro & GA-readiness
- [ ] Retro: activation/retention metrics, bug burn-down, feedback synthesis.
- [ ] Decide GA conversion path (revoke forever-coupon → real Checkout; honor early-supporter offer).
- [ ] GA-readiness assessment + go/no-go; draft GA roadmap.
- *Owner:* sprint-coordinator + feature-prioritizer. *Support:* feedback-synthesizer.

---

## Local Promo-Code Verification Checklist (planning-phase done-gate)

Run end-to-end against **Stripe test mode** before marking the *planning phase* complete:

- [ ] Stripe test Coupon (`percent_off=100, duration=forever`) + Promotion Code created; id in `.env`.
- [ ] Backend boots; `REGISTRATION_MODE=invite_only`, promo id and Stripe test keys set.
- [ ] Mint an invite (admin endpoint) → receive a magic link with an invite token.
- [ ] Public `POST /api/auth/register` **without** a valid invite is rejected; **with** the invite succeeds.
- [ ] Complete email verification (local token).
- [ ] `POST /api/subscriptions/create-checkout-session` with the magic-link path returns a Checkout URL
      with the promo **pre-applied** and **no card field** (because `payment_method_collection=if_required`).
- [ ] Complete the $0 checkout; forward webhooks locally (`stripe listen`/CLI):
      `checkout.session.completed` + `customer.subscription.created` received and idempotent on retry.
- [ ] `GET /api/subscriptions/subscription` → `is_pro=true`, `plan="pro"`, `status="active"`;
      `entitlements.get_entitlements(user)` returns `_PRO` (unlimited summaries, export, copilot).
- [ ] No real card was entered at any point.
- [ ] Submit a test bug via `<FeedbackWidget/>` → row in `feedback` table + `feedback_submitted` in PostHog.
- [ ] Sentry test error is tagged with the beta user and a release/SHA.
- [ ] `pytest tests/` and `npm run test` green; new flow covered by tests.

---

## Deliverables recap
1. **12-week, week-by-week roadmap** (above).
2. **Architectural-changes summary** for the Beta-Pro flow (above).
3. **Local promo-code verification checklist** (above).
4. **Agent-orchestration mapping** assigning workstreams to `.claude/agents` + `voltagent` (above).

> Scope note: this roadmap is the **plan**. It does **not** implement Weeks 1–12 — those ship as
> their own reviewed PRs off `main`.

## Review log
- _Pending implementation (filled per CLAUDE.md as weeks complete)._
