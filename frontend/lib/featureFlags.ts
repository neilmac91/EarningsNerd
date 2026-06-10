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
