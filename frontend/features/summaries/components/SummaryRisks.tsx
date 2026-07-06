import React from 'react'
import { SummaryBlock } from '@/features/summaries/components/SummaryBlock'
import { SectionEmpty } from './SectionEmpty'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import type { RiskFactor } from '@/types/summary'

interface SummaryRisksProps {
  risks: RiskFactor[]
}

/**
 * Trace-to-Source affordance, rendered through the shared SourceTrace so risk provenance reads
 * identically to financial-metric provenance. "Verified in filing" means the evidence excerpt was
 * located in the filing text; "Cited" means we link to the section but couldn't confirm the verbatim
 * quote. The evidence excerpt stays visible inline above; this chip carries the section + EDGAR link.
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

export function SummaryRisks({ risks }: SummaryRisksProps) {
  if (!risks || risks.length === 0) return <SectionEmpty label="Risk Factors" />

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
