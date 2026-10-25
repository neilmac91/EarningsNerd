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
 * Flip NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY='true' to enable; the backend endpoint also needs
 * ENABLE_INSIDER_ACTIVITY=true (docs/CONFIGURATION.md), which the deploy pins off.
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
 * Draw Multi-Period Analysis's four trend charts with the spec renderer (step 4 of the trend-chart migration, E192;
 * docs/design/analysis-trend-charts-spec-2026-10.md): one SVG per chart from the chart engine's plan, instead of
 * Recharts. It covers /analysis and its locked teaser. The keyboard values stop, tooltip and column wash arrive in
 * step 5 (E193), so it stays off in production until the founder's switch decision (F66). Set
 * NEXT_PUBLIC_CHARTS_V2='true' for a preview or for CI's charts-v2 e2e job; never in vercel.json, whose env reaches
 * production.
 * Default: disabled.
 */
export const CHARTS_V2 = process.env.NEXT_PUBLIC_CHARTS_V2 === 'true'

/**
 * Name 20-F filings on the plan cards. Mirrors the API's ENABLE_FPI_FILINGS, which decides whether
 * foreign private issuers' filings are served at all (backend/app/config.py defaults it off; the API
 * deploy step sets it on). The Free plan line reads "10-K, 10-Q and 20-F filings from SEC EDGAR" only
 * while this flag is set and "10-K and 10-Q filings from SEC EDGAR" otherwise, so the cards never name
 * a form the API keeps off. Set it in lockstep with the API's flag (tasks/todo.md F39).
 * Default: disabled.
 */
export const ENABLE_FPI_FILINGS =
  process.env.NEXT_PUBLIC_ENABLE_FPI_FILINGS === 'true'

/**
 * Advertise the 7-day card-required Pro trial across the UI (pricing card CTA/note/FAQ, the
 * landing's plan table, the filing-page paywall card, the signup gate). MUST flip in lockstep with the
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

/**
 * Logo.dev publishable token presence. When set, company marks hotlink `img.logo.dev`
 * (components/CompanyLogo.tsx) and the routes that show marks as they load (the landing, a company
 * page, the calendar, every /dashboard route through its layout) preconnect to that host; a surface
 * whose marks follow a search (the analysis page, the search lists) does not. When unset, marks stay
 * on the ticker monogram and no preconnect is emitted.
 */
export const LOGO_DEV_ENABLED = Boolean(process.env.NEXT_PUBLIC_LOGO_DEV_TOKEN)

/** Local research evidence pack prototype. Default off; direct route returns 404. */
export const ENABLE_RESEARCH_EVIDENCE_PACKS =
  process.env.NEXT_PUBLIC_ENABLE_RESEARCH_EVIDENCE_PACKS === 'true'

/** Local research prototype. Hidden, including direct URLs, unless explicitly enabled. */
export const ENABLE_FILING_REDLINES =
  process.env.NEXT_PUBLIC_ENABLE_FILING_REDLINES === 'true'

/** Local financial-refresh review prototype. Default off; no navigation entry. */
export const ENABLE_FINANCIAL_REFRESH_REVIEW =
  process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_REFRESH_REVIEW === 'true'
