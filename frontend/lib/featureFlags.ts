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
