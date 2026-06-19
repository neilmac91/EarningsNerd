import React from 'react'

interface MetricSourceLinkProps {
  url?: string | null
  verified?: boolean | null
  /** XBRL concept label shown when the value is verified (e.g. "Revenue"). */
  concept?: string | null
}

/**
 * Trace-to-Source affordance for a financial metric. "✓ … SEC XBRL" means the displayed value was
 * matched against the SEC-verified XBRL figure; "↗ Source" links to the filing without that claim.
 * Renders nothing when no source URL is available (backward compatible with un-enriched data).
 */
export function MetricSourceLink({ url, verified, concept }: MetricSourceLinkProps) {
  if (!url) return null
  const label = verified ? `✓ ${concept ? `${concept} · ` : ''}SEC XBRL` : '↗ Source'
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-[11px] font-medium text-mint-600 hover:underline dark:text-mint-400"
      aria-label={
        verified
          ? 'View the SEC XBRL-verified value in the original filing'
          : 'Open the source filing'
      }
    >
      {label}
    </a>
  )
}
