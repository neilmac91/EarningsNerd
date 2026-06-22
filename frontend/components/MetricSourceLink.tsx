import React from 'react'
import { SourceTrace } from '@/components/SourceTrace'

interface MetricSourceLinkProps {
  url?: string | null
  verified?: boolean | null
  /** XBRL concept label shown when the value is verified (e.g. "Revenue"). */
  concept?: string | null
}

/**
 * Trace-to-Source affordance for a financial metric, rendered through the shared SourceTrace so
 * metric and risk provenance read identically. "✓ … SEC XBRL" means the displayed value was matched
 * against the SEC-verified XBRL figure; otherwise a plain "Source" trace to the filing. Renders
 * nothing when no source URL is available (backward compatible with un-enriched data).
 */
export function MetricSourceLink({ url, verified, concept }: MetricSourceLinkProps) {
  if (!url) return null
  const isVerified = verified === true
  return (
    <SourceTrace
      url={url}
      verified={isVerified}
      label={isVerified ? `${concept ? `${concept} · ` : ''}SEC XBRL` : 'Source'}
      note={isVerified ? 'Matched against the SEC-filed XBRL value' : null}
    />
  )
}
