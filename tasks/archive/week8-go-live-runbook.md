# Week 8 — Closed-Beta Go-Live Runbook

> Take EarningsNerd from "hardened + deployed" (Weeks 1–7 done) to **friends-&-family receiving
> invite links and reaching Pro for $0 through the real production Stripe flow**.
>
> Conventions: `<...>` = a value you fill in. Commands target project **earnings-nerd**, region
> **us-west1**, service **earningsnerd-backend**. Run them in Cloud Shell. Secrets live in Google
> Secret Manager and are mounted as Cloud Run env vars; non-secret config is set with
> `--update-env-vars` (merge semantics — it never clobbers vars you don't list).

---

## Phase 0 — Pre-flight (confirm current state, ~5 min)

```bash
# What image + env is live right now?
gcloud run services describe earningsnerd-backend --region=us-west1 \
  --format="yaml(spec.template.spec.containers[0].image, spec.template.spec.containers[0].env)"

# What secrets are wired in?
gcloud run services describe earningsnerd-backend --region=us-west1 \
  --format="yaml(spec.template.spec.containers[0].volumeMounts, spec.template.spec.containers[0].env)" | grep -i secret -A2
gcloud secrets list
```

- [ ] Note the current `REGISTRATION_MODE` (the server-side gate may already be `invite_only`).
- [ ] Note the current `STRIPE_*` values — they are almost certainly **test-mode** today.
- [ ] Confirm `TRUSTED_PROXY_HOPS=1` is present (set in Week 7).
- [ ] `SENTRY_DSN`, `POSTHOG_API_KEY` present (monitoring live).

**Verified live state (2026-06-24):** image `:8213c1f` (Week 7 ✅), `REGISTRATION_MODE=invite_only` ✅,
`TRUSTED_PROXY_HOPS=1` ✅, `SENTRY_RELEASE` + `SENTRY_DSN` ✅. Stripe is **test mode**
(`STRIPE_BETA_PROMO_CODE_ID=promo_1Tlnc…`). Stripe keys + **price ids + publishable key are stored as
secrets** (Secret Manager), not plain env. **Two gaps found:**
- ⚠️ **`REVERSE_TRIAL_ENABLED=true`** in prod — see **Decision 2**. This likely should be `false`: it
  short-circuits the intended invite→$0-checkout→**forever** Pro flow (friends instead get a 7-day
  trial that **expires**, dropping them off Pro unless they checkout), and it activates the audit's
  reverse-trial re-grant vector (bounded by `invite_only`, but live).
- ⚠️ **`POSTHOG_API_KEY` is NOT set** on the backend → the Week 6 beta-funnel **backend** events
  (`signup_completed`, `invite_redeemed`, `subscription_activated`, `generation_*`,
  `feedback_submitted`) are **no-ops** in prod, so the funnel won't populate. Set it in Phase 2.

> ⚠️ **Decision 1 — does the public marketing site stay gated?**
> Two independent gates: `REGISTRATION_MODE=invite_only` (backend — blocks signup without an invite)
> and `WAITLIST_MODE` (frontend/Vercel — redirects `/` → `/waitlist`).
> - **Recommended for a *true* closed beta:** keep **`WAITLIST_MODE=true`**. The public hitting
>   earningsnerd.io sees the waitlist; invited friends use their direct `/register?invite=<token>`
>   link (the middleware allows it). The general public never reaches the app.
> - **Open-preview posture:** set `WAITLIST_MODE=false` — the marketing site/app is publicly
>   browsable, but registration is still invite-gated and Pro still needs `is_beta`. Flip this only
>   when you want the site visible (this is really a GA-adjacent step).
>
> The rest of this runbook assumes the **recommended** posture (waitlist stays up). One line changes
> if you choose otherwise (Phase 4).

> ⚠️ **Decision 2 — reverse trial vs. forever coupon.** Prod currently has `REVERSE_TRIAL_ENABLED=true`,
> which is inconsistent with the chosen beta model ("forever coupon + manual revoke at GA").
> - **Recommended — `false`:** friends go invite → $0 checkout (100%-off **forever**) → Pro that never
>   expires. Matches the plan; also closes the reverse-trial re-grant vector.
> - **Keep `true`:** friends get instant Pro for **7 days with no checkout at all**, but it **expires**
>   — they must then complete the $0 checkout or silently lose Pro. Simpler day-1, worse day-8.
>
> The two also overlap awkwardly if both are on (a friend gets a trial *and* is `is_beta`, so they
> hit checkout only after the trial lapses). **Decided 2026-06-24: OFF** — set `REVERSE_TRIAL_ENABLED=false`.

---

## Phase 1 — Stripe LIVE mode (Stripe Dashboard, ~20 min)

Toggle the dashboard to **Live mode** (top-right) and do all of the following in live mode:

1. **Products & Prices** — confirm/create the live Pro product with a **monthly** and **yearly**
   recurring price. Copy the live price ids → `price_…(monthly)`, `price_…(yearly)`.
2. **Coupon** — Products → Coupons → New: **`percent_off = 100`**, **`duration = forever`**, name e.g.
   `Friends & Family`.
3. **Promotion Code** — attach a code to that coupon (e.g. `FRIENDS2026`). Copy its **id** — it starts
   with **`promo_`** (NOT the human code, NOT the `co_…` coupon id). This is `STRIPE_BETA_PROMO_CODE_ID`.
   *(The backend validator rejects anything that isn't `promo_…`, so a wrong paste fails fast.)*
4. **API keys** — Developers → API keys: copy the live **Secret key** (`sk_live_…`) and **Publishable
   key** (`pk_live_…`).
5. **Webhook endpoint** — Developers → Webhooks → Add endpoint:
   - URL: `https://api.earningsnerd.io/api/subscriptions/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.created`,
     `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`,
     `customer.subscription.trial_will_end`.
   - After creating, reveal the **Signing secret** (`whsec_…`) → this is `STRIPE_WEBHOOK_SECRET`.

Checklist:
- [ ] live `price_…` monthly + yearly
- [ ] coupon 100%-off / forever
- [ ] promotion code id `promo_…`
- [ ] `sk_live_…`, `pk_live_…`
- [ ] webhook endpoint + `whsec_…`

---

## Phase 2 — Backend secrets + config (Cloud Shell, ~10 min)

**2a. Add live-value versions to the existing Stripe secrets** (all five are already mounted at
`:latest`, so a new version is picked up on the next revision):

```bash
printf '%s' 'sk_live_<...>'  | gcloud secrets versions add STRIPE_SECRET_KEY       --data-file=-
printf '%s' 'pk_live_<...>'  | gcloud secrets versions add STRIPE_PUBLISHABLE_KEY  --data-file=-
printf '%s' 'whsec_<...>'    | gcloud secrets versions add STRIPE_WEBHOOK_SECRET   --data-file=-
printf '%s' 'price_<...>'    | gcloud secrets versions add STRIPE_PRICE_MONTHLY_ID --data-file=-
printf '%s' 'price_<...>'    | gcloud secrets versions add STRIPE_PRICE_YEARLY_ID  --data-file=-
```

**2b. Roll a new revision + set the non-secret config** (this both picks up the `:latest` secret
versions from 2a and sets the env; `--update-env-vars` merges so it won't touch other vars):

```bash
gcloud run services update earningsnerd-backend --region=us-west1 \
  --update-env-vars=STRIPE_BETA_PROMO_CODE_ID=promo_<...>,REGISTRATION_MODE=invite_only,REVERSE_TRIAL_ENABLED=false,POSTHOG_API_KEY=<phc_...>,POSTHOG_HOST=https://us.i.posthog.com
```

> Notes
> - Stripe **secret key, publishable key, webhook secret, and both price ids are stored as secrets**
>   (verified from prod) — so they go through 2a (new secret version), not `--update-env-vars`.
> - `STRIPE_BETA_PROMO_CODE_ID` is just an id (not sensitive) → env var is fine.
> - `POSTHOG_API_KEY` = the same `phc_…` project key as the frontend's `NEXT_PUBLIC_POSTHOG_KEY`
>   (it's a client-style ingest key, env var is fine) — sets it so the backend funnel events fire.
> - `REVERSE_TRIAL_ENABLED=false` per **Decision 2** (omit if you decide to keep trials).
> - `REGISTRATION_MODE` is now a **fail-closed enum** — a typo crashes the new revision at startup and
>   Cloud Run keeps serving the old healthy one (safe), so you'll see an obvious deploy error rather
>   than a silently-open signup.

- [ ] secrets rotated to live
- [ ] price ids + promo id set
- [ ] `REGISTRATION_MODE=invite_only`

---

## Phase 3 — Frontend (Vercel) env (~5 min)

In the Vercel project → Settings → Environment Variables (Production):

- [ ] `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = pk_live_…`
- [ ] Confirm `NEXT_PUBLIC_API_BASE_URL = https://api.earningsnerd.io`
- [ ] Confirm `NEXT_PUBLIC_SENTRY_DSN`, `NEXT_PUBLIC_POSTHOG_KEY` set
- [ ] `NEXT_PUBLIC_ENABLE_FEEDBACK_WIDGET` — leave unset/`true` (the beta feedback widget is on by
      default; no action)
- [ ] **`WAITLIST_MODE`** — per Decision 1, leave **`true`** for a closed beta (or `false` to open the
      site). This is a server-side var (NOT `NEXT_PUBLIC_`).
- [ ] **Redeploy** the frontend so the new env vars take effect (Vercel → Deployments → Redeploy, or
      push any commit).

---

## Phase 4 — Verify BEFORE inviting anyone (~15 min)

Run the pre-deploy validator + health checks:

```bash
# From a checkout of the repo (or Cloud Shell with the backend image), against prod config:
python3 backend/scripts/deploy_check.py        # env vars, deps, config sanity
curl -s https://api.earningsnerd.io/health
curl -s https://api.earningsnerd.io/health/detailed   # DB + circuit breaker healthy
```

- [ ] `/health` → `{"status":"healthy"}`; `/health/detailed` DB healthy.
- [ ] Sentry: trigger a test error while logged in as a beta user → the Sentry issue shows the user
      id, **`beta: true`** tag, and a **`release`** = the deployed SHA.
- [ ] PostHog: confirm `signup_completed` / `subscription_activated` events arrive (you'll see them in
      the end-to-end test below).

**End-to-end live smoke test (one real $0 run — costs nothing):**
1. As an admin, mint yourself an invite: `POST /api/admin/invites` (see Phase 6). Use a *fresh* email.
2. Open the magic link `…/register?invite=<token>` → set a password → complete email verification.
3. Go to upgrade/checkout → **the Stripe Checkout page shows the promo pre-applied, total $0, and NO
   card field** (because `payment_method_collection=if_required` + the 100%-off discount).
4. Complete checkout → Stripe fires the live webhook → `GET /api/subscriptions/subscription` shows
   `is_pro=true`, `plan="pro"`, `status="active"`; Copilot/export unlock.
5. Submit a test note via the in-app **Feedback** widget → row lands in the `feedback` table + an admin
   email + a `feedback_submitted` PostHog event.

- [ ] $0 checkout, no card, → Pro, end-to-end on **live** Stripe.
- [ ] Webhook idempotent (Stripe will retry; entitlement doesn't double-apply).

> If anything fails here, **stop** — you have not yet invited real people. Fix and re-verify.

---

## Phase 5 — Cutover

If Phase 2 already set `REGISTRATION_MODE=invite_only`, the backend gate is live. Final confirmations:

- [ ] Public `POST /api/auth/register` **without** an invite → **403**. (Quick check:
      `curl -s -o /dev/null -w "%{http_code}" -X POST https://api.earningsnerd.io/api/auth/register -H 'content-type: application/json' -d '{"email":"nope@example.com","password":"<12+chars>"}'` → `403`.)
- [ ] `WAITLIST_MODE` set per Decision 1 (frontend redeployed).
- [ ] Known/accepted: OAuth (Google/Apple) signup still creates **free-tier** accounts in invite-only
      mode — never Pro (Pro needs a redeemed invite). Documented; revisit before public GA.

---

## Phase 6 — Mint & send the first cohort (5–10 people)

```bash
# Get an admin token first (log in as your admin user). Then per invitee:
TOKEN='<admin_access_token>'
curl -s -X POST https://api.earningsnerd.io/api/admin/invites \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"email":"friend@example.com","expires_in_hours":168,"send_email":true}'
# → returns {id, invite_link, email, expires_at}. The raw token is shown ONCE (only its hash is stored).
```

- [ ] `send_email:true` emails the magic link via Resend; or copy `invite_link` and send it yourself.
- [ ] List/track: `GET /api/admin/invites` (status: pending / used / revoked / expired).
- [ ] Revoke if needed: `POST /api/admin/invites/<id>/revoke`.

---

## Rollback (if go-live goes wrong)

- **Bad Stripe config / checkout broken:** revert the env update — re-run the Phase 2 `update` with the
  previous test ids/secret versions, or `gcloud run services update-traffic earningsnerd-backend
  --region=us-west1 --to-revisions=<previous-revision>=100` to instantly route back to the last good
  revision.
- **Gate misbehaving:** `--update-env-vars=REGISTRATION_MODE=invite_only` is the safe state (public
  blocked). Never set it to a non-enum value (the validator will reject it).
- **Need to pause the beta entirely:** revoke outstanding invites (`/api/admin/invites/<id>/revoke`)
  and/or keep `WAITLIST_MODE=true`. Existing Pro users keep access (forever coupon).
- Cloud Run keeps prior revisions; traffic reroute is instant and lossless.

---

## Day-2 operations (the standing beta runbook)

| Task | How |
|------|-----|
| **Invite a tester** | `POST /api/admin/invites {email, send_email:true}` |
| **See invite status** | `GET /api/admin/invites` (pending/used/revoked/expired) |
| **Revoke an invite** | `POST /api/admin/invites/{id}/revoke` |
| **Read the activation funnel** | PostHog → build the funnel from `tasks/beta-monitoring.md` (invite_redeemed → signup_completed → generation_succeeded → copilot_question_asked → feedback_submitted) |
| **Triage errors** | Sentry → filter `beta:true`; each issue carries the user id + release SHA |
| **Read feedback** | `feedback` table + the admin notification emails; `feedback_submitted` in PostHog |
| **Rotate the promo at GA** | Create a new coupon/promo, update `STRIPE_BETA_PROMO_CODE_ID`; existing forever-coupon subs are untouched until you migrate them |

---

## Carry-over security items (from the Week 7 sweep — `tasks/security-audit-week7.md`)

- [ ] **Triage the 39 Dependabot alerts** (17 high) before/around go-live (`npm audit` / `pip-audit`).
- [ ] Before ever setting `REVERSE_TRIAL_ENABLED=true`, add a persistent trial ledger (re-grant churn).
- [ ] Rotate the `appuser` DB password if it was ever pasted in plaintext.

## Done-gate for Week 8
Live $0 checkout → Pro verified end-to-end on live Stripe; public registration 403s without an invite;
Sentry release+cohort and PostHog funnel populating; first cohort invited and each confirmed reaching
Pro with no card.
