'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getFiling, Filing } from '@/features/filings/api/filings-api'
import { saveSummary, getSavedSummaries, SavedSummary, type Summary } from '@/features/summaries/api/summaries-api'
import AskCopilotRail from '@/features/filings/components/copilot/AskCopilotRail'
import FilingViewer from '@/features/filings/components/copilot/FilingViewer'
import FilingWorkspace from '@/features/filings/components/copilot/FilingWorkspace'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'
import AskAboutSelection from '@/features/filings/components/copilot/AskAboutSelection'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { CircleNotchIcon, SparkleIcon } from '@/lib/icons'
import Link from 'next/link'
// formatLocalDate (not date-fns format(new Date(...))): filing dates are UTC-midnight instants;
// local-TZ rendering shifts the calendar day west of UTC and, now that this page is
// server-rendered with data, would also cause a server/client hydration mismatch.
import { formatLocalDate } from '@/lib/format'
import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { Badge } from '@/components/ui'
import analytics from '@/lib/analytics'
import { getEntryPoint } from '@/lib/entryPoint'
import { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import { queryKeys } from '@/lib/queryKeys'
import StreamingSummaryDisplay from './StreamingSummaryDisplay'
import { TickerFilingsView } from '@/features/filings/components/TickerFilingsView'
import { SummaryDisplay } from '@/features/summaries/components/SummaryDisplay'
import { GenerateSignupGate } from '@/features/summaries/components/GenerateSignupGate'
import { useSummaryGeneration } from '@/features/summaries/hooks/useSummaryGeneration'

// StreamingSummaryDisplay + its stage constants live in ./StreamingSummaryDisplay.
// The summary-generation state machine lives in features/summaries/hooks/useSummaryGeneration;
// the summary/ticker views live in features/. This file is the route shell + layout wiring.

interface FilingSeedProps {
  /** Server-fetched seeds (SEO/ISR — see page.tsx): the first server render carries the real
   * filing header + summary so crawlers get HTML, not a spinner. `initialSummary: null` means
   * the backend confirmed no summary exists; `undefined` means unknown (client refetches). */
  initialFiling?: Filing
  initialSummary?: Summary | null
}

function FilingDetailView({ filingId, initialFiling, initialSummary }: { filingId: number } & FilingSeedProps) {
  const router = useRouter()

  // debug/demo URL flags. Read post-hydration from window.location rather than useSearchParams():
  // this page statically renders (ISR), and a useSearchParams() outside Suspense would bail the
  // whole tree out of the server HTML — the exact thing the SSR seeds exist for. Both flags only
  // suppress/augment chrome (quality badge, debug panel), so applying them a frame late is fine.
  const [urlFlags, setUrlFlags] = useState({ debug: false, demo: false })
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const debug = params.get('debug') === '1'
    const demo = params.get('demo') === '1'
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot post-hydration sync of URL flags; reading window.location during render would mismatch the server HTML
    if (debug || demo) setUrlFlags({ debug, demo })
  }, [])

  const [copilotOpen, setCopilotOpen] = useState(false)
  // "Ask about this" text selection → open the rail + pre-fill the composer.
  const [copilotPrefill, setCopilotPrefill] = useState<{ text: string; nonce: number } | null>(null)
  const summaryContentRef = useRef<HTMLElement>(null)
  const hasTrackedFilingView = useRef(false)
  const hasTrackedSummaryGenerated = useRef(false)
  const hasTrackedSummaryViewed = useRef(false)
  // eslint-disable-next-line react-hooks/purity -- seeds an analytics dwell-time ref with the first-render timestamp; value is captured once and only read in effects/handlers, never affecting render output
  const viewStartedAt = useRef<number>(Date.now())
  const entryPoint = useMemo(() => getEntryPoint(), [])

  const { data: currentUser, isPending: authPending } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isAuthenticated = Boolean(currentUser)
  // Settled /me query (data OR error): before this, isAuthenticated is false for EVERYONE, so the
  // signup gate / auto-generate decision must wait or logged-in visitors would flash the gate.
  const isAuthResolved = !authPending

  // initialDataUpdatedAt: 0 marks the ISR-cached seed as already stale so the client refetches
  // on mount — the seed only guarantees the first paint (and the crawler HTML).
  const { data: filing, isLoading: filingLoading } = useQuery<Filing>({
    queryKey: queryKeys.filing(filingId),
    queryFn: () => getFiling(filingId),
    initialData: initialFiling,
    initialDataUpdatedAt: 0,
  })

  const {
    summary,
    summaryLoading,
    streamingText,
    streamingStage,
    streamingMessage,
    elapsedSeconds,
    generationError,
    activeErrorMessage,
    isStreaming,
    hasStartedGeneration,
    hasSummaryContent,
    handleRegenerateSummary,
  } = useSummaryGeneration({ filingId, filing, isAuthenticated, isAuthResolved, entryPoint, initialSummary })

  // Single entry point for every "Ask" affordance (callout CTA, starter chips, tappable follow-ups,
  // coachmark, text selection): open the rail, optionally pre-fill, and attribute the surface. FREE
  // users land on the in-rail teaser (the prefill is a no-op for them), preserving the Pro gating.
  const handleAskCopilot = useCallback((prefillText: string, surface: string) => {
    if (filing) {
      analytics.copilotEntryClicked({
        filingId: filing.id,
        ticker: filing.company?.ticker ?? null,
        filingType: filing.filing_type,
        surface,
      })
    }
    setCopilotOpen(true)
    const text = prefillText.trim()
    // Reset to null when there's no prefill (e.g. the generic "Ask this filing" CTA) so we never
    // retain a stale prefill from an earlier starter/follow-up click.
    setCopilotPrefill(text ? { text, nonce: Date.now() } : null)
  }, [filing])
  const handleAskAboutSelection = useCallback((text: string) => {
    // Cap so the templated question stays under the backend's 2000-char question limit.
    const snippet = text.length > 1500 ? `${text.slice(0, 1500)}…` : text
    handleAskCopilot(`Explain this excerpt: "${snippet}"`, 'selection')
  }, [handleAskCopilot])

  // Smart back navigation handler
  const handleBack = () => {
    if (typeof window === 'undefined') return

    // Check if user navigated from within the app (has referrer from same origin)
    const referrer = document.referrer
    const currentOrigin = window.location.origin

    // If referrer exists and is from same origin, use browser back navigation
    // This preserves the user's navigation flow (e.g., from company page)
    if (referrer && referrer.startsWith(currentOrigin)) {
      // Use browser back to return to previous page in history
      router.back()
      return
    }

    // Fallback: navigate to company page if filing has company data
    // This handles cases where user came directly via URL or external link
    if (filing?.company?.ticker) {
      router.push(`/company/${filing.company.ticker}`)
      return
    }

    // Last resort: go to homepage
    router.push('/')
  }

  const { data: subscription } = useQuery({
    queryKey: queryKeys.subscription(),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!isAuthenticated,
  })

  // Mirror of the checkout's trial rule for the paywall card: first-time subscriber (RESOLVED
  // subscription with no status row) and not beta. Only signed-in users can hit the paywall
  // (generation requires auth), and while the query loads this stays false — under-promising is
  // the safe direction; a churned ex-Pro must never be promised "you won't be charged" (#619).
  // ENABLE_PRO_TRIAL keeps the copy dark until the backend's PRO_TRIAL_DAYS is live (lockstep).
  const trialEligible = Boolean(
    ENABLE_PRO_TRIAL && subscription && !subscription.status && !currentUser?.is_beta
  )

  const { data: savedSummaries } = useQuery<SavedSummary[]>({
    queryKey: queryKeys.savedSummaries(),
    queryFn: getSavedSummaries,
    retry: false,
    enabled: !!isAuthenticated,
  })

  const queryClient = useQueryClient()

  const saveMutation = useMutation({
    mutationFn: (summaryId: number) => saveSummary(summaryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.savedSummaries() })
      if (summary?.filing_id) {
        analytics.summarySaved(summary.filing_id, filing?.company?.ticker ?? null)
      }
    },
  })

  const isSaved = summary && savedSummaries?.some((s: SavedSummary) => s.summary_id === summary.id)
  const debugSummary = urlFlags.debug
  // Demo mode (curated first impression): the example/onboarding deep-links carry `?demo=1`.
  // It suppresses the quality badge + Regenerate button and silences the copilot attention nudge,
  // so a first-time visitor never meets a "Partial" badge on the curated example (plan item 1.3).
  const demoMode = urlFlags.demo

  useEffect(() => {
    if (!hasTrackedFilingView.current && filing) {
      analytics.filingViewed(
        filing.id,
        filing.company?.ticker ?? null,
        filing.filing_type,
        entryPoint
      )
      hasTrackedFilingView.current = true
    }
  }, [filing, entryPoint])

  useEffect(() => {
    if (!hasTrackedSummaryGenerated.current && hasSummaryContent && filing) {
      analytics.summaryGenerated(
        filing.company?.ticker ?? null,
        filing.filing_type,
        filing.id
      )
      hasTrackedSummaryGenerated.current = true
    }
  }, [hasSummaryContent, filing])

  // Activation funnel terminal step: the visitor actually sees summary content
  // (cached or freshly generated). duration_ms is time from page mount to content.
  useEffect(() => {
    if (!hasTrackedSummaryViewed.current && hasSummaryContent && filing && summary) {
      analytics.summaryViewed({
        filingId: filing.id,
        ticker: filing.company?.ticker ?? null,
        filingType: filing.filing_type,
        entryPoint,
        resultType: summary.raw_summary?.status,
        qualityVerdict: summary.raw_summary?.quality?.tier,
        durationMs: Date.now() - viewStartedAt.current,
      })
      hasTrackedSummaryViewed.current = true
    }
  }, [hasSummaryContent, filing, summary, entryPoint])

  if (filingLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-light dark:bg-background-dark">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    )
  }

  if (!filing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-light dark:bg-background-dark">
        <div className="text-center">
          <h1 className="text-2xl font-semibold mb-4 text-text-primary-light dark:text-text-primary-dark">Filing not found</h1>
          <Link href="/" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
            Go back home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <FilingViewerProvider
      filingId={filing.id}
      ticker={filing.company?.ticker ?? null}
      filingType={filing.filing_type}
    >
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      {/* Header */}
      <header className="bg-panel-light dark:bg-panel-dark border-b border-border-light dark:border-border-dark">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
            <button
              onClick={handleBack}
              className="text-brand-strong dark:text-brand-strong-dark hover:underline inline-flex items-center space-x-1 transition-colors group"
            >
              <span className="group-hover:-translate-x-1 transition-transform">←</span>
              <span>Back</span>
            </button>
          </div>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex-1">
              {filing.company ? (
                <>
                  <div className="flex flex-wrap items-center gap-3 mb-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark tracking-tight">
                        {filing.company.name}
                      </h1>
                      <Badge variant="solid" className="text-sm">
                        {filing.company.ticker}
                      </Badge>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                    <Badge variant={/10-Q|6-K/i.test(filing.filing_type) ? 'info' : 'neutral'}>
                      {filing.filing_type}
                    </Badge>
                    <span className="flex items-center space-x-1">
                      <span>Filed:</span>
                      <span className="font-medium">{formatLocalDate(filing.filing_date, 'MMMM dd, yyyy')}</span>
                    </span>
                    {filing.company.exchange && (
                      <span className="text-text-tertiary-light dark:text-text-secondary-dark">
                        {filing.company.exchange}
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark tracking-tight mb-2">
                    {filing.filing_type} Summary
                  </h1>
                  <p className="text-text-secondary-light dark:text-text-secondary-dark">
                    Filed: {formatLocalDate(filing.filing_date, 'MMMM dd, yyyy')}
                  </p>
                </>
              )}
            </div>

            {/* Tech badge */}
            <Badge variant="brand" className="hidden md:inline-flex">
              <SparkleIcon className="h-3.5 w-3.5" aria-hidden="true" />
              AI analysis
            </Badge>
          </div>
        </div>
      </header>

      {/* Main Content — summary + a unified Copilot/filing pane as reflowing research-desk panes on lg+ */}
      <FilingWorkspace
        open={copilotOpen}
        onOpenChange={setCopilotOpen}
        summaryAvailable={hasSummaryContent}
        demoMode={demoMode}
        secUrl={filing.sec_url ?? filing.document_url ?? null}
        copilotBody={
          <AskCopilotRail
            key={filing.id}
            filingId={filing.id}
            filingType={filing.filing_type}
            ticker={filing.company?.ticker ?? null}
            companyName={filing.company?.name ?? null}
            summaryAvailable={hasSummaryContent}
            isPro={subscription?.is_pro || false}
            isAuthenticated={isAuthenticated}
            open={copilotOpen}
            onOpenChange={setCopilotOpen}
            prefill={copilotPrefill}
            embedded
          />
        }
        filingBody={
          <FilingViewer
            key={filing.id}
            filingId={filing.id}
            filingLabel={`${filing.company?.ticker ?? filing.company?.name ?? 'Filing'} ${filing.filing_type}`}
            secUrl={filing.sec_url ?? filing.document_url ?? null}
            embedded
          />
        }
      >
        <main ref={summaryContentRef} className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {isStreaming || (hasStartedGeneration && !hasSummaryContent) ? (
            <StreamingSummaryDisplay
              streamingText={streamingText}
              stage={streamingStage}
              message={streamingMessage}
              filing={filing}
              error={generationError}
              onRetry={handleRegenerateSummary}
              elapsedSeconds={elapsedSeconds}
              trialEligible={trialEligible}
            />
          ) : summary && hasSummaryContent && filing ? (
            <SummaryDisplay
              summary={summary}
              filing={filing}
              isPro={subscription?.is_pro || false}
              saveMutation={saveMutation}
              isSaved={!!isSaved}
              debug={debugSummary}
              demoMode={demoMode}
              isAuthenticated={isAuthenticated}
              onRetry={handleRegenerateSummary}
              onAsk={handleAskCopilot}
            />
          ) : isAuthResolved && !isAuthenticated && filing && !summaryLoading ? (
            // No displayable summary (query settled) + signed out: generation requires an account,
            // so route to the gate — its sign-up/login links are the functional next step for any
            // guest here. Cached summaries render above for everyone (branch 2 wins first), so the
            // gate is only reached when there's genuinely nothing to show; !summaryLoading stops it
            // flashing while the query loads. Deliberately NOT gated on !activeErrorMessage: a
            // transient getSummary error must keep the working gate for a guest, not fall through
            // to the error card whose "Retry generation" dead-ends at "please sign in" for them
            // (it self-heals on reload if a cached summary did exist).
            <GenerateSignupGate filing={filing} entryPoint={entryPoint} />
          ) : !activeErrorMessage && (summaryLoading || !isAuthResolved) ? (
            // Still settling (summary query loading, or /me not yet resolved) and not actively
            // generating: show a neutral spinner, NOT the fake "Initializing AI analysis" progress
            // card. A signed-out visitor headed for the gate must never flash live AI-progress for
            // a generation that will never run (and it spun up a 200ms optimistic-progress timer).
            <div className="flex items-center justify-center py-24" role="status" aria-label="Loading">
              <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
            </div>
          ) : (
            <StreamingSummaryDisplay
              streamingText=""
              stage={activeErrorMessage ? 'error' : 'initializing'}
              message={activeErrorMessage || 'Initializing AI analysis...'}
              filing={filing}
              error={activeErrorMessage}
              onRetry={handleRegenerateSummary}
              elapsedSeconds={0}
              trialEligible={trialEligible}
            />
          )}
        </main>
      </FilingWorkspace>
    </div>
      <AskAboutSelection
        containerRef={summaryContentRef}
        enabled={(subscription?.is_pro ?? false) && hasSummaryContent}
        onAsk={handleAskAboutSelection}
      />
    </FilingViewerProvider>
  )
}

export default function FilingPageClient({ initialFiling, initialSummary }: FilingSeedProps = {}) {
  const params = useParams()
  const identifier = params.id as string
  const isTickerView = !/^\d+$/.test(identifier)

  if (isTickerView) {
    return <TickerFilingsView ticker={identifier.toUpperCase()} />
  }

  const filingId = parseInt(identifier, 10)
  return <FilingDetailView filingId={filingId} initialFiling={initialFiling} initialSummary={initialSummary} />
}
