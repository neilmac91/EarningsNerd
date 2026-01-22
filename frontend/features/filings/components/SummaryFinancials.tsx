import React from 'react'
import { SummaryBlock } from '@/components/SummaryBlock'
import { EmptyState } from '@/components/ui/EmptyState'
import type { MetricItem } from '@/types/summary'

interface SummaryFinancialsProps {
  notes?: string
  metrics?: MetricItem[]
}

export function SummaryFinancials({ notes, metrics }: SummaryFinancialsProps) {
  const hasContent = Boolean(notes || (metrics && metrics.length > 0))
  
  if (!hasContent) return <EmptyState label="Financial Highlights" />

  return (
    <div className="space-y-4">
      {notes && (
        <SummaryBlock type="neutral" title="Analyst Notes">
           {notes}
        </SummaryBlock>
      )}
      {metrics && metrics.length > 0 && (
        <div className="text-sm text-slate-600">
          <p>Key highlights from the reporting period:</p>
          <ul className="list-disc list-inside mt-2 space-y-1">
            {metrics.slice(0, 5).map((m: MetricItem, i: number) => (
              <li key={i}>
                <span className="font-medium">{m.metric}:</span> {m.current_period} 
                <span className="text-slate-400 mx-1">vs</span> 
                {m.prior_period}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
