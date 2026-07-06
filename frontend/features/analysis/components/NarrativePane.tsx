'use client'

import { type ComponentProps, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Badge, Button, Card, Notice } from '@/components/ui'
import { ArrowClockwiseIcon, CircleNotchIcon, DownloadSimpleIcon } from '@/lib/icons'
import { injectCitationMarkers } from '@/lib/citationMarkers'
import type { AnalysisCitation, AnalysisCompletion } from '@/features/analysis/api/analysis-api'

const SOURCE_ROW_ID = (n: number | string) => `analysis-source-${n}`
const FLASH_MS = 1500

/** Scroll a Sources-list row into view and re-trigger its `.citation-flash` pulse (the same
 *  ambient token/technique the copilot filing-viewer highlight uses) so clicking an inline
 *  citation chip visibly connects the figure to its Sources entry. */
function flashAndScrollToSource(n: number | string) {
  const el = document.getElementById(SOURCE_ROW_ID(n))
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.remove('citation-flash')
  void el.offsetWidth // force reflow so a repeat click restarts the animation
  el.classList.add('citation-flash')
  window.setTimeout(() => el.classList.remove('citation-flash'), FLASH_MS)
}

/** An inline `[n]` citation chip: no filing viewer to highlight into (unlike Copilot), so
 *  clicking scrolls to + flashes the matching Sources row instead. The excerpt is exposed via
 *  `title` (hover) and `aria-label` (screen readers) — the full text is also visible below in
 *  the Sources list, so a heavier popover isn't needed here. */
function NarrativeCitationChip({ citation }: { citation: AnalysisCitation }) {
  const label = citation.section_ref || `Source ${citation.n}`
  return (
    <button
      type="button"
      onClick={() => flashAndScrollToSource(citation.n)}
      title={`${citation.excerpt}${citation.section_ref ? ` · ${citation.section_ref}` : ''}`}
      aria-label={`Citation ${citation.n}: ${label}. ${citation.excerpt}`}
      className="tnum inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded border px-1 align-baseline font-data text-[10px] font-semibold leading-none transition-colors border-brand-border bg-brand-weak text-brand-strong hover:bg-brand-border/60 dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark dark:hover:bg-brand-border-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
    >
      [{citation.n}]
    </button>
  )
}

type MdExtra = { node?: unknown }

/** Text-bearing element overrides that route their children through the citation-chip injector —
 *  no className overrides, since `.markdown-body`'s global CSS (globals.css) targets the plain
 *  tag names directly and must keep applying unchanged. */
function buildNarrativeComponents(citations: AnalysisCitation[]) {
  const inject = (children: ReactNode) =>
    injectCitationMarkers(children, citations, (citation, key) => (
      <NarrativeCitationChip key={key} citation={citation} />
    ))
  return {
    p: ({ node: _n, children, ...rest }: ComponentProps<'p'> & MdExtra) => <p {...rest}>{inject(children)}</p>,
    li: ({ node: _n, children, ...rest }: ComponentProps<'li'> & MdExtra) => <li {...rest}>{inject(children)}</li>,
    strong: ({ node: _n, children, ...rest }: ComponentProps<'strong'> & MdExtra) => (
      <strong {...rest}>{inject(children)}</strong>
    ),
    em: ({ node: _n, children, ...rest }: ComponentProps<'em'> & MdExtra) => <em {...rest}>{inject(children)}</em>,
    td: ({ node: _n, children, ...rest }: ComponentProps<'td'> & MdExtra) => <td {...rest}>{inject(children)}</td>,
  }
}

export interface NarrativeState {
  status: 'idle' | 'streaming' | 'done' | 'error'
  /** Raw streamed text while streaming; the resolved narrative after complete. */
  text: string
  stage?: string
  completion?: AnalysisCompletion
  error?: string
}

const VERIFIED_BADGE_BASE =
  'Every cited figure resolves to an exact SEC XBRL value or a figure computed from those values (marked Computed).'

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
        Sources — cited figures verified against SEC XBRL data
      </div>
      <ul className="space-y-1">
        {citations.map((citation) => (
          <li
            key={citation.n}
            id={SOURCE_ROW_ID(citation.n)}
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
            {state.status === 'done' && completion && completion.citations.length > 0 ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={buildNarrativeComponents(completion.citations)}
              >
                {state.text}
              </ReactMarkdown>
            ) : (
              // Streaming: raw [F#] markers render as plain text (no citations resolved yet) —
              // the citation-chip pass only applies to the server-resolved, completed narrative.
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.text}</ReactMarkdown>
            )}
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
