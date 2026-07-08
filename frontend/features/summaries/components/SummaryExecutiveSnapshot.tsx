import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Badge } from '@/components/ui'
import { SectionEmpty } from './SectionEmpty'
import { parseExecutiveSnapshot, renderMarkdownValue } from '@/lib/formatters'

interface SummaryExecutiveSnapshotProps {
  snapshot: unknown
}

// tone -> Badge variant. neutral (and unknown) render NOTHING: tone is a schema field name,
// not user copy.
const TONE_VARIANT: Record<string, 'brand' | 'warning'> = {
  positive: 'brand',
  cautious: 'warning',
}

const Markdown = ({ text }: { text: string }) => (
  <div className="prose max-w-none prose-slate dark:prose-invert text-text-secondary-light dark:text-text-secondary-dark">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
  </div>
)

export function SummaryExecutiveSnapshot({ snapshot }: SummaryExecutiveSnapshotProps) {
  // Legacy/fallback: a plain markdown string (business_overview / MD&A) renders as prose.
  if (typeof snapshot === 'string') {
    return snapshot.trim() ? <Markdown text={snapshot} /> : <SectionEmpty label="executive summary" />
  }

  const parsed = parseExecutiveSnapshot(snapshot)
  // Off-schema object safety net: keep content visible rather than lose it (known shapes never
  // reach here, so the field-name label leak is killed for the real schema).
  if (!parsed) {
    const fallback = renderMarkdownValue(snapshot)
    return fallback ? <Markdown text={fallback} /> : <SectionEmpty label="executive summary" />
  }

  const toneVariant = parsed.tone ? TONE_VARIANT[parsed.tone.toLowerCase()] : undefined

  return (
    <div className="space-y-4 text-text-secondary-light dark:text-text-secondary-dark">
      {(parsed.headline || toneVariant) && (
        <div className="flex items-start justify-between gap-3">
          {parsed.headline && (
            <p className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">
              {parsed.headline}
            </p>
          )}
          {toneVariant && (
            <Badge variant={toneVariant} className="shrink-0 capitalize">
              {parsed.tone}
            </Badge>
          )}
        </div>
      )}
      {parsed.keyPoints.length > 0 && (
        <ul className="list-disc space-y-2 pl-5">
          {parsed.keyPoints.map((point, i) => (
            <li key={i} className="leading-relaxed">{point}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
