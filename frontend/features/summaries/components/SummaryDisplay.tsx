'use client'

import { useMemo, type Ref } from 'react'
import dynamic from 'next/dynamic'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import AiDisclaimer from '@/components/AiDisclaimer'
import type { Filing } from '@/features/filings/api/filings-api'
import type { ChangeReport, Summary } from '@/features/summaries/api/summaries-api'
import type { WordingContext } from '@/features/filings/components/WordingChanges'
import AskFilingCallout from '@/features/filings/components/copilot/AskFilingCallout'
import { SummaryBlocks } from '@/features/summaries/components/SummaryBlocks'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import { Button } from '@/components/ui/Button'
import { Badge, Card, CardBody, GuidanceCard } from '@/components/ui'
import { ChatCircleTextIcon } from '@/lib/icons'
import { ENABLE_QUALITY_BADGE, ENABLE_FINANCIAL_CHARTS } from '@/lib/featureFlags'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { ChangeReportCard } from './ChangeReportCard'
import { SummaryActionsBar, type SaveMutation } from './SummaryActionsBar'
import { useSummaryExports } from '../hooks/useSummaryExports'
import { useWhatChanged } from '../hooks/useWhatChanged'
import { cleanSummaryMarkdown, isSummaryFailure } from '../lib/summaryPlaceholder'

// Multi-period fundamentals trend (item 2.5), filing-scoped only — the company page no longer shows
// a company-wide trend (it would "refresh" on every new filing rather than reflect this document).
// recharts is heavy + DOM-only, so load it client-side like the other charts. It self-fetches and
// renders nothing until facts exist, so no loading fallback (which would flash an empty card before
// it decides). This is the page's single financial chart — it replaced the older current-vs-prior
// FinancialCharts, whose bar chart duplicated this one's metrics; the FinancialMetricsTable below
// still shows the numbers.
const FundamentalsTrendChart = dynamic(
  () => import('@/features/fundamentals/components/FundamentalsTrendChart'),
  { ssr: false },
)

// These exact server reason keys are held by test_quality_grounding_presence.py. Give
// readers the scope of each check without leaking internal diagnostics or asserting a
// figure is false: the literal-matching check can miss a valid presentation of the figure.
const GROUNDING_REASON = 'financial figures not grounded in SEC XBRL data'
const NO_GROUNDING_REASON = 'filing grounding unavailable: no usable excerpt or numeric XBRL data'
export function reasonWords(reason: string): string {
  if (reason === GROUNDING_REASON) return 'The filed revenue or net income was not found in the summary by the automatic check.'
  if (reason === NO_GROUNDING_REASON) return 'The filing’s text and figures were unavailable to check against.'
  const sections = /^only (\d+)\/(\d+) sections populated$/.exec(reason)
  if (sections) return `Only ${sections[1]} of ${sections[2]} summary sections contain information.`
  const figures = /^(\d+) summary figure\(s\) not traceable to filing data$/.exec(reason)
  if (figures) return `The automatic check could not trace ${figures[1]} summary figure${figures[1] === '1' ? '' : 's'} to the filing’s data.`
  return 'A coverage issue was recorded, but its details are unavailable.'
}

export interface SummaryDisplayProps {
  summary: Summary
  filing: Filing
  isPro: boolean
  saveMutation: SaveMutation
  isSaved: boolean
  debug?: boolean
  demoMode?: boolean
  isAuthenticated: boolean
  onRetry?: () => void
  /** Opens the Copilot rail with an optional pre-filled question; `surface` attributes the entry point. */
  onAsk: (prefill: string, surface: string) => void
  /** The server-read change report: What changed renders with the summary, not after it. */
  initialChangeReport?: ChangeReport
  /** The first content heading; the filing shell owns focus after a completed generation. */
  headingRef?: Ref<HTMLHeadingElement>
}

export function SummaryDisplay({
  summary,
  filing,
  isPro,
  saveMutation,
  isSaved,
  debug,
  demoMode,
  isAuthenticated,
  onRetry,
  onAsk,
  initialChangeReport,
  headingRef,
}: SummaryDisplayProps) {
  const markdownContent = summary.business_overview || ''
  // S4 honest degradation, decoupled: ALWAYS strip internal failure notices (they're not
  // user-facing copy), and let the quality badge + retry CTA carry the "partial" story instead.
  // This gives honest labeling without leaking raw internal text into the summary body.
  const cleanedMarkdown = useMemo(
    // Strip internal notices first (drops the optional leading disclaimer), then the now-leading
    // "## Executive Summary" H2 so the card shows ONE header — the DS CardTitle (T1.7).
    () => cleanSummaryMarkdown(markdownContent),
    [markdownContent]
  )
  const rawSummary = summary.raw_summary && typeof summary.raw_summary === 'object' ? summary.raw_summary : null
  const quality = rawSummary?.quality
  const isPartialQuality = ENABLE_QUALITY_BADGE && quality?.tier === 'partial'

  const { exportPdf, exportCsv } = useSummaryExports(filing)

  // A5 "What Changed": deterministic period-over-period diff (metric deltas, and the Item 1A wording
  // comparison the viewer is entitled to). DB-only/cheap on the backend; only renders when there's
  // something material to report. Seeded from the server read, so the section is in the first
  // render: a late insert pushed every later section down and renumbered the table of contents.
  const { report: changeReport, provisional: changeReportProvisional } = useWhatChanged(filing.id, initialChangeReport)
  const ticker = filing.company?.ticker ?? null
  const wordingIdentity = useMemo<Omit<WordingContext, 'provisional'>>(
    () => ({ filingId: filing.id, ticker, filingType: filing.filing_type, isAuthenticated }),
    [filing.id, ticker, filing.filing_type, isAuthenticated],
  )
  const whatChangedContext = useMemo<WordingContext>(
    () => ({ ...wordingIdentity, provisional: changeReportProvisional }),
    [wordingIdentity, changeReportProvisional],
  )

  const writerFallback = rawSummary?.writer?.fallback_used === true
  // A stored summary that failed (placeholder filler, a writer error, the fallback body, nothing left
  // once the notices are stripped) shows the error card, not its body. The company page's "summary
  // ready" reads the same rule (isSummaryReady), so its lead never offers a summary this page will not
  // show, and its "Summarize latest filing" lands on this card's Retry.
  const isError = isSummaryFailure(summary)
  const hasPolishedMarkdown = !isError

  const isPartial = rawSummary?.status === 'partial'
  // A generation marked partial must not read as full, even on an older row without
  // a quality verdict. An absent or unfamiliar verdict never implies completeness.
  const coverageTier = isPartial || quality?.tier === 'partial' ? 'partial' : quality?.tier === 'full' ? 'full' : 'unknown'
  const coverageReasons = [...new Set((quality?.reasons ?? []).map(reasonWords))]
  const showQualityBadge = ENABLE_QUALITY_BADGE
  const showRegenerate = Boolean(!demoMode && isPro && (isPartial || writerFallback || isPartialQuality) && onRetry)

  // T2: the single structured projection the page renders (metrics, risks-with-provenance, prose,
  // tables — one home per number). Computed on read by the backend from the enriched raw_summary.
  const renderedSections = summary.rendered_sections ?? []
  const hasSections = renderedSections.length > 0

  interface MetadataSections {
    action_items?: string[]
    [key: string]: unknown
  }

  const metadata: MetadataSections | null = rawSummary ? (rawSummary.sections as MetadataSections ?? null) : null

  // "AAPL’s 10-K" when the issuer is known, else the cleaner "this 10-K"; a filing with no ticker names its company in
  // its display casing.
  const subjectName = filing.company?.ticker || formatCompanyName(filing.company?.name)
  const askSubjectLabel = subjectName ? `${subjectName}’s ${filing.filing_type}` : `this ${filing.filing_type}`

  return (
    <div className="space-y-6">
      {/* Action Buttons */}
      <SummaryActionsBar
        key={filing.id}
        filingId={filing.id}
        summaryId={summary && summary.id ? summary.id : null}
        isAuthenticated={isAuthenticated}
        isSaved={isSaved}
        saveMutation={saveMutation}
        isPro={isPro}
        summaryFinished={!isError}
        onExportPdf={exportPdf}
        onExportCsv={exportCsv}
      />

      {isError ? (
        <>
          <GuidanceCard
            variant="error"
            title="This summary did not finish"
            headingLevel="h2"
            // The card's own sentence: SUMMARY_FALLBACK_MESSAGE is the backend's stored body (the
            // failure detector's token), and the failure stays until a retry, so "temporarily" promised
            // a timing the code does not keep.
            description="The last attempt for this filing did not finish. Try again to generate it."
            action={
              onRetry ? (
                <Button variant="secondary" onClick={onRetry}>
                  Try again
                </Button>
              ) : undefined
            }
          />
          {/* A stored summary that failed holds no sections, but the change report needs none. */}
          <ChangeReportCard filingId={filing.id} initialReport={initialChangeReport} context={wordingIdentity} />
        </>
      ) : (
        <>
          {/* Honest quality badge + Pro Regenerate affordance, when either applies. No "Summary"
              heading of its own: the numbered sections below are the document's headings under the
              page's h1 (2026-10 critique P-05). The body is the structured page (T2) — a number has
              exactly one home there, so no leading markdown card or duplicate metrics table renders. */}
          {(showQualityBadge || showRegenerate) && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              {showQualityBadge ? (
                <div className="min-w-0 flex-1 basis-64 space-y-2" role="group" aria-label="Summary coverage">
                  {/* A short label keeps Badge's one-line contract; full reasons wrap below it. */}
                  <Badge variant={coverageTier === 'full' ? 'brand' : coverageTier === 'partial' ? 'warning' : 'neutral'}>
                    {coverageTier === 'full' ? 'Full summary' : coverageTier === 'partial' ? 'Partial coverage' : 'Coverage unknown'}
                  </Badge>
                  <details className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                    <summary className="w-fit max-w-full cursor-pointer rounded-lg py-3 text-brand-strong dark:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
                      Coverage details
                    </summary>
                    <div className="space-y-2 pt-2">
                      <p>
                        {coverageTier === 'full'
                          ? 'This summary met the minimum coverage checks when it was generated. It may still omit sections or contain errors.'
                          : coverageTier === 'partial'
                            ? 'Some information could not be included or checked in this summary.'
                            : 'No coverage assessment is available for this summary.'}
                      </p>
                      {quality?.covered_count !== undefined && quality?.total_count !== undefined && (
                        <p>{quality.covered_count} of {quality.total_count} summary sections contain information.</p>
                      )}
                      {coverageReasons.length > 0 ? (
                        <ul className="list-disc space-y-2 pl-5">
                          {coverageReasons.map(reason => <li key={reason}>{reason}</li>)}
                        </ul>
                      ) : coverageTier === 'partial' ? (
                        <p>No further coverage details were recorded.</p>
                      ) : null}
                      <p>Coverage does not verify every claim. Check the cited sources and original filing.</p>
                    </div>
                  </details>
                </div>
              ) : (
                <span />
              )}
              {/* Pro-only force-regeneration (backend gates it to Pro); hidden in demo mode. */}
              {showRegenerate && (
                <Button variant="secondary" onClick={onRetry}>
                  Regenerate summary
                </Button>
              )}
            </div>
          )}

          {/* The ONE structured surface (T2): render_sections projection → per-section Cards + a
              sticky TOC. A legacy summary that produced no structured sections falls back to the
              derived markdown (belt-and-suspenders for the corpus-refresh cutover). */}
          {/* A5 "What changed" vs the prior comparable filing rides inside the structured page as a
              numbered section (2026-10 critique P-07); a legacy markdown summary keeps it as a card
              under the markdown, the card the page shows wherever no section holds it. */}
          {hasSections ? (
            <SummaryBlocks
              sections={renderedSections}
              summary={summary}
              whatChanged={changeReport}
              whatChangedContext={whatChangedContext}
              firstHeadingRef={headingRef}
            />
          ) : hasPolishedMarkdown ? (
            <>
              <Card as="section" className="overflow-hidden">
                <CardBody className="markdown-body text-text-secondary-light dark:text-text-secondary-dark">
                  <h2 ref={headingRef} tabIndex={headingRef ? -1 : undefined} className="outline-none">Summary</h2>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {cleanedMarkdown}
                  </ReactMarkdown>
                </CardBody>
              </Card>
              <ChangeReportCard filingId={filing.id} initialReport={initialChangeReport} context={wordingIdentity} />
            </>
          ) : null}

          {/* Turn the just-finished read into the next action — placed high, directly under the
              summary (T1.7 defect f). */}
          <AskFilingCallout filingType={filing.filing_type} subjectLabel={askSubjectLabel} onAsk={onAsk} />

          {/* 2.5 + roadmap B: multi-period trend of the standardized fundamentals (revenue/NI/EPS/…)
              *as reported in this filing* — the filing's own comparative years, an immutable snapshot
              faithful to the document. Self-fetches + self-gates (renders nothing until facts exist). */}
          {ENABLE_FINANCIAL_CHARTS && filing.id && (
            <ChartErrorBoundary>
              <FundamentalsTrendChart
                filingId={filing.id}
                subtitle={
                  filing.company?.ticker
                    ? `${filing.company.ticker} · figures as reported in this ${filing.filing_type}`
                    : `Figures as reported in this ${filing.filing_type}`
                }
              />
            </ChartErrorBoundary>
          )}

          {/* Web/PDF parity (audit): the exported PDF of this summary carries a disclaimer —
              the on-page surface must too, not just the global footer. */}
          <AiDisclaimer>
            May be incomplete or contain errors. The authoritative source is always the
            original SEC filing.
          </AiDisclaimer>
        </>
      )}

      {metadata?.action_items && Array.isArray(metadata.action_items) && metadata.action_items.length > 0 && (
        <Card as="section" className="p-cap-6">
          {/* h2, like the summary's sections: it follows them as a sibling, not inside the last one. */}
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-1">Suggested follow-ups</h2>
          <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark mb-3">Tap a question to ask this filing.</p>
          <ul className="space-y-2">
            {metadata.action_items.map((item: string, index: number) => (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => onAsk(item, 'followup')}
                  className="group flex w-full items-start gap-2 rounded-lg border border-border-light dark:border-white/10 bg-background-light/60 dark:bg-white/5 px-3 py-2 text-left text-sm text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-border hover:text-brand-strong dark:hover:border-brand-border-dark dark:hover:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                >
                  <ChatCircleTextIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
                  <span>{item}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {debug && rawSummary && (
        <section className="bg-panel-dark rounded-lg border border-border-dark p-4 text-xs text-text-primary-dark">
          {/* Explicit ink: the global h1–h6 --heading-color is theme-aware but not
              surface-aware — this section is fixed-dark in both themes. */}
          <h3 className="text-sm font-semibold mb-2 text-text-primary-dark">Debug: raw summary payload</h3>
          <pre className="whitespace-pre-wrap break-all">
            {JSON.stringify(rawSummary, null, 2)}
          </pre>
        </section>
      )}
    </div>
  )
}
