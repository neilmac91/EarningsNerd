import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { SummaryBlock } from '@/components/SummaryBlock'
import { EmptyState } from '@/components/ui/EmptyState'

interface SummaryLiquidityProps {
  liquidityContent: string | null
  footnotesContent: string | null
}

export function SummaryLiquidity({ liquidityContent, footnotesContent }: SummaryLiquidityProps) {
  const hasContent = Boolean(liquidityContent || footnotesContent)
  
  if (!hasContent) return <EmptyState label="Liquidity & Capital" />

  return (
    <div className="space-y-6">
      {liquidityContent && (
         <SummaryBlock type="neutral" title="Liquidity Position">
          <div className="prose max-w-none prose-sm dark:prose-invert">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {liquidityContent}
            </ReactMarkdown>
          </div>
        </SummaryBlock>
      )}
      {footnotesContent && (
         <div className="mt-4 border-t border-slate-200 dark:border-slate-800 pt-4">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2 uppercase tracking-wide">Notable Footnotes</h3>
          <div className="prose max-w-none prose-sm dark:prose-invert text-slate-600 dark:text-slate-300">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {footnotesContent}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}
