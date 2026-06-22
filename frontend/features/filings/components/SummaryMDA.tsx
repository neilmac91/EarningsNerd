import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { EmptyState } from '@/components/ui/EmptyState'
import { renderMarkdownValue } from '@/lib/formatters'

interface SummaryMDAProps {
  content: unknown
}

export function SummaryMDA({ content }: SummaryMDAProps) {
  if (!content) return <EmptyState label="Management Discussion" />

  return (
    <div className="prose max-w-none prose-slate dark:prose-invert text-slate-700 dark:text-slate-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {renderMarkdownValue(content)}
      </ReactMarkdown>
    </div>
  )
}
