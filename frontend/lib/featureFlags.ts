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
 * Enable tabbed section UI (Executive Summary, Financials, Risks, etc.)
 * When false, displays a single unified markdown summary view
 * Default: false (simplified view)
 */
export const ENABLE_SECTION_TABS =
  process.env.NEXT_PUBLIC_ENABLE_SECTION_TABS === 'true'

/**
 * Enable financial charts (Revenue, Net Income visualizations)
 * When false, charts are hidden from the UI
 * Default: false (charts hidden)
 */
export const ENABLE_FINANCIAL_CHARTS =
  process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS === 'true'

/**
 * Highlight a "Recommended" filing (latest 10-K, else latest filing) on the company page
 * with a one-click summary CTA, so first-time visitors don't have to decide between filing
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
 */
export const exampleFilingHref = (entry: string): string =>
  EXAMPLE_FILING_ID
    ? `/filing/${EXAMPLE_FILING_ID}?entry=${encodeURIComponent(entry)}`
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
 * Show the dashboard earnings calendar (upcoming earnings for watched companies).
 * Ships off by default — the backend `/api/dashboard/calendar/upcoming` returns empty until an
 * FMP_API_KEY is provisioned, so the widget stays dark until both are ready.
 * Flip NEXT_PUBLIC_ENABLE_CALENDAR='true' once FMP is configured.
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
 * Show the multi-filing Compare feature — the "Compare" nav entry, the watchlist CTA, and the
 * /compare + /compare/result routes (the routes 404 when this is off, so direct URLs are hidden too).
 * Ships OFF: the picker can't yet tell which filings have summaries, so comparing a freshly-fetched
 * filing dead-ends on a backend 404 ("Summary for filing N not found"). Hidden until that flow is
 * reworked. Flip NEXT_PUBLIC_ENABLE_COMPARE='true' to re-enable.
 * Default: disabled.
 */
export const ENABLE_COMPARE =
  process.env.NEXT_PUBLIC_ENABLE_COMPARE === 'true'
