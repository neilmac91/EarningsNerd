# Launch-Readiness & Measurement

Site is **live but pre-traffic** (the `WAITLIST_MODE` gate is already flipped off in prod). Goal of
this workstream: make sure the homepage is honest + accessible and the activation funnel is fully
measurable *before* real users arrive, so early traffic produces clean baseline data.

Driven by a verification pass (2026-06-20) that reconciled the planning docs
(`homepage-redesign-v2.md`, `activation-gap-analysis.md`, the post-sprint inventory) against the
actual code. **The docs materially overstated the gaps** — most flagged "blockers" were already done.

## Verified posture (corrected record, with evidence)

| Item | Doc/inventory claim | Verified reality |
|------|---------------------|------------------|
| Hero mockup figures | FY2022 data mislabeled FY2025 | **Done.** `HeroExample.tsx` shows Apple FY2022, correctly labeled, XBRL-verified; real data fetched server-side (ISR), fallback only on API failure. |
| A11y CTA contrast | white-on-mint ~2.5:1, fails AA | **Done.** CTAs are `bg-mint-500` + `text-slate-950` = **12.36:1** (exceeds AAA). `focus-visible` on every CTA; full ARIA + keyboard nav on search. |
| SocialProofStrip | fabricated "500+/10,000+" | **Done.** Honest capability claims only. |
| JSON-LD / SEO | missing | **Done.** Organization + WebSite + SearchAction in `page.tsx`; OG/Twitter metadata + `og-image.png`; `robots.ts` + `sitemap.ts` live. |
| Funnel events | defined but never fired; `summary_viewed` missing | **Done.** All events fire; client→server identity joins via `ph_id` query param on the stream → backend reuses it as the distinct_id. Activation rate, success rate, p50/p95 latency, quality verdict all measurable. |
| Reduced motion | unguarded animations | **Mostly done** — CSS animations guarded; **`useCountUp` was not** (the one genuine code gap). |
| Funnel segmentation | n/a | **Gap:** `company_viewed` / `filing_viewed` lacked `entry_point`, so the funnel couldn't be segmented by source before `generation_started`. |

## Shipped in this PR

### Commit 1 — a11y: reduced-motion guard on `useCountUp`
- `frontend/hooks/useCountUp.ts`: if `prefers-reduced-motion: reduce`, snap to the final value with
  no tween (WCAG 2.3.3). Hydration-safe: initializer stays `0` (server/client first render agree);
  the effect honors the preference on the client.
- Test: `tests/unit/useCountUp.spec.ts`.

### Commit 2 — measurement: activation-funnel segmentation
- `lib/entryPoint.ts`: extracted the shared `getEntryPoint()` (was duplicated inline on the filing
  page) so the filing **and** company pages attribute to the same source. Test: `tests/unit/entryPoint.spec.ts`.
- `analytics.ts`: added `entry_point` to `company_viewed` + `filing_viewed`; added
  `company_search_result_clicked` (closes the search→navigation loop causally) and
  `paywall_prompt_shown`.
- `company/[ticker]/page-client.tsx` + `filing/[id]/page-client.tsx`: pass `entry_point`.
- `CompanySearch.tsx`: fire `company_search_result_clicked` on result selection (click, instant
  match, Enter).
- `summaries-api.ts`: exported `isPaywallStreamError`; filing page fires `paywall_prompt_shown`
  when the upgrade wall is shown.

**Deliberate design note (paywall):** the backend already fires `paywall_hit` server-side with
`entry_point` + the joined distinct_id. A frontend `paywall_hit` would **double-count**, so the
frontend fires a *distinct* `paywall_prompt_shown` — the client-confirmed UX moment the user is
actually shown the wall. The two must not be conflated in dashboards.

## Owner / ops (not code — outstanding)
- [ ] **PostHog activation dashboard** from the (already-firing) events: funnel
      `landing → entry CTA → generation_started → generation_succeeded → summary_viewed`; success rate
      `succeeded / (succeeded + failed + timed_out)`; p50/p95 `duration_ms`; `quality_verdict`
      breakdown; `entry_point` segmentation (unlocked by commit 2). Establish the baseline.
- [ ] Confirm `NEXT_PUBLIC_EXAMPLE_FILING_ID` is set in prod (zero-wait example deep-link).
- [x] `WAITLIST_MODE=false` in prod — already flipped (site live, pre-traffic).

## Out of scope (follow-on, not launch-blocking)
Phase 2 hero CTA re-hierarchy + real product visual, Phase 3 "where the numbers come from"
persuasion section, and the A/B program — these are **conversion optimization**, best done *after*
1–2 weeks of baseline data, not before measuring.

## Verification
- `npm run typecheck` clean; `npm run lint` clean (`--max-warnings 0`); full frontend suite **98 passing**
  (incl. the 2 new specs). Backend untouched.
