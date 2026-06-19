import React from 'react'
import { SummaryBlock } from '@/components/SummaryBlock'
import { EmptyState } from '@/components/ui/EmptyState'
import type { RiskFactor } from '@/types/summary'

interface SummaryRisksProps {
  risks: RiskFactor[]
}

/**
 * Trace-to-Source affordance: a quiet link back to the original SEC filing with an honest
 * verified/cited label. "Verified in filing" means the evidence excerpt was located in the filing
 * text (the link jumps to the exact passage); "Cited — open section" means we link to the section
 * but couldn't confirm the verbatim quote.
 */
function TraceToSource({ risk }: { risk: RiskFactor }) {
  const sectionRef = risk.source_section_ref?.trim() || null
  const url = risk.source_url?.trim() || null
  const verified = risk.source_verified === true

  if (!url && !sectionRef) return null

  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
      {sectionRef && (
        <span className="text-text-tertiary-light dark:text-text-tertiary-dark">{sectionRef}</span>
      )}
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 font-medium text-mint-600 hover:underline dark:text-mint-400"
          aria-label={
            verified
              ? 'View the verified source passage in the original SEC filing'
              : 'Open the cited section in the original SEC filing'
          }
        >
          <span aria-hidden="true">{verified ? '✓' : '↗'}</span>
          {verified ? 'Verified in filing' : 'Cited — open section'}
        </a>
      )}
    </div>
  )
}

export function SummaryRisks({ risks }: SummaryRisksProps) {
  if (!risks || risks.length === 0) return <EmptyState label="Risk Factors" />

  return (
    <div className="space-y-4">
      {risks.map((risk, index) => (
        <SummaryBlock
          key={`${risk.summary}-${index}`}
          type="bearish"
          title={risk.title || 'Risk Factor'}
        >
          <div className="space-y-2">
            <p>{risk.description || risk.summary}</p>
            <div className="mt-2 rounded border border-border-light bg-background-light p-2 text-xs text-text-secondary-light dark:border-border-dark dark:bg-background-dark dark:text-text-secondary-dark">
              <span className="mr-2 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary-light dark:text-text-tertiary-dark">
                Evidence
              </span>
              {risk.supporting_evidence}
              <TraceToSource risk={risk} />
            </div>
          </div>
        </SummaryBlock>
      ))}
    </div>
  )
}
