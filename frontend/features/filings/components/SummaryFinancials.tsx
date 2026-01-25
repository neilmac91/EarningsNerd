import React from 'react'
import { SummaryBlock } from '@/components/SummaryBlock'
import { EmptyState } from '@/components/ui/EmptyState'
import type { MetricItem } from '@/types/summary'

interface SummaryFinancialsProps {
  notes?: string
  metrics?: MetricItem[]
}

// Check if a value is a placeholder or missing
function isPlaceholder(value: string | undefined | null): boolean {
  if (!value) return true
  const placeholders = ['not available', 'n/a', '—', '-', 'unavailable', 'retry']
  return placeholders.some(p => value.toLowerCase().includes(p))
}

// Check if a metric has at least some real data
function hasRealData(metric: MetricItem): boolean {
  return !isPlaceholder(metric.current_period) || !isPlaceholder(metric.prior_period)
}

export function SummaryFinancials({ notes, metrics }: SummaryFinancialsProps) {
  // Filter to only metrics with real data
  const validMetrics = metrics?.filter(hasRealData) ?? []
  const hasContent = Boolean(notes || validMetrics.length > 0)

  if (!hasContent) return <EmptyState label="Financial Highlights" />

  return (
    <div className="space-y-4">
      {notes && (
        <SummaryBlock type="neutral" title="Analyst Notes">
           {notes}
        </SummaryBlock>
      )}
      {validMetrics.length > 0 && (
        <div className="text-sm text-slate-600">
          <p>Key highlights from the reporting period:</p>
          <ul className="list-disc list-inside mt-2 space-y-1">
            {validMetrics.slice(0, 5).map((m: MetricItem, i: number) => {
              const hasCurrent = !isPlaceholder(m.current_period)
              const hasPrior = !isPlaceholder(m.prior_period)

              return (
                <li key={i}>
                  <span className="font-medium">{m.metric}:</span>{' '}
                  {hasCurrent ? m.current_period : 'Data pending'}
                  {hasPrior && (
                    <>
                      <span className="text-slate-400 mx-1">vs</span>
                      {m.prior_period}
                    </>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
