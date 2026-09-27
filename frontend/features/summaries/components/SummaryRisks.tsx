import React from 'react'
import { SummaryBlock } from '@/features/summaries/components/SummaryBlock'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import type { RiskFactor } from '@/types/summary'

interface SummaryRisksProps {
  risks: RiskFactor[]
  projection?: {
    version?: number
    verified_count?: number
    withheld_count?: number
    source_available?: boolean
  }
}

/**
 * Trace-to-Source affordance for the server-owned source-first projection. Every item reaching this
 * component is an original filing span; unmatched/model-only risks are withheld on the server.
 */
function TraceToSource({ risk }: { risk: RiskFactor }) {
  if (!risk.source_url?.trim() && !risk.source_section_ref?.trim()) return null
  return (
    <div className="mt-2">
      <SourceTrace
        url={risk.source_url}
        verified={risk.source_verified === true}
        sectionRef={risk.source_section_ref}
        excerpt={risk.supporting_evidence}
      />
    </div>
  )
}

export function SummaryRisks({ risks, projection }: SummaryRisksProps) {
  const sourceFirst = projection?.version === 1
  const verified = sourceFirst && typeof projection.verified_count === 'number' ? projection.verified_count : 0
  const withheld = sourceFirst && typeof projection.withheld_count === 'number' ? projection.withheld_count : 0
  const notice = verified > 0
    ? `${verified} source-verified filing ${verified === 1 ? 'excerpt' : 'excerpts'}.${withheld > 0 ? ` ${withheld} ${withheld === 1 ? 'item' : 'items'} withheld because the evidence could not be matched.` : ''} Selected excerpts are not a complete risk inventory.`
    : `Source-verified risk excerpts are unavailable. Review the filing.${withheld > 0 ? ` ${withheld} ${withheld === 1 ? 'item' : 'items'} withheld because the evidence could not be matched.` : ''} Selected excerpts are not a complete risk inventory.`

  if (!sourceFirst) return <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{notice}</p>

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{notice}</p>
      {risks.map((risk, index) => (
        <SummaryBlock
          key={`${risk.summary}-${index}`}
          type="bearish"
          title={`Filing excerpt ${index + 1}`}
        >
          <div className="space-y-2">
            <div className="mt-2 rounded border border-border-light bg-background-light p-2 text-xs text-text-secondary-light dark:border-border-dark dark:bg-background-dark dark:text-text-secondary-dark">
              <span className="mr-2 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark">
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
