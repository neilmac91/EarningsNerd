'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Badge, Button, Card, Notice } from '@/components/ui'
import { ArrowClockwiseIcon, CircleNotchIcon, DownloadSimpleIcon } from '@/lib/icons'
import type { AnalysisCitation, AnalysisCompletion } from '@/features/analysis/api/analysis-api'

export interface NarrativeState {
  status: 'idle' | 'streaming' | 'done' | 'error'
  /** Raw streamed text while streaming; the resolved narrative after complete. */
  text: string
  stage?: string
  completion?: AnalysisCompletion
  error?: string
}

const VERIFIED_BADGE_BASE = 'Every cited figure resolves to an exact SEC XBRL value.'

function verifiedBadgeTitle(unverified: number | null | undefined): string {
  if (!unverified) return VERIFIED_BADGE_BASE
  const one = unverified === 1
  return `${VERIFIED_BADGE_BASE} ${unverified} reference${one ? '' : 's'} the model emitted could not be verified against the dataset and ${one ? 'was' : 'were'} removed.`
}

function CitationList({ citations }: { citations: AnalysisCitation[] }) {
  if (citations.length === 0) return null
  return (
    <div className="mt-4 border-t border-border-light pt-3 dark:border-white/10">
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
        Sources — cited figures verified against SEC XBRL
      </div>
      <ul className="space-y-1">
        {citations.map((citation) => (
          <li
            key={citation.n}
            className="tnum font-data flex items-baseline gap-2 text-xs text-text-secondary-light dark:text-text-secondary-dark"
          >
            <span className="shrink-0 rounded bg-brand-weak px-1.5 py-0.5 font-semibold text-brand-strong dark:bg-white/10 dark:text-brand-strong-dark">
              {citation.n}
            </span>
            <span>
              {citation.excerpt}
              {citation.section_ref && (
                <span className="ml-1 text-text-tertiary-light dark:text-text-secondary-dark">
                  · {citation.section_ref}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * The streamed AI narrative: live tokens while generating (raw [F#] markers and all), swapped for
 * the server-resolved narrative (+ verified Sources list) on complete — the Copilot handoff.
 */
export default function NarrativePane({
  state,
  onRefresh,
  refreshDisabled,
  onExport,
}: {
  state: NarrativeState
  /** The force-regenerate button (metered server-side; hidden when absent). */
  onRefresh?: () => void
  refreshDisabled?: boolean
  /** PDF download (Pro can_export; hidden when absent or before a persisted completion). */
  onExport?: () => void
}) {
  if (state.status === 'idle') return null

  const completion = state.completion
  const notEnoughData = completion?.kind === 'not_enough_data'

  return (
    <Card as="section" className="p-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            AI trend analysis
          </h2>
          {state.status === 'streaming' && (
            <span className="flex items-center gap-1.5 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
              <CircleNotchIcon className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              {state.stage === 'assembling' ? 'Assembling the numbers…' : 'Writing…'}
            </span>
          )}
          {state.status === 'done' && completion && !notEnoughData && (
            <Badge variant="solid" title={verifiedBadgeTitle(completion.unverified)}>
              {completion.grounded} verified citations
            </Badge>
          )}
          {state.status === 'done' && completion?.cached && (
            <Badge title="Served from a previous run of this exact period range — regenerates automatically when new filings arrive.">
              Cached
            </Badge>
          )}
        </div>
        {state.status === 'done' && !notEnoughData && (
          <div className="flex items-center gap-2">
            {onExport && completion?.analysis_id != null && (
              <Button size="sm" variant="secondary" onClick={onExport}>
                <DownloadSimpleIcon className="h-3.5 w-3.5" aria-hidden="true" />
                Export PDF
              </Button>
            )}
            {onRefresh && (
              <Button size="sm" variant="secondary" onClick={onRefresh} disabled={refreshDisabled}>
                <ArrowClockwiseIcon className="h-3.5 w-3.5" aria-hidden="true" />
                Refresh analysis
              </Button>
            )}
          </div>
        )}
      </div>

      {state.status === 'error' ? (
        <Notice
          variant="error"
          title={state.error || 'Something went wrong generating the analysis.'}
        />
      ) : notEnoughData ? (
        <Notice
          variant="info"
          title="Not enough reported history in the selected range for a meaningful analysis."
          description="Try widening the period range."
        />
      ) : (
        <>
          <div className="markdown-body" aria-live={state.status === 'streaming' ? 'polite' : undefined}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.text}</ReactMarkdown>
          </div>
          {state.status === 'done' && completion && <CitationList citations={completion.citations} />}
          {state.status === 'done' && completion && (
            <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
              AI-generated. Informational only — not investment advice. Cited figures resolve to
              SEC XBRL values; uncited statements are the model&apos;s interpretation and can be
              wrong.
            </p>
          )}
        </>
      )}
    </Card>
  )
}
