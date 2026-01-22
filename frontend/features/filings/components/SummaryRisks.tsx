import React from 'react'
import { SummaryBlock } from '@/components/SummaryBlock'
import { EmptyState } from '@/components/ui/EmptyState'
import type { RiskFactor } from '@/types/summary'

interface SummaryRisksProps {
  risks: RiskFactor[]
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
            <div className="mt-2 text-xs bg-rose-50 text-rose-800 p-2 rounded border border-rose-100">
              <span className="font-semibold uppercase tracking-wider text-[10px] mr-2">Evidence</span>
              {risk.supporting_evidence}
            </div>
          </div>
        </SummaryBlock>
      ))}
    </div>
  )
}
