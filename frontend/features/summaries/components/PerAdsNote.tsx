import type { PerAdsValue } from '@/types/summary'
import { fmtDecimal } from '@/lib/format'

// Format the per-ADS figure in the issuer's reporting currency, matching the backend's
// code-prefixed style ("CNY 45.6") so the headline and the arithmetic caption read consistently.
function formatPerAds(value: number, currency?: string | null): string {
  const num = fmtDecimal(value, { maxDigits: 2 })
  return currency ? `${currency} ${num}` : num
}

/**
 * Per-ADS EPS for ADRs (roadmap 1.5). XBRL reports earnings per *ordinary share*; ADR holders care
 * about the per-ADS figure. We show it WITH its conversion arithmetic inline and the sourced +
 * dated deposit-agreement ratio as a visible line under it (a title tooltip never shows on touch and
 * no keyboard reaches it) — so the correction is auditable, never an unexplained number. Rendered
 * only when the backend attached a `per_ads` block (ratio != 1 ADRs).
 */
// The backend's ratio registry (backend/app/services/edgar/ads_ratios.py) joins the document and the
// ratio with a colon, the product's separator, since E45; a payload cached before then (the ratio rides
// xbrl_data) joins them with an em-dash, which the visible line reads as the same colon.
const SOURCE_DASH = /\s*\u2014\s*/g

export function PerAdsNote({ perAds }: { perAds: PerAdsValue }) {
  const source = perAds.source ? perAds.source.replace(SOURCE_DASH, ': ') : null
  const ratioSource = [source, perAds.as_of ? `as of ${perAds.as_of}` : null]
    .filter(Boolean)
    .join(' · ')
  // Defensive against a malformed payload: `value` is typed `number`, but this rides runtime JSON
  // from the backend, so only render the figure when it's a real finite number (never "≈ NaN").
  // The arithmetic is a backend-built string and is safe to show on its own.
  const hasValue = typeof perAds.value === 'number' && Number.isFinite(perAds.value)
  if (!hasValue && !perAds.arithmetic) return null

  return (
    // whitespace-normal: the metrics-table cell sets whitespace-nowrap (to keep the headline figure
    // on one line), and `white-space` inherits — without this the arithmetic caption can't wrap and
    // would overflow the column.
    <span className="mt-0.5 block whitespace-normal text-xs text-text-tertiary-light dark:text-text-secondary-dark">
      {hasValue && (
        <span className="font-medium text-text-secondary-light dark:text-text-secondary-dark">
          ≈ {formatPerAds(perAds.value, perAds.currency)} per ADS
        </span>
      )}
      {perAds.arithmetic && <span className="mt-0.5 block">{perAds.arithmetic}</span>}
      {ratioSource && <span className="mt-0.5 block">Ratio source: {ratioSource}</span>}
    </span>
  )
}
