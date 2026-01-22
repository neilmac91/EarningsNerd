import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SummaryBlock } from '@/components/SummaryBlock'
import { EmptyState } from '@/components/ui/EmptyState'

interface SummaryGuidanceProps {
  content: string | null
}

export function SummaryGuidance({ content }: SummaryGuidanceProps) {
  if (!content) return <EmptyState label="Guidance & Outlook" />

  return (
    <SummaryBlock type="neutral" title="Forward-Looking Statements">
      <div className="prose max-w-none prose-sm">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </SummaryBlock>
  )
}
