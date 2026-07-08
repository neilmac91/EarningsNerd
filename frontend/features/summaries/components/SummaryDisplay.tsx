'use client'

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import dynamic from 'next/dynamic'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import AiDisclaimer from '@/components/AiDisclaimer'
import type { Filing } from '@/features/filings/api/filings-api'
import { getWhatChanged, type Summary } from '@/features/summaries/api/summaries-api'
import { WhatChanged } from '@/features/filings/components/WhatChanged'
import AskFilingCallout from '@/features/filings/components/copilot/AskFilingCallout'
import { SummaryBlocks } from '@/features/summaries/components/SummaryBlocks'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import { Button } from '@/components/ui/Button'
import { Badge, Card, CardBody, GuidanceCard } from '@/components/ui'
import { FileTextIcon, SparkleIcon } from '@/lib/icons'
import { stripInternalNotices } from '@/lib/stripInternalNotices'
import { stripLeadingExecutiveHeading } from '@/lib/stripLeadingExecutiveHeading'
import { ENABLE_QUALITY_BADGE, ENABLE_FINANCIAL_CHARTS } from '@/lib/featureFlags'
import { queryKeys } from '@/lib/queryKeys'
import { SummaryActionsBar, type SaveMutation } from './SummaryActionsBar'
import { useSummaryExports } from '../hooks/useSummaryExports'

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

// P0-2 badge de-escalation (data-quality plan, safeguard #5): the XBRL literal-grounding check
// is a heuristic — when it is the ONLY partial reason, render neutral wording instead of an
// accusatory data-integrity verdict (it false-fired on every bank pre-fix). The full reason
// list stays available in the badge tooltip.
const GROUNDING_REASON = 'financial figures not grounded in SEC XBRL data'
export function partialBadgeLabel(reasons: string[] | undefined): string {
  if (reasons && reasons.length === 1 && reasons[0] === GROUNDING_REASON) {
    return 'Partial coverage'
  }
  return `Partial${reasons && reasons.length ? ` · ${reasons[0]}` : ''}`
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
}: SummaryDisplayProps) {
  const markdownContent = summary.business_overview || ''
  // S4 honest degradation, decoupled: ALWAYS strip internal failure notices (they're not
  // user-facing copy), and let the quality badge + retry CTA carry the "partial" story instead.
  // This gives honest labeling without leaking raw internal text into the summary body.
  const cleanedMarkdown = useMemo(
    // Strip internal notices first (drops the optional leading disclaimer), then the now-leading
    // "## Executive Summary" H2 so the card shows ONE header — the DS CardTitle (T1.7).
    () => stripLeadingExecutiveHeading(stripInternalNotices(markdownContent)),
    [markdownContent]
  )
  const rawSummary = summary.raw_summary && typeof summary.raw_summary === 'object' ? summary.raw_summary : null
  const quality = rawSummary?.quality as { tier?: string; reasons?: string[] } | undefined
  const isPartialQuality = ENABLE_QUALITY_BADGE && quality?.tier === 'partial'

  const { exportPdf, exportCsv } = useSummaryExports(filing)

  // A5 "What Changed": deterministic period-over-period diff (metric deltas, risk changes, key
  // changes). DB-only/cheap on the backend; only renders when there's something material to report.
  const { data: changeReport } = useQuery({
    queryKey: queryKeys.whatChanged(filing.id),
    queryFn: () => getWhatChanged(filing.id),
    staleTime: 10 * 60 * 1000,
  })

  const fallbackMessage = 'Summary temporarily unavailable. Please retry.'
  const writerError = rawSummary?.writer_error
  const writerFallback = rawSummary?.writer?.fallback_used === true
  const trimmedMarkdown = cleanedMarkdown.trim()
  const isFallbackMessage = trimmedMarkdown === fallbackMessage
  const hasPolishedMarkdown = trimmedMarkdown.length > 0 && !isFallbackMessage && !writerError

  const isPartial = rawSummary?.status === 'partial'

  const isError = Boolean(writerError) || isFallbackMessage || (!hasPolishedMarkdown && trimmedMarkdown.length === 0)

  // T2: the single structured projection the page renders (metrics, risks-with-provenance, prose,
  // tables — one home per number). Computed on read by the backend from the enriched raw_summary.
  const renderedSections = summary.rendered_sections ?? []
  const hasSections = renderedSections.length > 0

  interface MetadataSections {
    action_items?: string[]
    [key: string]: unknown
  }

  const metadata: MetadataSections | null = rawSummary ? (rawSummary.sections as MetadataSections ?? null) : null

  // "AAPL’s 10-K" when the issuer is known, else the cleaner "this 10-K".
  const subjectName = filing.company?.ticker || filing.company?.name
  const askSubjectLabel = subjectName ? `${subjectName}’s ${filing.filing_type}` : `this ${filing.filing_type}`

  return (
    <div className="space-y-6">
      {/* Action Buttons */}
      <SummaryActionsBar
        summaryId={summary && summary.id ? summary.id : null}
        isAuthenticated={isAuthenticated}
        isSaved={isSaved}
        saveMutation={saveMutation}
        isPro={isPro}
        onExportPdf={exportPdf}
        onExportCsv={exportCsv}
      />

      {isError ? (
        <GuidanceCard
          variant="error"
          title="Summary temporarily unavailable"
          description={fallbackMessage}
          action={
            onRetry ? (
              <Button variant="secondary" onClick={onRetry}>
                Retry
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          {/* Summary header: title + honest quality badge + Pro Regenerate affordance. The body is
              the structured page below (T2) — a number has exactly one home there, so no leading
              markdown card or duplicate metrics table renders anymore. */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <FileTextIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
              <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Summary</h2>
              {/* S4 quality badge: honest signal of full vs partial output. Suppressed in demo mode
                  so a first-time visitor never meets "Partial" on the curated example (plan 1.3). */}
              {!demoMode && ENABLE_QUALITY_BADGE && quality?.tier && (
                <Badge
                  variant={quality.tier === 'full' ? 'brand' : 'warning'}
                  title={quality.reasons && quality.reasons.length ? quality.reasons.join('; ') : undefined}
                >
                  {quality.tier === 'full' ? 'Full summary' : partialBadgeLabel(quality.reasons)}
                </Badge>
              )}
            </div>
            {/* Pro-only force-regeneration (backend gates it to Pro); hidden in demo mode. */}
            {!demoMode && isPro && (isPartial || writerFallback || isPartialQuality) && onRetry && (
              <Button variant="secondary" onClick={onRetry}>
                Regenerate Analysis
              </Button>
            )}
          </div>

          {/* The ONE structured surface (T2): render_sections projection → per-section Cards + a
              sticky TOC. A legacy summary that produced no structured sections falls back to the
              derived markdown (belt-and-suspenders for the corpus-refresh cutover). */}
          {hasSections ? (
            <SummaryBlocks sections={renderedSections} summary={summary} />
          ) : hasPolishedMarkdown ? (
            <Card as="section" className="overflow-hidden">
              <CardBody className="markdown-body text-text-secondary-light dark:text-text-secondary-dark">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {cleanedMarkdown}
                </ReactMarkdown>
              </CardBody>
            </Card>
          ) : null}

          {/* Turn the just-finished read into the next action — placed high, directly under the
              summary (T1.7 defect f). */}
          <AskFilingCallout filingType={filing.filing_type} subjectLabel={askSubjectLabel} onAsk={onAsk} />

          {/* A5: What Changed vs the prior comparable filing */}
          {changeReport?.has_changes && <WhatChanged report={changeReport} />}

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
        <Card as="section" className="p-6">
          <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-1">Suggested follow-ups</h3>
          <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark mb-3">Tap a question to ask the Copilot.</p>
          <ul className="space-y-2">
            {metadata.action_items.map((item: string, index: number) => (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => onAsk(item, 'followup')}
                  className="group flex w-full items-start gap-2 rounded-lg border border-border-light dark:border-white/10 bg-background-light/60 dark:bg-white/5 px-3 py-2 text-left text-sm text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:border-brand-border hover:text-brand-strong dark:hover:text-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                >
                  <SparkleIcon className="mt-0.5 h-4 w-4 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
                  <span>{item}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {debug && rawSummary && (
        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4 text-xs text-gray-100">
          {/* Explicit ink: the global h1–h6 --heading-color is theme-aware but not
              surface-aware — this section is fixed-dark in both themes. */}
          <h3 className="text-sm font-semibold mb-2 text-gray-100">Debug: raw summary payload</h3>
          <pre className="whitespace-pre-wrap break-all">
            {JSON.stringify(rawSummary, null, 2)}
          </pre>
        </section>
      )}
    </div>
  )
}
