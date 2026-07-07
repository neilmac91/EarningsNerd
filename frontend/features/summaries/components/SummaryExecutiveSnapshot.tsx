import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SectionEmpty } from './SectionEmpty'

interface SummaryExecutiveSnapshotProps {
  content: string
}

export function SummaryExecutiveSnapshot({ content }: SummaryExecutiveSnapshotProps) {
  if (!content) return <SectionEmpty label="executive summary" />
  
  return (
    <div className="prose max-w-none prose-slate dark:prose-invert text-text-secondary-light dark:text-text-secondary-dark">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
