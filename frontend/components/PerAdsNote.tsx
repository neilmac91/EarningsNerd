import type { PerAdsValue } from '@/types/summary'

// Format the per-ADS figure in the issuer's reporting currency, matching the backend's
// code-prefixed style ("CNY 45.6") so the headline and the arithmetic caption read consistently.
function formatPerAds(value: number, currency?: string | null): string {
  const num = value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return currency ? `${currency} ${num}` : num
}

/**
 * Per-ADS EPS for ADRs (roadmap 1.5). XBRL reports earnings per *ordinary share*; ADR holders care
 * about the per-ADS figure. We show it WITH its conversion arithmetic inline and the sourced +
 * dated deposit-agreement ratio in the tooltip — so the correction is auditable, never an
 * unexplained number. Rendered only when the backend attached a `per_ads` block (ratio != 1 ADRs).
 */
export function PerAdsNote({ perAds }: { perAds: PerAdsValue }) {
  const tooltip = [perAds.source, perAds.as_of ? `as of ${perAds.as_of}` : null]
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
    <span
      className="mt-0.5 block whitespace-normal text-xs text-text-tertiary-light dark:text-text-secondary-dark"
      title={tooltip || undefined}
    >
      {hasValue && (
        <span className="font-medium text-text-secondary-light dark:text-text-secondary-dark">
          ≈ {formatPerAds(perAds.value, perAds.currency)} per ADS
        </span>
      )}
      {perAds.arithmetic && <span className="mt-0.5 block">{perAds.arithmetic}</span>}
    </span>
  )
}
