/**
 * Feature flags for EarningsNerd UI
 *
 * These flags control which UI features are enabled/disabled.
 * Flags are configured via environment variables in next.config.js
 *
 * To enable a feature, set the corresponding env var to 'true'
 * To disable a feature, set it to 'false' (or leave unset for default)
 */

/**
 * Enable financial charts (Revenue, Net Income visualizations)
 * When false, charts are hidden from the UI
 * Default: false (charts hidden)
 */
export const ENABLE_FINANCIAL_CHARTS =
  process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS === 'true'

/**
 * Highlight a "Recommended" filing (the company's most recent filing of any type) on the company
 * page with a one-click summary CTA, so first-time visitors don't have to decide between filing
 * types/dates before activating. The full year-grouped list stays below.
 * Default: enabled (set NEXT_PUBLIC_ENABLE_RECOMMENDED_FILING='false' to disable).
 */
export const ENABLE_RECOMMENDED_FILING =
  process.env.NEXT_PUBLIC_ENABLE_RECOMMENDED_FILING !== 'false'

/**
 * Pre-generated example filing for zero-wait activation.
 * When set, the homepage "See an Example" CTA deep-links directly to the
 * cached filing summary at `/filing/{id}` instead of the `/company/AAPL`
 * fallback — so first-time visitors see an instant example with no
 * 3-click + 30-80s generation wait.
 *
 * Set NEXT_PUBLIC_EXAMPLE_FILING_ID to a filing id whose Summary has been
 * pre-generated (see backend/scripts/pregenerate_examples.py).
 * Default: undefined (CTA falls back to /company/AAPL).
 */
export const EXAMPLE_FILING_ID = process.env.NEXT_PUBLIC_EXAMPLE_FILING_ID

/**
 * Href for "see an example" CTAs. Deep-links to the pre-generated example
 * filing (tagged with an `entry` param for funnel attribution) when
 * EXAMPLE_FILING_ID is set, else falls back to the company page.
 *
 * The example/onboarding deep-link carries `demo=1` so the filing page renders
 * in demo mode (curated first impression): the quality badge + Regenerate
 * button are suppressed and the copilot's attention nudge is silenced, so a
 * first-time visitor never meets a "Partial" badge on the curated example.
 */
export const exampleFilingHref = (entry: string): string =>
  EXAMPLE_FILING_ID
    ? `/filing/${EXAMPLE_FILING_ID}?entry=${encodeURIComponent(entry)}&demo=1`
    : '/company/AAPL'

/**
 * Honest degradation (roadmap S4). When enabled, the filing summary shows an explicit quality
 * badge ("Full summary" / "Partial — ...; retry") driven by the backend's
 * `raw_summary.quality` verdict, and STOPS stripping internal failure notices client-side —
 * so a degraded summary is surfaced honestly with a one-click regenerate instead of being
 * dressed up as a complete one.
 * Default: disabled (set NEXT_PUBLIC_ENABLE_QUALITY_BADGE='true' to enable), preserving the
 * current notice-stripping behavior until validated.
 */
export const ENABLE_QUALITY_BADGE =
  process.env.NEXT_PUBLIC_ENABLE_QUALITY_BADGE === 'true'

/**
 * Show the "Continue with Apple" sign-in button.
 * Ships off by default — the Apple backend exchange (Increment 4) and the Apple
 * Developer Console setup must be live first, otherwise the button 404s.
 * Flip NEXT_PUBLIC_ENABLE_APPLE_SIGNIN='true' once Sign in with Apple is wired up.
 */
export const ENABLE_APPLE_SIGNIN =
  process.env.NEXT_PUBLIC_ENABLE_APPLE_SIGNIN === 'true'

/**
 * Cloudflare Turnstile (bot defense) site key. When set, the Turnstile widget renders on the
 * auth / contact / waitlist forms and a token is sent to the backend for verification (the
 * backend must also have TURNSTILE_SECRET_KEY). When unset, the widget renders nothing and the
 * forms behave exactly as before — so this is dark until both keys are configured.
 */
export const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || ''
export const TURNSTILE_ENABLED = TURNSTILE_SITE_KEY.length > 0

/**
 * Show the homepage "Market Movers" section (Stocktwits/FMP trending tickers).
 * Ships OFF: the FMP validation path is dead (legacy API cut off 2025-08-31) and no license-clean
 * $0 replacement exists, so prod was serving a hardcoded fallback with an internal error string —
 * see tasks/homepage-sections-review-findings.md (verdict: hide now; backend teardown follows in
 * a later PR). Flip NEXT_PUBLIC_ENABLE_MARKET_MOVERS='true' only with a licensed data source.
 */
export const ENABLE_MARKET_MOVERS =
  process.env.NEXT_PUBLIC_ENABLE_MARKET_MOVERS === 'true'

/**
 * Show the dashboard earnings calendar (upcoming earnings for watched companies).
 * Ships off by default. The FMP dependency is retired: the backend
 * `/api/dashboard/calendar/upcoming` now reads the owned `earnings_events` table (seeded by the
 * Alpha Vantage + EDGAR 8-K engine via the `earnings-calendar-refresh` job) and degrades to an
 * empty calendar if that table isn't seeded. Flip NEXT_PUBLIC_ENABLE_CALENDAR='true' only after
 * confirming `earnings_events` is seeded and fresh in the target environment. The same flag lights
 * up the `/calendar` page and its nav entries, whose market-wide endpoint is also live.
 */
export const ENABLE_CALENDAR = process.env.NEXT_PUBLIC_ENABLE_CALENDAR === 'true'

/**
 * Show the insider-activity (Form 4) panel on the company page. The backend endpoint does a LIVE
 * SEC EDGAR fan-out across recent Form 4 filings (up to a ~75s ceiling), so this ships off by
 * default and should be enabled deliberately once validated against SEC rate limits.
 * Flip NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY='true' to enable.
 */
export const ENABLE_INSIDER_ACTIVITY =
  process.env.NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY === 'true'

/**
 * Show the in-dashboard beta feedback widget (floating "Feedback" launcher for logged-in users).
 * On by default so beta testers can report bugs/ideas from anywhere; set
 * NEXT_PUBLIC_ENABLE_FEEDBACK_WIDGET='false' to hide it (e.g. post-beta).
 */
export const ENABLE_FEEDBACK_WIDGET =
  process.env.NEXT_PUBLIC_ENABLE_FEEDBACK_WIDGET !== 'false'

/**
 * Show Multi-Period Analysis — the Pro flagship: pick a company, pick up to 10 fiscal years or
 * 12 quarters, get charts + a metrics grid + a streamed AI trend narrative with verifiable
 * citations. The /analysis route 404s while off (same gate pattern as Compare), so it ships dark
 * until the backend has been verified in prod and the companyfacts cache is warmed.
 * Flip NEXT_PUBLIC_ENABLE_ANALYSIS='true' to launch.
 * Default: disabled.
 */
export const ENABLE_ANALYSIS =
  process.env.NEXT_PUBLIC_ENABLE_ANALYSIS === 'true'

/**
 * Advertise the 7-day card-required Pro trial across the UI (pricing card CTA/note/FAQ, the
 * filing-page paywall card, the signup gate, homepage CTA banner). MUST flip in lockstep with the
 * backend's PRO_TRIAL_DAYS on Cloud Run: the backend defaults the trial OFF (rollout convention —
 * enable per environment only after the Stripe test-mode checklist in PR #619), and showing trial
 * copy while checkout grants no trial is a false billing claim. Ships dark.
 * Flip NEXT_PUBLIC_ENABLE_PRO_TRIAL='true' together with PRO_TRIAL_DAYS=7.
 * Default: disabled.
 */
export const ENABLE_PRO_TRIAL =
  process.env.NEXT_PUBLIC_ENABLE_PRO_TRIAL === 'true'

/**
 * Show the full-text filing search product (the /search route + its nav and footer entries).
 * Hidden by founder decision — it's our weakest offering — but kept in the codebase so it can be
 * reintroduced by flipping one flag. Same gate pattern as ENABLE_ANALYSIS/ENABLE_CALENDAR: the
 * /search route 404s while off, so the feature is hidden even from direct URLs / bookmarks, not
 * just from the nav. NOTE: this gates ONLY the full-text search page — the homepage's ticker
 * search (features/companies CompanySearch) is a separate product and is unaffected.
 * Flip NEXT_PUBLIC_ENABLE_FULLTEXT_SEARCH='true' to bring it back.
 * Default: disabled.
 */
export const ENABLE_FULLTEXT_SEARCH =
  process.env.NEXT_PUBLIC_ENABLE_FULLTEXT_SEARCH === 'true'
