import React from 'react'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { FIGURE_LINKED, FIGURE_MATCHED, figureNote, type FigureEvidence } from '@/features/filings/lib/evidenceLabels'

interface MetricSourceLinkProps extends Omit<FigureEvidence, 'verified'> {
  url?: string | null
  verified?: boolean | null
  /** Section heading (e.g. "Consolidated Statements of Operations") — the in-app jump target for
   * figures (item 1.4), since metrics carry no verbatim excerpt. */
  sectionRef?: string | null
  /** Pairs the chip with its copy in the other responsive layout (see SourceTrace's `layoutTwin`). */
  layoutTwin?: string
}

/**
 * Trace-to-Source affordance for a financial metric, rendered through the shared SourceTrace so
 * metric and risk provenance read identically. "Matches filing" means the server compared the row's
 * figures with the company's filed data and they agree, or it replaced a figure that did not with the
 * filed one, and the panel says which (lib/evidenceLabels.figureNote); any other figure reads "Linked,
 * not checked". Renders nothing when no source URL is available (backward compatible with un-enriched
 * data).
 */
export function MetricSourceLink({ url, verified, sectionRef, layoutTwin, filed, replaced, takeawayWithheld }: MetricSourceLinkProps) {
  if (!url) return null
  const isVerified = verified === true
  return (
    <SourceTrace
      url={url}
      verified={isVerified}
      sectionRef={sectionRef}
      kind="xbrl"
      label={isVerified ? FIGURE_MATCHED : FIGURE_LINKED}
      note={figureNote({ verified: isVerified, filed, replaced, takeawayWithheld })}
      layoutTwin={layoutTwin}
    />
  )
}
