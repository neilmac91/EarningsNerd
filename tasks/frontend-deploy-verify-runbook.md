# Frontend deploy & verify runbook

> Written after a stale-deploy incident: the entire "Ask this Filing" Copilot (PRs #349–#373) was
> merged to `main` and green in CI + Vercel **previews**, but production (`earningsnerd.io`) kept
> serving an older build (~PR #348), so the feature was invisible to users. **Merged ≠ shipped.**

## 0. TL;DR

- The frontend deploys to **Vercel via Git integration** (no GitHub Action does it — see `.github/workflows`).
- Vercel builds a **preview** per PR branch (the green "Ready" bot comments). Production is a **separate**
  promotion of the **Production Branch** (`main`). A green preview does **not** mean production updated.
- Feature flags live in `frontend/lib/featureFlags.ts` and default **OFF**. Production values come from
  `frontend/vercel.json` `env` (version-controlled) and/or the Vercel dashboard env vars.

## 1. Symptom → is production stale?

Run the automated check (works against any deployed URL):

```bash
cd frontend
SMOKE_BASE_URL=https://earningsnerd.io npx playwright test prod-smoke
```

- **Passes** → production is serving the Copilot (current-ish `main`).
- **Fails** (no "Ask this Filing" launcher on `/filing/3`) → production is **stale** (older than PR #350).

Manual tell: open `https://earningsnerd.io/filing/3`. A mint **"Ask this Filing"** button should sit at the
bottom-right. The notification bell (top-right) shipped in #348; if the bell is present but the launcher
is not, production is pinned between #348 and #350.

## 2. Fix a stale production deploy (Vercel dashboard — manual)

1. **Vercel → project → Deployments.** Note the latest **Production** deployment's commit + timestamp.
   If it's far behind `origin/main`, that's the problem.
2. **Settings → Git.** Confirm **Production Branch = `main`** and that "Automatically deploy" on push is
   enabled. (If the production branch is something else, or auto-deploy is paused, that's the root cause.)
3. **Promote `main`:** either redeploy the latest `main` (Deployments → ⋯ → **Redeploy**, *uncheck* "use
   existing build cache" if a build is suspected stale) or push a trivial commit to `main`.
4. Re-run the smoke check in §1. It should pass.

If the production **build itself fails** (it shouldn't — previews build the same code), open the failed
deployment's build logs; fix forward on `main`.

## 3. Feature flags (built features that ship OFF by default)

Defined in `frontend/lib/featureFlags.ts`, read from `NEXT_PUBLIC_*` env at **build** time. Set them in
`frontend/vercel.json` `env` (preferred — version-controlled, auditable) or the Vercel dashboard.

| Env var | Feature | Repo default | Recommendation |
|---|---|---|---|
| `NEXT_PUBLIC_ENABLE_SECTION_TABS` | Tabbed summary sections | **ON** (set in vercel.json) | Keep on — pure UI, tested. |
| `NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS` | Revenue/Net-income charts | **ON** (set in vercel.json) | Keep on — additive, has an error boundary. |
| `NEXT_PUBLIC_ENABLE_QUALITY_BADGE` | Honest "Full/Partial" quality badge | OFF | **Recommended ON** (on-strategy trust signal) — but it also **stops client-side stripping of internal failure notices**, so *degraded* summaries show raw notices. Preview a known-degraded summary before enabling. |
| `NEXT_PUBLIC_EXAMPLE_FILING_ID` | Homepage "see an example" deep-links to a pre-generated filing | unset → `/company/AAPL` | Recommend `"3"` (the live Apple example) for instant activation. |
| `NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY` | Form 4 insider panel (company page) | OFF | **Leave OFF** until validated — backend does a slow live SEC EDGAR fan-out (~75s ceiling). |
| `NEXT_PUBLIC_ENABLE_CALENDAR` | Dashboard earnings calendar | OFF | Enable **only after** `FMP_API_KEY` is provisioned on the backend (else empty). |
| `NEXT_PUBLIC_ENABLE_APPLE_SIGNIN` | "Continue with Apple" button | OFF | Leave OFF until the Apple backend exchange is wired (else 404). |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Cloudflare Turnstile bot defense | unset | Set only with the matching backend `TURNSTILE_SECRET_KEY`. |

To enable a flag, add it to `frontend/vercel.json` `env` and redeploy:

```json
"env": {
  "NEXT_PUBLIC_ENABLE_QUALITY_BADGE": "true"
}
```

## 4. Post-deploy verification checklist

Automated:

```bash
cd frontend && SMOKE_BASE_URL=https://earningsnerd.io npx playwright test prod-smoke
```

Manual (on `https://earningsnerd.io/filing/3`):
- [ ] Bottom-right **"Ask this Filing"** launcher is visible (anonymous or free user).
- [ ] Click it → free user sees the value-prop teaser + **Upgrade to Pro** (opens the contextual modal).
- [ ] As a **Pro** user on desktop → opening it shows the side-by-side research-desk pane with
      **[Answer · Filing]** tabs; ⌘K opens it; asking a question streams a grounded answer with `[n]`/`[F#]`
      citation chips; clicking a citation highlights the passage in the in-app **Filing** tab.
- [ ] Summary page shows tabbed sections (if `ENABLE_SECTION_TABS`) and charts (if `ENABLE_FINANCIAL_CHARTS`).

## 5. Prevent recurrence

- **Smoke check**: `frontend/tests/e2e/prod-smoke.spec.ts` (opt-in via `SMOKE_BASE_URL`). Consider wiring a
  **scheduled** GitHub Action (e.g. hourly) that runs it against production and alerts on failure, so a
  stale/failed production promotion is caught automatically instead of by a user.
- **Centralized flags**: keep production feature-flag values in `frontend/vercel.json` (in the repo) rather
  than only in the Vercel dashboard, so what's enabled in production is reviewable in PRs.
- **Definition of "shipped"**: a feature is shipped when the **production** smoke check passes — not when the
  PR merges or the preview is green.
