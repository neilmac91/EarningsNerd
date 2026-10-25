'use client'

import { useMemo, useRef, type ComponentProps, type ElementType, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import AiDisclaimer from '@/components/AiDisclaimer'
import { Badge, Button, Card, Notice, countControlClass, cx } from '@/components/ui'
import { ArrowClockwiseIcon, CircleNotchIcon, DownloadSimpleIcon } from '@/lib/icons'
import { injectCitationMarkers } from '@/lib/citationMarkers'
import { flashElement } from '@/lib/citationFlash'
import type { AnalysisCitation, AnalysisCompletion } from '@/features/analysis/api/analysis-api'
import { sourceUrl, type FactProvenance } from '@/features/analysis/lib/provenance'
import { citationDisplay, compactNarrativeText, currencyAmountsNeedingPrecision, remarkAnalysisPeriods, remarkCompactAnalysis, splitNarrativeEvidence, type NarrativeOperand } from '@/features/analysis/lib/narrativeDisplay'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { prefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { groupQualityNotes, noteMarksFigure, qualityNotesModelFromWire, type QualityNotesModel } from '@/features/analysis/lib/dataNotes'
import { structuredNarrativeParts } from '@/features/analysis/lib/narrativePresentation'
import { usePrintDetails } from '@/features/analysis/lib/usePrintDetails'
import { useReportDataNotes } from './DataNotesContext'
import DataNoteMark, { dataNoteDescription } from './DataNoteMark'
import DataNotesLink from './DataNotesLink'
import { DataNotesList } from './DataNotes'

const SOURCE_ROW_ID = (n: number | string) => `analysis-source-${n}`

/** Scroll a Sources-list row into view and re-trigger its `.citation-flash` pulse (the shared
 *  flashElement helper the copilot filing-viewer highlight also uses) so clicking an inline
 *  citation chip visibly connects the figure to its Sources entry. */
function flashAndScrollToSource(n: number | string) {
  const el = document.getElementById(SOURCE_ROW_ID(n))
  if (!el) return
  el.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'center' })
  flashElement(el)
}

/** An inline `[n]` citation chip: no filing viewer to highlight into (unlike Copilot), so
 *  clicking scrolls to + flashes the matching Sources row instead. The excerpt is exposed via
 *  `title` (hover) and `aria-label` (screen readers) — the full text is also visible below in
 *  the Sources list, so a heavier popover isn't needed here. */
function NarrativeCitationChip({ citation, notes }: { citation: AnalysisCitation; notes: QualityNotesModel }) {
  const label = citation.section_ref || `Source ${citation.n}`
  const note = notes.noteForQuality(citation)
  const display = citationDisplay(citation)
  // Names only a note whose letter the chip shows (D-061); the rest are read in the Sources list's data notes.
  const described = dataNoteDescription(note)
  return (
    <button
      type="button"
      onClick={() => flashAndScrollToSource(citation.n)}
      title={`${display}${citation.section_ref ? ` · ${citation.section_ref}` : ''}`}
      aria-label={`Citation ${citation.n}: ${label}. ${display}${described ? `, ${described}` : ''}`}
      className="tnum inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded border px-1 align-baseline font-data text-xs font-semibold leading-none transition-colors border-brand-border bg-brand-weak text-brand-strong hover:bg-brand-border/60 dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark dark:hover:bg-brand-border-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
    >
      [{citation.n}]<DataNoteMark note={note} />
    </button>
  )
}

type MdExtra = { node?: unknown }
type NarrativeTag = 'p' | 'li' | 'strong' | 'em' | 'td'

/** Text-bearing element overrides that route their children through the citation-chip injector —
 *  no className overrides, since `.markdown-body`'s global CSS (globals.css) targets the plain
 *  tag names directly and must keep applying unchanged. */
function buildNarrativeComponents(citations: AnalysisCitation[], notes: QualityNotesModel) {
  const inject = (children: ReactNode) =>
    injectCitationMarkers(children, citations, (citation, key) => (
      <NarrativeCitationChip key={key} citation={citation} notes={notes} />
    ))
  // The five overrides differ only in tag name — one factory (strip react-markdown's `node`,
  // spread the rest, inject the children) instead of five hand-copied wrappers.
  const wrap = (tag: NarrativeTag) => {
    const Tag = tag as ElementType
    const MdTag = ({ node: _n, children, ...rest }: ComponentProps<NarrativeTag> & MdExtra) => (
      <Tag {...rest}>{inject(children)}</Tag>
    )
    return MdTag
  }
  return { p: wrap('p'), li: wrap('li'), strong: wrap('strong'), em: wrap('em'), td: wrap('td') }
}

/** Short evidence stays readable; a longer list names its notes even while folded. */
function NarrativeEvidence({ operands, citations, notes, preciseAmounts }: { operands: NarrativeOperand[]; citations: AnalysisCitation[]; notes: QualityNotesModel; preciseAmounts: ReadonlySet<string> }) {
  const figures = operands.map((operand) => ({
    ...operand,
    source: citations.find((citation) => citation.n === operand.citation)!,
    display: operand.formatted ? operand.value : compactNarrativeText(operand.value, preciseAmounts),
  }))
  if (figures.length <= 3) return <ul role="list" className="my-3 list-none !pl-0 text-sm" aria-label="Figures behind this finding">
    {figures.map((figure, index) => <li key={index} className="!m-0 inline">
      {figure.label} <span className="tnum">{figure.display}</span>, {formatAnalysisPeriod(figure.period)}{figure.derived && <DataNoteMark calculated announce />}{' '}
      <NarrativeCitationChip citation={figure.source} notes={notes} /><span aria-hidden="true">{index < figures.length - 1 ? '; ' : '.'}</span>
    </li>)}
  </ul>
  // The fold names the letters its chips show: only notes that question the number mark a figure (D-061).
  const noteKeys = new Set(figures.map((figure) => notes.noteForQuality(figure.source)?.key))
  const letters = notes.notes.filter((note) => noteKeys.has(note.key) && noteMarksFigure(note)).map((note) => note.letter)
  return <details className="my-3 text-sm">
    <summary className={cx('cursor-pointer rounded', countControlClass('summary'))}>
      Show the {figures.length} source figures behind this{letters.length > 0 && <> · figures carry {letters.length === 1 ? 'note' : 'notes'} {letters.join(', ')}</>}
    </summary>
    <ul role="list" className="mt-2 list-none !pl-0" aria-label="Figures behind this finding">
      {figures.map((figure, index) => <li key={index} className="!m-0 grid grid-cols-1 gap-x-3 gap-y-1 border-t border-border-light py-2 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto_auto] dark:border-white/10">
        <span className="font-data text-xs text-text-tertiary-light dark:text-text-tertiary-dark">{formatAnalysisPeriod(figure.period)}</span>
        <span>{figure.label}</span>
        <span className="font-data">{figure.display}{figure.derived && <DataNoteMark calculated announce />}</span>
        <span><NarrativeCitationChip citation={figure.source} notes={notes} /></span>
      </li>)}
    </ul>
  </details>
}

export interface NarrativeState {
  status: 'idle' | 'streaming' | 'done' | 'error'
  /** Raw streamed text while streaming; the resolved narrative after complete. */
  text: string
  stage?: string
  completion?: AnalysisCompletion
  error?: string
}

const SOURCE_BADGE_BASE =
  'Sources identify filed and calculated figures.'

/** The teaser's sample is one saved run of the pipeline (features/analysis/demo, D-046): its figures are the
 *  pipeline's, not approximations, but the run is not the reader's own. Readers do not know the word "pipeline", so
 *  the copy says "one saved analysis run" (tests/unit/narrative-pane.spec.tsx holds both words out). */
const SAMPLE_NOTE =
  'Sample data: figures and narrative from one saved analysis run. Run an analysis to see cited figures checked against the company’s filed data and source warnings shown for review.'

function sourceWarningText(
  unverified: number | null | undefined,
  mismatched?: number | null
): string {
  const warnings: string[] = []
  if (unverified) {
    const one = unverified === 1
    warnings.push(
      `${unverified} model source reference${one ? '' : 's'} did not resolve to the analysis dataset and ${one ? 'was' : 'were'} removed.`
    )
  }
  if (mismatched) {
    const one = mismatched === 1
    warnings.push(
      `${mismatched} figure${one ? '' : 's'} printed next to a source entry could not be reconciled with the listed dataset value. Check the Sources list before relying on the narrative ${one ? 'figure' : 'figures'}.`
    )
  }
  return warnings.join(' ')
}

function sourceBadgeTitle(unverified: number | null | undefined, mismatched?: number | null): string {
  const warning = sourceWarningText(unverified, mismatched)
  return warning ? `${SOURCE_BADGE_BASE} ${warning}` : SOURCE_BADGE_BASE
}

/** How a calculated source was made, keyed on its recorded reason: an empty input list alone does not prove a
 *  calculation predates kept inputs. */
function calculationWords(provenance: FactProvenance): string {
  if (provenance.reasons.includes('legacy_calculation')) return 'calculated before we kept its inputs'
  return provenance.inputs.length ? 'calculated from filed figures' : 'calculated figure'
}

function CitationList({ citations, sample, notes }: { citations: AnalysisCitation[]; sample?: boolean; notes: QualityNotesModel }) {
  if (citations.length === 0) return null
  return (
    <div className="mt-4 border-t border-border-light pt-3 dark:border-white/10">
      <div className="mb-2 text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark">
        {sample
          ? 'Sources · sample data (one saved run)'
          : 'Sources · filed and calculated figures'}
      </div>
      <ul className="space-y-1">
        {citations.map((citation) => (
          <li
            key={citation.n}
            id={SOURCE_ROW_ID(citation.n)}
            className="tnum font-data flex items-baseline gap-2 text-xs text-text-secondary-light dark:text-text-secondary-dark"
          >
            <span className="shrink-0 rounded bg-brand-weak px-1.5 py-0.5 font-semibold text-brand-strong dark:bg-white/10 dark:text-brand-strong-dark">
              [{citation.n}]
            </span>
            {/* min-w-0 lets this flex child shrink; break-words keeps long unbroken tokens
                (us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax) inside the card
                at mobile widths instead of overflowing it. */}
            <span className="min-w-0 break-words">
              {citationDisplay(citation)}
              <DataNoteMark note={notes.noteForQuality(citation)} calculated={citation.provenance?.method === 'calculated' || (!citation.provenance && citation.derived)} announce />
              {sourceUrl(citation.source_url ?? citation.provenance?.source_url) && <a className="ml-2 rounded text-brand-strong underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark" href={sourceUrl(citation.source_url ?? citation.provenance?.source_url)!} target="_blank" rel="noopener noreferrer" aria-label={`Original filing for source ${citation.n}: ${citation.concept?.replaceAll('_', ' ') || 'figure'}, ${citation.period ? formatAnalysisPeriod(citation.period) : 'period not recorded'}`}>Original filing</a>}
              {citation.section_ref && (
                <span className="ml-1 text-text-tertiary-light dark:text-text-tertiary-dark">
                  · {citation.provenance?.method === 'calculated' ? calculationWords(citation.provenance) : citation.provenance?.method === 'reported' ? 'SEC filing' : citation.section_ref}
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
 * the server-resolved narrative (+ Sources list) on complete — the Copilot handoff.
 */
export default function NarrativePane({
  state,
  onRefresh,
  refreshDisabled,
  onExport,
  sample = false,
}: {
  state: NarrativeState
  /** The force-regenerate button (metered server-side; hidden when absent). */
  onRefresh?: () => void
  refreshDisabled?: boolean
  /** PDF download (Pro can_export; hidden when absent or before a persisted completion). */
  onExport?: () => void
  /** Teaser mode: the payload is one saved run of the pipeline, not the reader's own analysis, so a
   *  "Sample data" badge stands in for the live run's source count and Cached badges (F3). */
  sample?: boolean
}) {
  const printScope = usePrintDetails()
  const completion = state.completion
  const reportNotes = useReportDataNotes()
  // A citation can retain its own concern even when the corresponding report value has a
  // different quality record. Reuse report letters; append citation-only notes without
  // changing dataset counts or inferring that a separately checked value clears the citation.
  const presentation = completion?.narrative_presentation
  const notes = useMemo(() => presentation
    ? qualityNotesModelFromWire(presentation.notes.notes)
    : groupQualityNotes(completion?.citations ?? [], reportNotes ?? undefined), [reportNotes, completion?.citations, presentation])
  const citedNoteKeys = new Set((completion?.citations ?? []).map((citation) => notes.noteForQuality(citation)?.key))
  const citedNotes = notes.notes.filter((note) => citedNoteKeys.has(note.key))
  const reportNoteKeys = new Set(reportNotes?.notes.map((note) => note.key))
  const supplementalNotes = citedNotes.filter((note) => !reportNoteKeys.has(note.key))
  const narrativeParts = useMemo(() => state.status === 'done'
    ? presentation ? structuredNarrativeParts(state.text, presentation) : splitNarrativeEvidence(state.text, completion?.citations ?? [])
    : [], [state.status, state.text, completion?.citations, presentation])
  const preciseAmounts = useMemo(() => currencyAmountsNeedingPrecision(state.status === 'done' ? state.text : ''), [state.status, state.text])
  const headingRef = useRef<HTMLHeadingElement>(null)
  // Stable components-map identity across re-renders — a fresh object every render would make
  // react-markdown treat each element type as new and remount the whole narrative subtree
  // (losing e.g. focus on a citation chip) instead of reconciling it.
  const narrativeComponents = useMemo(
    () =>
      completion && completion.citations.length > 0
        ? buildNarrativeComponents(completion.citations, notes)
        : undefined,
    [completion, notes]
  )

  if (state.status === 'idle') return null

  const notEnoughData = completion?.kind === 'not_enough_data'
  const sourceWarning =
    completion && !sample
      ? sourceWarningText(completion.unverified, completion.mismatched)
      : ''

  return (
    <Card as="section" className="p-4 sm:p-cap-6" data-analysis-print-scope={printScope}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h2
            ref={headingRef}
            tabIndex={-1}
            className="text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
          >
            AI trend analysis
          </h2>
          {state.status === 'streaming' && (
            <span className="flex items-center gap-1.5 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
              <CircleNotchIcon className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
              {state.stage === 'assembling' ? 'Assembling the numbers…' : 'Writing…'}
            </span>
          )}
          {state.status === 'done' && completion && !notEnoughData && sample && (
            <Badge title={SAMPLE_NOTE}>
              Sample data
            </Badge>
          )}
          {state.status === 'done' && completion && !notEnoughData && !sample && (
            <Badge
              title={sourceBadgeTitle(completion.unverified, completion.mismatched)}
            >
              {completion.grounded} {completion.grounded === 1 ? 'source' : 'sources'}
            </Badge>
          )}
          {state.status === 'done' && <DataNotesLink notes={citedNotes} />}
          {state.status === 'done' && completion?.cached && !sample && (
            // The explanation is a visible line, not a title tooltip: a phone or a keyboard never shows a title.
            <>
              <Badge>Cached</Badge>
              <span className="text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
                Served from an earlier run · regenerates if these figures change
              </span>
            </>
          )}
        </div>
        {state.status === 'done' && !notEnoughData && (
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {onExport && completion?.analysis_id != null && (
              <Button size="sm" variant="secondary" wrap className="max-w-full" onClick={onExport}>
                <DownloadSimpleIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Export PDF
              </Button>
            )}
            {onRefresh && (
              // Refresh restarts the stream, which unmounts this row and the focused button with it;
              // hand focus to the heading first so a keyboard user is not dropped to <body>.
              // `loading`, never native `disabled`, for refreshDisabled: Chromium blurs a focused
              // button that turns disabled.
              <Button
                size="sm"
                variant="secondary"
                wrap
                className="max-w-full"
                onClick={(e) => {
                  if (document.activeElement === e.currentTarget) headingRef.current?.focus({ preventScroll: true })
                  onRefresh()
                }}
                loading={refreshDisabled}
                leftIcon={<ArrowClockwiseIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
              >
                Refresh analysis
              </Button>
            )}
          </div>
        )}
      </div>

      {state.status === 'done' && completion && !notEnoughData && sourceWarning && (
        <Notice
          variant="info"
          className="mb-4"
          title="Some source references need attention"
          description={sourceWarning}
        />
      )}

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
            {state.status === 'done' && completion ? (
              narrativeParts.map((part, index) => part.kind === 'evidence' ? (
                <NarrativeEvidence key={index} operands={part.operands} citations={completion.citations} notes={notes} preciseAmounts={preciseAmounts} />
              ) : (
                <ReactMarkdown key={index} remarkPlugins={completion.narrative_presentation ? [remarkGfm, remarkAnalysisPeriods] : [remarkGfm, [remarkCompactAnalysis, { preciseAmounts }]]} components={narrativeComponents}>
                  {part.text}
                </ReactMarkdown>
              ))
            ) : (
              // Streaming: raw [F#] markers render as plain text (no citations resolved yet) —
              // the citation-chip pass only applies to the server-resolved, completed narrative.
              // A period window still reads as its range while it streams.
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkAnalysisPeriods]}>{state.text}</ReactMarkdown>
            )}
          </div>
          {state.status === 'done' && completion && (
            <CitationList citations={completion.citations} sample={sample} notes={notes} />
          )}
          {state.status === 'done' && supplementalNotes.length > 0 && <details className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark"><summary className="cursor-pointer rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Data notes for these sources</summary><div className="mt-2"><DataNotesList notes={supplementalNotes} /></div></details>}
          {state.status === 'done' && completion && (
            <AiDisclaimer className="mt-3">
              {sample
                ? SAMPLE_NOTE
                : 'Source entries identify filed figures or computed figures. They do not verify every nearby narrative figure or conclusion. The analysis can be incomplete or wrong.'}
            </AiDisclaimer>
          )}
        </>
      )}
    </Card>
  )
}
