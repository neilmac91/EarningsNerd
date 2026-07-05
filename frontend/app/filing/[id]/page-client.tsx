'use client'

import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getFiling, getCompanyFilings, Filing } from '@/features/filings/api/filings-api'
import { getSummary, generateSummaryStream, isPaywallStreamError, Summary, saveSummary, getSavedSummaries, getSummaryProgress, getWhatChanged, SummaryProgressData, SavedSummary } from '@/features/summaries/api/summaries-api'
import { WhatChanged } from '@/features/filings/components/WhatChanged'
import AskCopilotRail from '@/features/filings/components/copilot/AskCopilotRail'
import FilingViewer from '@/features/filings/components/copilot/FilingViewer'
import FilingWorkspace from '@/features/filings/components/copilot/FilingWorkspace'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'
import AskAboutSelection from '@/features/filings/components/copilot/AskAboutSelection'
import AskFilingCallout from '@/features/filings/components/copilot/AskFilingCallout'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import { getCompany, Company } from '@/features/companies/api/companies-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getApiUrl } from '@/lib/api/client'
import { BookmarkSimpleIcon, CheckCircleIcon, CircleNotchIcon, DownloadSimpleIcon, FileArrowDownIcon, FileTextIcon, SparkleIcon } from '@/lib/icons'
import { useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { format } from 'date-fns'
import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import FinancialMetricsTable from '@/components/FinancialMetricsTable'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import { isAxiosError } from 'axios'
import { stripInternalNotices } from '@/lib/stripInternalNotices'
import { ENABLE_QUALITY_BADGE } from '@/lib/featureFlags'
import analytics from '@/lib/analytics'
import { getEntryPoint } from '@/lib/entryPoint'
import { ENABLE_FINANCIAL_CHARTS } from '@/lib/featureFlags'
import { sanitizeFilename } from '@/lib/format'
import { Button } from '@/components/ui/Button'
import { Badge, Card, GuidanceCard, Skeleton, SkeletonText } from '@/components/ui'
import StreamingSummaryDisplay from './StreamingSummaryDisplay'
import { queryKeys } from '@/lib/queryKeys'

// StreamingSummaryDisplay + its stage constants live in ./StreamingSummaryDisplay.

// --- Helper Functions ---

const getFriendlyErrorMessage = (error: unknown): string | null => {
  if (!error) return null

  if (isAxiosError(error)) {
    const payload = error.response?.data as { detail?: string; message?: string } | string | undefined
    if (typeof payload === 'string') return payload
    if (payload?.detail) return payload.detail
    if (payload?.message) return payload.message
    if (error.code === 'ECONNABORTED' || error.message?.toLowerCase().includes('timeout')) {
      return 'Generation timed out, please retry.'
    }
    return error.message
  }

  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error

  return 'Unexpected error occurred while loading the summary.'
}

// --- Components ---
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

const SummarySections = dynamic(() => import('@/components/SummarySections'), {
  ssr: false,
  loading: () => <SummarySectionsSkeleton />,
})

function TickerFilingsView({ ticker }: { ticker: string }) {
  const normalizedTicker = ticker.toUpperCase()

  const { data: company, isLoading: companyLoading, error: companyError } = useQuery<Company>({
    queryKey: queryKeys.tickerCompany(normalizedTicker),
    queryFn: () => getCompany(normalizedTicker),
    retry: 1,
  })

  const { data: filings, isLoading: filingsLoading, error: filingsError } = useQuery<Filing[]>({
    queryKey: queryKeys.tickerFilings(normalizedTicker),
    queryFn: () => getCompanyFilings(normalizedTicker),
    enabled: !!company,
    retry: 1,
  })

  if (companyLoading) {
    return (
      <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
        <div className="flex h-full min-h-screen items-center justify-center">
          <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        </div>
      </div>
    )
  }

  if (!company || companyError) {
    return (
      <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
        <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
          <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">Filings unavailable</h1>
          <p className="mt-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            We couldn&apos;t load filings for <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{normalizedTicker}</span> right now. Please try again later.
          </p>
          {companyError instanceof Error && (
            <p className="mt-3 text-xs text-text-secondary-light dark:text-text-secondary-dark">{companyError.message}</p>
          )}
          <Link
            href="/"
            className="mt-6 inline-flex items-center rounded-full bg-brand px-5 py-2 text-sm font-semibold text-white transition hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark"
          >
            Back to home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">{company.name}</h1>
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {company.ticker} • Latest SEC filings
            </p>
          </div>
          <Link
            href={`/company/${company.ticker}`}
            className="inline-flex items-center rounded-full border border-border-light dark:border-white/20 bg-panel-light dark:bg-white/5 px-4 py-2 text-sm font-medium text-text-primary-light dark:text-text-primary-dark transition hover:border-brand-border hover:bg-brand-weak dark:hover:border-white/40 dark:hover:bg-white/10"
          >
            View company dashboard
          </Link>
        </div>

        <div className="rounded-3xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 p-6 shadow-e3 dark:shadow-[0_20px_50px_rgba(15,23,42,0.45)]">
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Recent Filings</h2>
          <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Select a filing below to open it and generate an AI summary instantly.
          </p>

          <div className="mt-6 space-y-3">
            {filingsLoading && (
              <div className="space-y-3" role="status" aria-label="Loading filings">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-20 rounded-2xl" />
                ))}
                <span className="sr-only">Loading filings…</span>
              </div>
            )}

            {filingsError instanceof Error && (
              <div className="rounded-xl border border-error-light/30 dark:border-error-dark/40 bg-error-light/10 dark:bg-error-dark/10 p-4 text-sm text-error-light dark:text-error-dark">
                Unable to load filings right now. {filingsError.message}
              </div>
            )}

            {!filingsLoading && !filingsError && filings && filings.length === 0 && (
              <div className="rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/10 p-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
                No filings available yet for {company.ticker}. Check back soon.
              </div>
            )}

            {filings && filings.length > 0 && (
              <div className="grid gap-3">
                {filings.map((filing) => (
                  <Link
                    key={filing.id}
                    href={`/filing/${filing.id}`}
                    className="group flex flex-col gap-3 rounded-xl border border-border-light dark:border-white/10 bg-panel-light hover:bg-white dark:bg-panel-dark dark:hover:bg-white/[0.06] shadow-e2 dark:shadow-none p-5 transition-colors duration-fast hover:border-brand-border dark:hover:border-brand-border-dark"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">{filing.filing_type}</p>
                        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                          {filing.filing_date ? format(new Date(filing.filing_date), 'MMM dd, yyyy') : 'Date TBD'}
                        </p>
                      </div>
                      <Badge variant="brand">Generate AI summary</Badge>
                    </div>
                    <div className="text-xs text-text-secondary-light dark:text-text-secondary-dark">Accession: {filing.accession_number}</div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function FilingDetailView({ filingId }: { filingId: number }) {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingStage, setStreamingStage] = useState<string>('')
  const [streamingMessage, setStreamingMessage] = useState<string>('')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [hasStartedGeneration, setHasStartedGeneration] = useState(false)
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

  const { data: currentUser } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isAuthenticated = Boolean(currentUser)

  const { data: filing, isLoading: filingLoading } = useQuery<Filing>({
    queryKey: queryKeys.filing(filingId),
    queryFn: () => getFiling(filingId),
  })

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

  const { data: summary, isLoading: summaryLoading, refetch, error: summaryError } = useQuery<Summary | null>({
    queryKey: queryKeys.summary(filingId),
    queryFn: () => getSummary(filingId),
    retry: false,
    enabled: !!filing,
  })

  const { data: subscription } = useQuery({
    queryKey: queryKeys.subscription(),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!isAuthenticated,
  })

  const { data: savedSummaries } = useQuery<SavedSummary[]>({
    queryKey: queryKeys.savedSummaries(),
    queryFn: getSavedSummaries,
    retry: false,
    enabled: !!isAuthenticated,
  })

  const queryClient = useQueryClient()

  const summaryHasPlaceholder = !!(summary?.business_overview && summary.business_overview.includes('Generating summary'))
  const hasSummaryContent = !!(summary?.business_overview && !summaryHasPlaceholder)
  const isGenerating = isStreaming || summaryHasPlaceholder

  // Progress data is used for polling side-effect, not displayed directly
  useQuery<SummaryProgressData>({
    queryKey: queryKeys.summaryProgress(filingId),
    queryFn: () => getSummaryProgress(filingId),
    enabled: !!filing && !!isGenerating,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.stage === 'completed' || data?.stage === 'error') {
        return false
      }
      return 1000
    },
  })


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
  const summaryErrorMessage = getFriendlyErrorMessage(summaryError)
  const activeErrorMessage = generationError || summaryErrorMessage
  const debugSummary = searchParams?.get('debug') === '1'
  // Demo mode (curated first impression): the example/onboarding deep-links carry `?demo=1`.
  // It suppresses the quality badge + Regenerate button and silences the copilot attention nudge,
  // so a first-time visitor never meets a "Partial" badge on the curated example (plan item 1.3).
  const demoMode = searchParams?.get('demo') === '1'

  const handleGenerateSummary = useCallback(async (options?: { force?: boolean }) => {
    // Feature flag for auth requirement (default to false implies POC mode/open access)
    const requireAuth = process.env.NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY === 'true'

    if (requireAuth && !isAuthenticated) {
      setGenerationError('Please sign in to generate summaries.')
      // Optional: Redirect to login or show modal
      // router.push('/login')
      return
    }
    setHasStartedGeneration(true)
    setGenerationError(null)
    setIsStreaming(true)
    setStreamingText('')
    setStreamingStage('initializing')
    setStreamingMessage(options?.force ? 'Regenerating analysis...' : 'Initializing AI analysis...')

    try {
      await generateSummaryStream(
        filingId,
        (chunk: string) => {
          // REPLACE (not append): the backend emits the summary as a single full-markdown 'chunk',
          // and A5 progressive 'preview' frames are growing full renders routed through here — each
          // supersedes the last, and the final 'chunk' supersedes the previews.
          setGenerationError(null)
          setStreamingText(chunk)
        },
        (stage: string, message: string, data?: { elapsed_seconds?: number; heartbeat_count?: number }) => {
          setGenerationError(null)
          setStreamingStage(stage)
          setStreamingMessage(message)
          if (data?.elapsed_seconds !== undefined) {
            setElapsedSeconds(data.elapsed_seconds)
          }
        },
        () => {
          setGenerationError(null)
          // Refetch the summary to get the full structured data
          refetch()
          queryClient.invalidateQueries({ queryKey: queryKeys.summary(filingId) })
          setIsStreaming(false)
        },
        (errorMessage: string) => {
          setGenerationError(errorMessage)
          setStreamingStage('error')
          setStreamingMessage(errorMessage)
          setIsStreaming(false)
          // Reset progress state on error
          setStreamingText('')
          // Activation funnel: record the client-confirmed moment the upgrade wall is shown.
          if (isPaywallStreamError(errorMessage) && filing) {
            analytics.paywallPromptShown({
              filingId: filing.id,
              ticker: filing.company?.ticker ?? null,
              filingType: filing.filing_type,
              entryPoint,
            })
          }
        },
        { force: options?.force, entryPoint }
      )
    } catch (error: unknown) {
      const errObj = error as { message?: string }
      const message = errObj?.message || 'Failed to generate summary'
      setGenerationError(message)
      setStreamingStage('error')
      setStreamingMessage(message)
      setIsStreaming(false)
      setStreamingText('')
    } finally {
      setIsStreaming(false)
    }
  }, [filingId, filing, refetch, queryClient, isAuthenticated, entryPoint])

  // Wrapper for regeneration with force=true
  const handleRegenerateSummary = useCallback(() => {
    handleGenerateSummary({ force: true })
  }, [handleGenerateSummary])

  // Auto-generate summary when page loads if no summary exists
  useEffect(() => {
    const requireAuth = process.env.NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY === 'true'
    const shouldAutoGenerate = !requireAuth || isAuthenticated

    // Auto-generate if all conditions are met
    // POC mode: removed isAuthenticated check to allow all users
    if (
      filing &&
      !summaryLoading &&
      !isStreaming &&
      !hasSummaryContent &&
      !hasStartedGeneration &&
      !generationError &&
      shouldAutoGenerate
    ) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: auto-kicks off async streaming summary generation once the filing loads and no summary exists
      handleGenerateSummary()
    }
  }, [filing, summaryLoading, isStreaming, hasSummaryContent, hasStartedGeneration, generationError, handleGenerateSummary, isAuthenticated])

  useEffect(() => {
    if (hasSummaryContent) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clears stale error state once async-streamed summary content arrives
      setGenerationError(null)
    }
  }, [hasSummaryContent])

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
                      <span className="font-medium">{format(new Date(filing.filing_date), 'MMMM dd, yyyy')}</span>
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
                    Filed: {format(new Date(filing.filing_date), 'MMMM dd, yyyy')}
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
          ) : (
            <StreamingSummaryDisplay
              streamingText=""
              stage={activeErrorMessage ? 'error' : 'initializing'}
              message={activeErrorMessage || 'Initializing AI analysis...'}
              filing={filing}
              error={activeErrorMessage}
              onRetry={handleRegenerateSummary}
              elapsedSeconds={0}
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

interface SaveMutation {
  mutate: (summaryId: number) => void
  isPending: boolean
}

function SummaryDisplay({
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
}: {
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
}) {
  const markdownContent = summary.business_overview || ''
  // S4 honest degradation, decoupled: ALWAYS strip internal failure notices (they're not
  // user-facing copy), and let the quality badge + retry CTA carry the "partial" story instead.
  // This gives honest labeling without leaking raw internal text into the summary body.
  const cleanedMarkdown = useMemo(
    () => stripInternalNotices(markdownContent),
    [markdownContent]
  )
  const rawSummary = summary.raw_summary && typeof summary.raw_summary === 'object' ? summary.raw_summary : null
  const quality = rawSummary?.quality as { tier?: string; reasons?: string[] } | undefined
  const isPartialQuality = ENABLE_QUALITY_BADGE && quality?.tier === 'partial'

  // A5 "What Changed": deterministic period-over-period diff (metric deltas, risk changes, key
  // changes). DB-only/cheap on the backend; only renders when there's something material to report.
  const { data: changeReport } = useQuery({
    queryKey: queryKeys.whatChanged(filing.id),
    queryFn: () => getWhatChanged(filing.id),
    staleTime: 10 * 60 * 1000,
  })

  const fallbackMessage = 'Summary temporarily unavailable — please retry.'
  const writerError = rawSummary?.writer_error
  const writerFallback = rawSummary?.writer?.fallback_used === true
  const trimmedMarkdown = cleanedMarkdown.trim()
  const isFallbackMessage = trimmedMarkdown === fallbackMessage
  const hasPolishedMarkdown = trimmedMarkdown.length > 0 && !isFallbackMessage && !writerError

  const isPartial = rawSummary?.status === 'partial'

  const isError = Boolean(writerError) || isFallbackMessage || (!hasPolishedMarkdown && trimmedMarkdown.length === 0)

  interface MetadataSections {
    financial_highlights?: {
      table?: Array<{
        metric: string
        current_period: string
        prior_period: string
        commentary?: string
      }>
      notes?: string
    }
    action_items?: string[]
    [key: string]: unknown
  }

  const metadata: MetadataSections | null = rawSummary ? (rawSummary.sections as MetadataSections ?? null) : null

  // "AAPL’s 10-K" when the issuer is known, else the cleaner "this 10-K".
  const subjectName = filing.company?.ticker || filing.company?.name
  const askSubjectLabel = subjectName ? `${subjectName}’s ${filing.filing_type}` : `this ${filing.filing_type}`

  const handleExportPDF = () => {
    const apiUrl = getApiUrl()
    const url = `${apiUrl}/api/summaries/filing/${filing.id}/export/pdf`

    fetch(url, {
      credentials: 'include',
    })
      .then(response => {
        if (!response.ok) {
          if (response.status === 403) {
            alert('PDF export is a Pro feature. Please upgrade to Pro.')
            return
          }
          throw new Error('Export failed')
        }
        return response.blob()
      })
      .then(blob => {
        if (!blob) {
          throw new Error('No blob received')
        }
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${sanitizeFilename(filing.filing_type, 'filing')}_${filing.filing_date ? format(new Date(filing.filing_date), 'yyyyMMdd') : 'summary'}.pdf`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      })
      .catch(error => {
        console.error('Export error:', error)
        alert('Failed to export PDF. Please try again.')
      })
  }

  const handleExportCSV = () => {
    const apiUrl = getApiUrl()
    const url = `${apiUrl}/api/summaries/filing/${filing.id}/export/csv`

    fetch(url, {
      credentials: 'include',
    })
      .then(response => {
        if (!response.ok) {
          if (response.status === 403) {
            alert('CSV export is a Pro feature. Please upgrade to Pro.')
            return
          }
          throw new Error('Export failed')
        }
        return response.blob()
      })
      .then(blob => {
        if (!blob) {
          throw new Error('No blob received')
        }
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${sanitizeFilename(filing.filing_type, 'filing')}_${filing.filing_date ? format(new Date(filing.filing_date), 'yyyyMMdd') : 'summary'}.csv`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      })
      .catch(error => {
        console.error('Export error:', error)
        alert('Failed to export CSV. Please try again.')
      })
  }

  return (
    <div className="space-y-6">
      {/* Action Buttons */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
        {isAuthenticated && (
          <div>
            {summary && summary.id && (
              isSaved ? (
                // Terminal confirmation — a static success chip (no success Badge variant exists;
                // DS §9 reserves success for a genuine done-state, which "Saved" is).
                <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold bg-success-light/10 text-success-light dark:bg-success-dark/10 dark:text-success-dark">
                  <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
                  Saved
                </span>
              ) : (
                <Button
                  variant="secondary"
                  onClick={() => saveMutation.mutate(summary.id)}
                  disabled={saveMutation.isPending}
                >
                  <BookmarkSimpleIcon className="h-4 w-4" />
                  Save Summary
                </Button>
              )
            )}
          </div>
        )}
        {/* Export buttons - only show for Pro users */}
        {isPro && (
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" onClick={handleExportPDF}>
              <DownloadSimpleIcon className="h-4 w-4" />
              Export PDF
            </Button>
            <Button variant="secondary" onClick={handleExportCSV}>
              <FileArrowDownIcon className="h-4 w-4" />
              Export CSV
            </Button>
          </div>
        )}
      </div>

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
          {hasPolishedMarkdown && (
            <Card as="section" className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-2">
                  <FileTextIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark" />
                  <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Summary</h2>
                  {/* S4 quality badge: honest signal of full vs partial output.
                      Suppressed in demo mode so a first-time visitor never meets "Partial" on the
                      curated example (plan item 1.3) — the badge still shows on user-chosen filings. */}
                  {!demoMode && ENABLE_QUALITY_BADGE && quality?.tier && (
                    <Badge
                      variant={quality.tier === 'full' ? 'brand' : 'warning'}
                      title={quality.reasons && quality.reasons.length ? quality.reasons.join('; ') : undefined}
                    >
                      {quality.tier === 'full'
                        ? 'Full summary'
                        : `Partial${quality.reasons && quality.reasons.length ? ` — ${quality.reasons[0]}` : ''}`}
                    </Badge>
                  )}
                </div>
                {/* Regenerate button - shown for partial results or fallback summaries. Pro-only:
                    force-regeneration deletes the shared summary + triggers a paid LLM run, so the
                    backend gates it to Pro (see summaries.generate_summary_stream). Hidden for
                    non-Pro to avoid a 403. Error-retry (no summary yet) uses a different affordance
                    and stays open to all. Suppressed in demo mode (curated example). */}
                {!demoMode && isPro && (isPartial || writerFallback || isPartialQuality) && onRetry && (
                  <Button variant="secondary" onClick={onRetry}>
                    Regenerate Analysis
                  </Button>
                )}
              </div>
              <div className="markdown-body text-text-secondary-light dark:text-text-secondary-dark">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {cleanedMarkdown}
                </ReactMarkdown>
              </div>
            </Card>
          )}

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
                    ? `${filing.company.ticker} — figures as reported in this ${filing.filing_type}`
                    : `Figures as reported in this ${filing.filing_type}`
                }
              />
            </ChartErrorBoundary>
          )}

          {/* Financial Metrics Table */}
          {metadata?.financial_highlights?.table && Array.isArray(metadata.financial_highlights.table) && (
            <FinancialMetricsTable
              metrics={metadata.financial_highlights.table}
              notes={metadata.financial_highlights.notes}
            />
          )}

          {/* Structured Summary with Tabs */}
          <SummarySections
            summary={summary}
            metrics={metadata?.financial_highlights?.table}
          />
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

      {/* End-of-summary discovery surface: turn the just-finished read into the next action. Hidden on
          a degraded/error summary; FREE users open the same rail and land on the upsell teaser. */}
      {!isError && (
        <AskFilingCallout filingType={filing.filing_type} subjectLabel={askSubjectLabel} onAsk={onAsk} />
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

function SummarySectionsSkeleton() {
  return (
    // SkeletonText carries its own role="status" — the wrapper must stay
    // role-less so live regions never nest.
    <div className="bg-panel-light dark:bg-panel-dark rounded-xl shadow-e2 dark:shadow-none border border-border-light dark:border-white/10 p-6 space-y-4">
      <Skeleton className="h-4 w-32" />
      <SkeletonText lines={3} />
    </div>
  )
}

export default function FilingPageClient() {
  const params = useParams()
  const identifier = params.id as string
  const isTickerView = !/^\d+$/.test(identifier)

  if (isTickerView) {
    return <TickerFilingsView ticker={identifier.toUpperCase()} />
  }

  const filingId = parseInt(identifier, 10)
  return <FilingDetailView filingId={filingId} />
}

