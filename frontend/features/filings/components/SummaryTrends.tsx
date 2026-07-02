import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SummaryBlock } from '@/components/SummaryBlock'
import { SectionEmpty } from './SectionEmpty'
import { renderMarkdownValue } from '@/lib/formatters'

interface SummaryTrendsProps {
  threeYearTrend: unknown
  segmentPerformance: unknown
}

export function SummaryTrends({ threeYearTrend, segmentPerformance }: SummaryTrendsProps) {
  const hasContent = Boolean(threeYearTrend || segmentPerformance)
  
  if (!hasContent) return <SectionEmpty label="Trends & Segments" />

  return (
    <div className="space-y-6">
      {Boolean(threeYearTrend) && (
        <SummaryBlock type="bullish" title="Three-Year Trend Analysis">
           <div className="prose max-w-none prose-sm dark:prose-invert">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {renderMarkdownValue(threeYearTrend)}
            </ReactMarkdown>
          </div>
        </SummaryBlock>
      )}
      {Boolean(segmentPerformance) && (
        <div className="mt-6">
          <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-3">Segment Performance</h3>
          <div className="prose max-w-none prose-slate dark:prose-invert text-text-secondary-light dark:text-text-secondary-dark">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {renderMarkdownValue(segmentPerformance)}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}
