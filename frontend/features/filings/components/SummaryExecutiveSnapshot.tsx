import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { EmptyState } from '@/components/ui/EmptyState'

interface SummaryExecutiveSnapshotProps {
  content: string
}

export function SummaryExecutiveSnapshot({ content }: SummaryExecutiveSnapshotProps) {
  if (!content) return <EmptyState label="Executive Summary" />
  
  return (
    <div className="prose max-w-none prose-slate dark:prose-invert text-slate-700 dark:text-slate-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
