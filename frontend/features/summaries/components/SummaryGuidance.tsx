import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SummaryBlock } from '@/features/summaries/components/SummaryBlock'
import { SectionEmpty } from './SectionEmpty'

interface SummaryGuidanceProps {
  content: string | null
}

export function SummaryGuidance({ content }: SummaryGuidanceProps) {
  if (!content) return <SectionEmpty label="Guidance & Outlook" />

  return (
    <SummaryBlock type="neutral" title="Forward-Looking Statements">
      <div className="prose max-w-none prose-sm dark:prose-invert">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </SummaryBlock>
  )
}
