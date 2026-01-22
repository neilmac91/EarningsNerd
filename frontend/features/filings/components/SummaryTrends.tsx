import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SummaryBlock } from '@/components/SummaryBlock'
import { EmptyState } from '@/components/ui/EmptyState'
import { renderMarkdownValue } from '@/lib/formatters'

interface SummaryTrendsProps {
  threeYearTrend: unknown
  segmentPerformance: unknown
}

export function SummaryTrends({ threeYearTrend, segmentPerformance }: SummaryTrendsProps) {
  const hasContent = Boolean(threeYearTrend || segmentPerformance)
  
  if (!hasContent) return <EmptyState label="Trends & Segments" />

  return (
    <div className="space-y-6">
      {Boolean(threeYearTrend) && (
        <SummaryBlock type="bullish" title="Three-Year Trend Analysis">
           <div className="prose max-w-none prose-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {renderMarkdownValue(threeYearTrend)}
            </ReactMarkdown>
          </div>
        </SummaryBlock>
      )}
      {Boolean(segmentPerformance) && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-3">Segment Performance</h3>
          <div className="prose max-w-none prose-slate">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {renderMarkdownValue(segmentPerformance)}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}
