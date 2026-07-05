# Homepage Redesign v2 — Review, Critique, and Superseding Plan

*Written 2026-06-10. Supersedes the "Homepage Redesign Plan" in `tasks/todo.md`
(dated 2026-02-05, marked "AWAITING APPROVAL"). Review conducted read-only against
the live codebase and the shipped activation work (PRs #236/#237, Q1–Q8 + S1–S5).*

---

## 1. Verdict & Thesis

**Verdict: RE-SCOPE.** Do not "approve" the v1 plan — it already shipped, in full,
the same day it was written (commit `26df0ac`, 2026-02-05: "Redesign homepage:
dark-first premium layout inspired by Stocktwits"). The `AWAITING APPROVAL` status
in `tasks/todo.md` is stale documentation of completed work, not a pending proposal.

**Thesis:** The homepage's problem in June 2026 is not visual polish — v1 delivered
that. The problems are that the redesigned homepage (a) **is unreachable** (every
visitor is 307-redirected to `/waitlist`), (b) **tells lies** (fabricated trust
metrics, wrong financial figures in the hero mockup), (c) **optimizes the wrong
action** (a registration CTA dominates a product that requires no registration to
deliver value), and (d) **is unmeasured** (zero activation-funnel events exist).
v2 is therefore a truth-, reachability-, funnel-, and measurement-focused re-scope
— not another coat of paint.

---

## 2. Plan-vs-Reality Delta Table

Every item verified against the working tree at HEAD (`6dfd05e`).

| v1 Plan Item | Plan Said | Reality | Status |
|---|---|---|---|
| `HeroMockup.tsx` | "New file to create" | Exists (`frontend/components/HeroMockup.tsx`, 136 lines), rendered at `page.tsx:112` | ✅ Built — but shows wrong data (§4 CRO-3) |
| `SocialProofStrip.tsx` | "New file to create" | Exists, rendered at `page.tsx:122`; hardcodes "500+ companies / 10,000+ filings" (`SocialProofStrip.tsx:6-7`) | ✅ Built — fabricated numbers (§4 CRO-2) |
| `HowItWorks.tsx` | "New file to create" | Exists, rendered at `page.tsx:144` | ✅ Built |
| `FeatureShowcase.tsx` | "New file to create" | Exists, rendered at `page.tsx:151` | ✅ Built |
| `CtaBanner.tsx` | "New file to create" | Exists, rendered at `page.tsx:169` | ✅ Built |
| `NavLink.tsx` | "New file (optional)" | Does not exist; `Header.tsx` uses `next/link` inline | ➖ Skipped (correctly) |
| Header overhaul | Nav links + dual CTAs | Done: `Header.tsx:8-10` (Pricing, Contact) + Log In/Get Started; mobile menu | ✅ Built — but `/pricing` is not in the middleware allowlist, so the nav link bounces to `/waitlist` while gated (`middleware.ts:3-18` vs `Header.tsx:9`) |
| Hero split layout | Copy left / mockup right | Done: `page.tsx:69-115`; mockup `hidden lg:block` (`page.tsx:110`) | ✅ Built — no product visual on mobile |
| Footer overhaul | Multi-column | Done (commit `26df0ac`) | ✅ Built |
| Design tokens | `hero-dark`, glow shadows | `hero-gradient`/`hero-glow` + `glow-mint` shipped; `hero-dark` token never created (plan §2 references it as pre-existing — it never existed) | ⚠️ Partially built |
| Scroll-triggered fade-ins (Phase 5) | Per-section | `.animate-on-scroll` utility exists (`globals.css:101-110`) but nothing on the homepage uses it | ➖ Not wired (fine — drop it) |
| "Remove waitlist redirect (or make configurable)" (Phase 5) | To do | Configurable via `WAITLIST_MODE`, **default ON**: redirect lives in BOTH `middleware.ts:42-58` and `page.tsx:52-57` | ❌ Gate still up — the shipped homepage has effectively never been seen by production traffic |
| Theme toggle removal | Dark-first homepage | Homepage/Header are dark-only; `ThemeToggle.tsx` still exists for app pages | ✅ Built |
| Lighthouse/perf audit (Phase 5) | To do | No evidence of execution; no measurement artifacts | ❓ Unverified |
| **Made obsolete by activation work (June 2026)** | — | Q2 added "See an Example" deep-link (`page.tsx:93`, `featureFlags.ts:47`, `backend/scripts/pregenerate_examples.py`); Q1 opened `/company` + `/filing` through the gate; Q5 added recommended-filing CTA on company pages | 🔄 The hero's static mockup now competes with a *real, zero-wait, clickable* product demo the plan never anticipated |

**Net:** ~90% of v1 is live code. The remaining v1 checklist items are either moot
(skipped components), already superseded (example CTA), or are exactly the
strategic decisions v1 deferred (gate removal, performance/SEO audit, measurement).

---

## 3. Recommended Objective & Primary CTA

**Primary objective: ACTIVATION — an anonymous visitor reaches their first
successful summary (rendered, full-quality) in the same session.**

Justification against product stage:

1. **The product needs no signup to deliver value.** Summary generation requires no
   auth (`NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY` defaults false,
   `filing/[id]/page-client.tsx:330,397`), the first summary is never quota-gated
   (S5, `summaries.py:267-281`), and the demo path is deliberately open through the
   waitlist gate (Q1, `middleware.ts:15-18`). A homepage whose visually dominant CTA
   is "Get Started Free → /register" (`page.tsx:85-91`) inserts registration friction
   *before* the value moment, against the product's own architecture.
2. **It matches the declared north star.** `tasks/todo.md:3-4` and
   `tasks/activation-gap-analysis.md` define the north star as "anonymous visitor →
   first successful, high-quality summary, fast and reliable." Fourteen
   engineering items (Q1–Q8, S1–S5) just shipped in service of it. A homepage that
   optimizes signup or waitlist lead-gen instead would orphan that investment.
3. **Activation is the best signup engine anyway.** A visitor who has just read a
   useful summary has a concrete reason to register (save it, watchlist, more
   quota). Signup conversion becomes a *downstream* metric, captured at the moment
   of demonstrated value (e.g., the S5 quota's "create a free account" prompt).
4. **SEO-led discovery is a prerequisite, not the objective.** Top-of-funnel is
   currently near-zero by construction (307 gate, no robots/sitemap on the frontend
   domain). Fixing indexability is in-scope (§5 Phase 1) but it serves activation;
   it isn't the page's job.

**Primary CTA: the company search bar.** One hero, one action: "search a company"
— it is the product's first step and the funnel's entry event. Hierarchy:

- **Primary:** `CompanySearch` (promoted visually to the hero's focal element).
- **Secondary (zero-effort path):** "See a live example →" deep-linking to the
  pre-generated filing (`/filing/{NEXT_PUBLIC_EXAMPLE_FILING_ID}`) — for
  low-intent visitors who won't type. This is a *real page*, not a mockup.
- **Demoted:** "Get Started Free" moves to the header only (it's already there as
  `Header.tsx`'s register CTA). The hero stops competing with itself.

The current hero violates v1's own Principle 5 ("One Clear Action"): it stacks
**two buttons + a search bar + 8 ticker chips** (`page.tsx:84-106`) — four
competing actions above the fold.

---

## 4. Critique by Lens

Severity: 🔴 critical (blocks the objective / legal-credibility risk),
🟠 major (measurably hurts the objective), 🟡 minor (polish/correctness).

### Conversion / CRO

- 🔴 **CRO-1: The homepage is unreachable.** `WAITLIST_MODE` defaults on; `/` 307s
  to `/waitlist` in `middleware.ts:56-58` *and again* in `page.tsx:55-57`. Every
  dollar of homepage design work has had zero production exposure since Feb. The
  single highest-leverage "redesign" available is flipping one env var — and the
  go-live checklist (`activation-gap-analysis.md:179-188`) is complete except
  funnel instrumentation (Q2 ✅ Q3 ✅ Q4 ✅ Q7 ✅ S5 ✅, instrumentation ❌).
- 🔴 **CRO-2: Fabricated social proof.** "500+ companies covered / 10,000+ filings
  analyzed" are hardcoded constants (`SocialProofStrip.tsx:6-7`). No COUNT query
  on Company/Filing/Summary exists anywhere in the backend (verified: routers,
  models, `metrics_service.py` track HTTP metrics only). These are invented usage
  claims — an FTC Act §5 deceptive-practices exposure and, worse for an early
  product, a credibility time bomb for exactly the skeptical-investor audience the
  plan says it targets. Honest replacements exist (§5 Phase 0).
- 🔴 **CRO-3: The hero mockup shows wrong financial data.** `HeroMockup.tsx:40-73`
  labels Apple "FY 2025" with Revenue $394.3B / Net income $97.2B / EPS $6.42 —
  Apple's FY2022 figures. The product's core promise is numeric accuracy
  (XBRL-grounded); its first impression presents misattributed numbers. Any
  sophisticated visitor who notices is gone.
- 🟠 **CRO-4: CTA hierarchy optimizes registration over activation** (§3). Also
  duplicated in `CtaBanner.tsx` (Get Started Free primary again).
- 🟠 **CRO-5: No objection handling.** Nothing answers "how do I know the AI is
  right?" (the #1 objection for this category — and the codebase has a real
  answer: XBRL grounding, SEC EDGAR sourcing, the S4 quality verdict). Nothing
  states what's free (FREE_TIER_SUMMARY_LIMIT=5/mo; guest 3/day when
  `ENABLE_GUEST_DAILY_QUOTA` is on).
- 🟡 **CRO-6: "Show, don't tell" is half-realized.** The mockup's "summary text" is
  grey skeleton bars (`HeroMockup.tsx:51-55`) — it literally shows nothing. Q2
  created a better artifact: a real cached summary one click away.

### Visual & Interaction Design

- 🟠 **D-1: Static mockup vs. live product.** Post-Q2, the strongest possible hero
  visual is the real thing (screenshot of, or live route to, the pre-generated
  example). A 2026 best-in-class pattern is product-as-hero (real UI, real data),
  not decorative skeletons. At minimum the mockup must be clickable to the example.
- 🟠 **D-2: No product visual on mobile** — `hidden lg:block` (`page.tsx:110`).
  Mobile visitors (typically the traffic majority) get copy + buttons only. v1
  specified desktop-split-hero and never wrote the mobile story.
- 🟡 **D-3: Motion without consent.** `animate-float` is an infinite transform loop
  with no `prefers-reduced-motion` guard (`globals.css:36-47`; only `radar-ping`
  is guarded, `globals.css:74-78`). The count-up rAF loop in
  `SocialProofStrip.tsx:26-38` also ignores reduced-motion. Violates v1's own
  Principle 4 and WCAG 2.3.3 (AAA) / general motion-safety practice.
- 🟡 **D-4: Glass-morphism/glow is acceptable but already a 2021–2023 idiom**;
  fine to keep (restrained here), wrong place to invest further. Stocktwits is a
  social/feed product — a weak reference for a research tool whose credibility
  cues should be data fidelity (real tables, citations, sourcing) rather than
  social-energy gradients. No further "premium treatment" work is warranted.

### Performance / Core Web Vitals

- 🟢 (Good) Hero LCP element is text — no hero image to optimize; mockup is inline
  DOM/SVG; Inter via `next/font` (`layout.tsx:10-12`); Suspense skeletons have
  fixed heights (`page.tsx:19-49`), containing CLS.
- 🟠 **P-1: Unnecessary client components.** `HeroMockup.tsx:1` and
  `SocialProofStrip.tsx:1` are `'use client'` for purely static/animatable content;
  `QuickAccessBar` is client for one analytics call. Each adds hydration JS to the
  most important page. HeroMockup is trivially a server component; the counter can
  be CSS-only or dropped with the fake stats.
- 🟡 **P-2: Two client-fetch waterfalls** (HotFilings, TrendingTickers via React
  Query, `HotFilings.tsx:61`) render below the fold — acceptable, but INP on
  low-end mobile should be watched once real traffic exists; `backdrop-filter`
  blur (`globals.css:115`) is the main paint cost.
- 🟡 **P-3: v1's perf criteria were never validated** (no Lighthouse artifacts in
  repo/history). Carry forward as Phase 4 verification, against field data (CrUX /
  Vercel Analytics) not just lab.

### SEO & Discoverability

- 🔴 **S-1: `/` is un-indexable by design.** 307 from the canonical URL means the
  homepage content has never been crawlable; `/waitlist` (the landing everyone
  gets) exports **no metadata** (verified: no `metadata` export in
  `app/waitlist/page.tsx`), inheriting the generic layout title.
- 🔴 **S-2: No `robots.txt`, no sitemap on the frontend domain.** Middleware
  allowlists `/robots.txt` and `/sitemap.xml` (`middleware.ts:10-11`) but neither
  exists — no `app/robots.ts`, no `app/sitemap.ts`, nothing in `public/`, no
  rewrite to the backend's `/sitemap.xml` router (`backend/app/routers/sitemap.py`
  serves only the API domain). They 404. Company/filing pages — the long-tail SEO
  asset (every ticker × every filing) — are open through the gate (Q1) but
  undiscoverable.
- 🟠 **S-3: No structured data** (zero JSON-LD in the codebase). `Organization` +
  `WebSite`+`SearchAction` on the homepage are table stakes.
- 🟠 **S-4: `og-image.svg`** (`layout.tsx:26`, only file in `public/` besides
  assets): most social crawlers (Facebook, X, LinkedIn, Slack) do not render SVG
  og:images — shares show no card image.
- 🟡 **S-5: No page-level `metadata` export on `page.tsx`** — fine while inheriting
  layout defaults, but the homepage should own its title/description and canonical.

### Accessibility (WCAG 2.2 AA)

- 🔴 **A-1: The primary CTA fails contrast.** White text on `bg-mint-500`
  (#10B981, `tailwind.config.js:9`; `page.tsx:87`, repeated in CtaBanner/Header) ≈
  **2.5:1** — far below the 4.5:1 AA requirement for 16px semibold text. Fix: dark
  text on mint (e.g., mint-950/slate-950 on mint-400/500 ≈ 8–10:1), the standard
  fintech dark-theme pattern.
- 🟠 **A-2: Motion ignores `prefers-reduced-motion`** (D-3).
- 🟡 **A-3:** 10px/`text-[10px]` slate-500 labels inside the mockup are decorative
  but readable as content; either `aria-hidden` the whole mockup (it's a picture)
  or fix sizes/contrast. Decorative emoji `🔥` in the "Trending Filings" h2
  (`page.tsx:131`) should be `aria-hidden`.
- 🟢 (Good) `focus-visible` outlines are present on hero CTAs (`page.tsx:87,94`);
  skeletons carry `role="status"`/`aria-live` (`page.tsx:21,34`).

### Engineering

- 🟠 **E-1: Gate logic duplicated** in `middleware.ts:42-58` and `page.tsx:52-57`
  — two sources of truth for the same env var; they can drift (and the page-level
  one defeats static rendering of `/`). Single source: middleware only.
- 🟠 **E-2: Nav links to a gated route.** `/pricing` (`Header.tsx:9`) is not in
  `ALLOWED_PATHS` (`middleware.ts:3-13`); while gated, clicking "Pricing" from
  `/login`, `/contact`, or any `/company/*` page bounces to `/waitlist`. Broken
  journey shipped for 4 months — also evidence that the gated state gets no QA.
- 🟡 **E-3: Dead code:** `TrendingCompanies.tsx` is built but unused on the
  homepage; `.animate-on-scroll` utility unused. Prune or wire deliberately.
- 🟡 **E-4: Marketing copy duplicated** between `/waitlist` (its own
  problem/how-it-works/features/trust sections, `app/waitlist/page.tsx:91-246`)
  and the homepage equivalents — two pages to keep honest, and the waitlist
  version lacks the Q2 example CTA entirely (it shows a *third*, static mockup).

### Content / Copy

- 🟢 (Good) The shipped headline — "Understand any SEC filing in minutes"
  (`page.tsx:72-76`) — is honest and specific. v1's proposed "The #1 Platform for
  SEC Filing Analysis" is an unverifiable superlative; it was correctly not
  shipped. Keep the honest register.
- 🟠 **C-1:** "Real-Time XBRL Data" (FeatureShowcase) overstates — XBRL is
  point-of-filing data, cached 24h (CacheTTL.XBRL_DATA). Say "XBRL-verified
  financials" (the waitlist page's "XBRL-aware" copy is more honest).

### Measurement

- 🔴 **M-1: The objective is unmeasured.** PostHog is integrated (consent-aware,
  `posthog-provider.tsx`) and four component-level events exist
  (`company_searched` `CompanySearch.tsx:55`; `quick_access_click`
  `QuickAccessBar.tsx:22`; `hot_filing_summary_clicked` `HotFilings.tsx:231-235`;
  `market_mover_clicked` `TrendingTickers.tsx:92-100`) — but **no
  generation_started/succeeded/failed/timed_out events exist anywhere**, and
  `backend/app/services/posthog_client.py` has zero call sites. The
  search→filing→generate→success funnel cannot be assembled.
  `activation-gap-analysis.md:189-191` already prescribed the exact event set;
  it is the one unfinished go-live item.
- 🟠 **M-2: v1's success criteria measure proxies only** (Lighthouse scores,
  "looks like a real platform") — nothing ties the page to a conversion or
  activation number. A redesign that can't be falsified can't be called a success.

---

## 5. The Upgraded Plan (v2)

**Objective:** maximize **activation rate** = sessions landing on `/` that reach a
`summary_viewed` (success) event in-session. Everything below is sequenced by
leverage; visual work comes last because the visuals already exist.

### Phase 0 — Truth & Safety (prereq for any traffic) — *NEW*

1. **Replace fabricated stats** in `SocialProofStrip.tsx` with claims that are true
   today, no DB needed:
   - "Every SEC-registered company" (true — search covers the full SEC ticker
     universe via `company_tickers.json`, `edgar/compat.py:76-82`)
   - "10-K & 10-Q coverage" · "Sourced directly from SEC EDGAR" · "Every figure
     traceable to XBRL"
   - (Optional, later) real counters via one cached endpoint:
     `COUNT(filings)`, `COUNT(summaries)` — display only once the numbers are
     impressive on their own.
2. **Fix or replace the hero mockup's numbers** (`HeroMockup.tsx:62-73`): use the
   actual latest Apple 10-K figures from the pre-generated example (or relabel the
   fiscal year correctly) — interim fix while Phase 2 replaces the mockup.
3. **A11y/motion fixes:** dark-on-mint primary buttons (A-1, sitewide token-level
   change); wrap `float`/count-up in `prefers-reduced-motion` guards (D-3);
   `aria-hidden` the mockup and the 🔥 emoji.
4. **Fix `/pricing` gate bounce** (E-2): add `/pricing` to `ALLOWED_PATHS` (or hide
   the nav link while gated).
5. **Instrument the funnel** (M-1) — the last open go-live item: add
   `generation_started/succeeded/failed/timed_out` + `summary_viewed` (with
   `duration_ms`, `result_type`, `quality_verdict`, `entry_point`) on the filing
   page/stream client, and wire `posthog_client.py` server-side for generation
   outcomes. Define the funnel in PostHog: `$pageview(/)` → `company_searched` |
   `quick_access_click` | `example_cta_clicked` (new event) → `filing page view` →
   `generation_started` → `summary_viewed`.

### Phase 1 — Open & Index (the real "redesign") — *NEW*

1. **Flip the gate:** set `WAITLIST_MODE=false` (owner action; checklist now
   complete). Keep `/waitlist` as a campaign page, give it `metadata` and the Q2
   example CTA. Remove the duplicate redirect from `page.tsx:52-57` so `/` is
   statically renderable (E-1).
2. **Set `NEXT_PUBLIC_EXAMPLE_FILING_ID` in prod** (script
   `backend/scripts/pregenerate_examples.py` already exists) — without it, "See an
   Example" silently degrades to the 3-click/60s `/company/AAPL` path.
3. **SEO foundation:** `app/robots.ts`; `app/sitemap.ts` (homepage + static pages,
   plus company/filing URLs — reuse/proxy the backend sitemap router);
   page-level `metadata` + canonical on `page.tsx`; JSON-LD `Organization` +
   `WebSite`/`SearchAction`; replace `og-image.svg` with a 1200×630 PNG.

### Phase 2 — Activation-first hero — *revised from v1 §2*

1. **Re-rank CTAs** (§3): search bar becomes the hero's focal element (size,
   placement, autofocus on desktop); "See a live example →" secondary;
   "Get Started Free" removed from the hero (stays in header). Apply the same
   demotion in `CtaBanner` ("Run your first summary" → search or example, with
   register as the post-value ask).
2. **Real product as the visual:** make the hero visual the actual example —
   either a real screenshot (static, optimized, `next/image`) of the pre-generated
   filing page, linked to it, or a trimmed live-data card. Kill the skeleton-bar
   mockup. *Carried over from v1's "Show, don't tell," upgraded from decoration to
   demonstration.*
3. **Mobile story** (D-2): below the search bar, show a compact example card
   (company, 3 real metrics, "Read the full summary →") instead of hiding the
   product entirely on <lg.
4. **Server-componentize** the static pieces (P-1).

### Phase 3 — Honest persuasion — *revised from v1 §3/§6*

1. **Accuracy/objection section** (replaces generic FeatureShowcase emphasis):
   "Where the numbers come from" — EDGAR sourcing, XBRL grounding, quality verdict
   (ties to S4; if `NEXT_PUBLIC_ENABLE_QUALITY_BADGE` ships on, the homepage claim
   and product behavior align: we tell you when a summary is partial).
2. **Free-tier clarity:** state what a visitor gets without a card (first summary
   free, no signup; 5/month free account) near the CTA.
3. Keep Hot Filings / Trending Tickers sections as-is (they're real data and the
   page's only live proof today); tighten "Real-Time XBRL" copy (C-1).

### Phase 4 — Measure, then iterate — *NEW*

1. **Baseline for 2 weeks post-launch:** activation rate, search engagement rate
   (% of `/` sessions firing search/quick-access/example events), time-to-first-
   summary p50/p90, generation success rate, example-CTA CTR, signup rate among
   activated users.
2. **Verify CWV in the field** (Vercel Analytics/CrUX) against v1's lab targets
   (LCP < 2.5s, CLS < 0.1, INP < 200ms) — carried over from v1, now with field data.
3. **Only after baseline:** A/B headline and hero-visual variants via PostHog
   feature flags. Targets are set *from the baseline* (e.g., +20% relative on
   activation rate per iteration), not invented in advance.

**Success metrics (tied to the objective, not proxies):**
- Primary: activation rate (`/` session → successful `summary_viewed`).
- Guardrails: generation success rate (from new events), CWV field data,
  organic impressions on `/company/*`//`filing/*` (Search Console) post-Phase 1.
- Explicitly *not* a success metric: Lighthouse alone, or "looks premium."

---

## 6. Quick Wins vs. Strategic Bets

| # | Item | Effort | Impact | Phase |
|---|------|--------|--------|-------|
| QW1 | Remove fabricated stats; honest claims (`SocialProofStrip.tsx:6-7`) | XS | Critical (risk removal) | 0 |
| QW2 | Fix mockup figures / fiscal-year label (`HeroMockup.tsx:40-73`) | XS | High | 0 |
| QW3 | Dark-on-mint button text (A-1) | XS | High (AA compliance) | 0 |
| QW4 | Reduced-motion guards (D-3) | XS | Medium | 0 |
| QW5 | `/pricing` allowlist fix (E-2) | XS | Medium | 0 |
| QW6 | Set `NEXT_PUBLIC_EXAMPLE_FILING_ID` in prod | XS (ops) | High | 1 |
| QW7 | `robots.ts` + `sitemap.ts` + page metadata + PNG og-image | S | High | 1 |
| QW8 | De-duplicate gate logic (`page.tsx:52-57`) | XS | Medium | 1 |
| SB1 | Funnel instrumentation (6 events, FE+BE) | M | **Critical** — everything else is unfalsifiable without it | 0 |
| SB2 | Flip `WAITLIST_MODE=false` (owner decision) | XS (+risk mgmt) | **Highest single lever** | 1 |
| SB3 | Hero re-hierarchy: search primary, example secondary, register demoted | M | High | 2 |
| SB4 | Real-product hero visual + mobile example card | M | High | 2 |
| SB5 | Accuracy/"where numbers come from" section + free-tier clarity | M | Medium-High | 3 |
| SB6 | Real-counts endpoint + live counters (optional) | S | Low-Medium (only when numbers impress) | 3+ |
| SB7 | A/B program on headline/hero | M | Compounding | 4 |

---

## 7. Resolved Open Questions & Risks

### v1's five open questions, resolved

1. **Waitlist vs. live?** Go live (flip `WAITLIST_MODE=false`) once SB1
   (instrumentation) ships — every other go-live checklist item
   (`activation-gap-analysis.md:179-188`) is done. If the business wants the gate
   longer, then `/waitlist` *is* the homepage and must inherit v2 Phases 0–2
   (metadata, example CTA, honest claims) — today it has none of them.
2. **Product mockup?** Use the real product: screenshot of (or live card from) the
   Q2 pre-generated example filing, linked to it. Never display invented
   financials. The static `HeroMockup` is retired after Phase 2 (figures corrected
   in Phase 0 as interim).
3. **Copy tone?** Honest-specific, not superlative. Keep the shipped headline;
   reject "#1 Platform" (unverifiable claim, same class of problem as the
   fabricated stats).
4. **Nav links?** Only live, gate-reachable routes: Pricing (after QW5), Contact;
   optionally `#hot-filings`/`#trending` anchors. Add Dashboard/Log-in states as-is.
5. **Social links?** None until real, maintained profiles exist. Dead social
   icons are negative social proof.

### Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Fabricated metrics already in production code** (even if unreached, they're one env flip from public) | 🔴 | QW1 ships before SB2; grep CI guard for unverifiable claim patterns is cheap insurance |
| **SEO/redirect**: prolonged 307 on `/` + missing robots/sitemap = zero organic compounding; competitors index the long tail of `{ticker} 10-K summary` queries first | 🔴 | Phase 1; until gate flips, give `/waitlist` real metadata and self-canonical |
| **Quality coin-flip on open traffic**: homepage promises "decision-ready insights" while S1 (structured output), S4 (quality gate/badge) are default-off — degraded summaries still ship looking complete (`stripInternalNotices.ts:14-23`) | 🟠 | Run the S3 eval-harness adoption gate; enable `NEXT_PUBLIC_ENABLE_QUALITY_BADGE` at or before gate-flip so the homepage's honesty extends into the product; monitor `generation_failed`/`timed_out` events from day one |
| **Example filing staleness** (screenshot or cached summary drifts from current UI/figures) | 🟡 | Re-run `pregenerate_examples.py` on a schedule; date-stamp the example ("AAPL 10-K, filed Nov 2025") |
| **Traffic spike on gate-flip hits SEC EDGAR limits** | 🟡 | Existing protections (circuit breaker, S5 guest quota — enable `ENABLE_GUEST_DAILY_QUOTA`, sec_rate_limiter); pre-generate QuickAccessBar tickers so the hottest paths are cache hits |
| **Re-doing v1**: someone "approves" the stale plan and rebuilds shipped components | 🟡 | This document supersedes it; mark the v1 plan in `tasks/todo.md` as SHIPPED (26df0ac) / SUPERSEDED |

---

## Appendix: Evidence Index (spot-verified)

- Plan shipped same-day: `git log` — `26df0ac` (2026-02-05) touches
  `page.tsx`, `HeroMockup.tsx`, `SocialProofStrip.tsx`, `HowItWorks.tsx`,
  `FeatureShowcase.tsx`, `CtaBanner.tsx`, `Header.tsx`, `Footer.tsx`,
  `tailwind.config.js`, `globals.css`.
- Gate: `frontend/middleware.ts:42-58` + `frontend/app/page.tsx:52-57`
  (default-on, 307).
- Fabricated stats: `frontend/components/SocialProofStrip.tsx:5-9`.
- Wrong mockup figures: `frontend/components/HeroMockup.tsx:40,62-73`.
- CTA contrast: `tailwind.config.js:9` (#10B981) + `page.tsx:87`
  (`bg-mint-500` + white text ≈ 2.5:1).
- Motion guard gap: `globals.css:36-47` (unguarded) vs `:74-78` (guarded).
- SEO gaps: no `app/robots.ts`/`app/sitemap.ts`/`public/robots.txt`;
  `og-image.svg` at `layout.tsx:26`; no JSON-LD (repo-wide grep);
  no `metadata` export in `app/waitlist/page.tsx`.
- Funnel darkness: events only in `CompanySearch.tsx:55`,
  `QuickAccessBar.tsx:22`, `HotFilings.tsx:231-235`,
  `TrendingTickers.tsx:92-100`; zero call sites for
  `backend/app/services/posthog_client.py`; prescription at
  `tasks/activation-gap-analysis.md:189-191`.
- Activation flow: no-auth generation (`filing/[id]/page-client.tsx:330,397`),
  first summary never gated (`summaries.py:267-281`), example deep-link
  (`page.tsx:93`, `featureFlags.ts:47`, `backend/scripts/pregenerate_examples.py`),
  recommended filing (`company/[ticker]/page-client.tsx:310-339`).
