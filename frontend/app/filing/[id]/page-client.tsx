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
import { BookmarkSimpleIcon, CircleNotchIcon, DownloadSimpleIcon, FileArrowDownIcon, FileTextIcon, SparkleIcon, WarningCircleIcon } from '@/lib/icons'
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
import { GuidanceCard, Skeleton, SkeletonText } from '@/components/ui'

// --- Constants ---

const WHIMSY_MESSAGES = [
  "Turning caffeine into investments insights...",
  "Teaching the AI to read between the lines...",
  "Scanning 400 pages of footnotes so you don't have to...",
  "Cross-referencing historical data with crystal ball predictions...",
  "Translating 'Corporate Speak' into plain English...",
  "Wait for it... the good stuff is coming...",
  "Analyzing the fine print size 8 font...",
  "Reviewing the obscure 'Other' section...",
  "Decrypting the CEO's optimism...",
  "Looking for hidden gems in the appendix..."
]

// Ordered list of the real pipeline stages the backend streams over SSE
// (see backend/app/services/summary_pipeline.py). Step status is derived from the
// live stage below — not from a timer — so the log reflects what is actually happening.
const STAGE_ORDER = ['initializing', 'queued', 'fetching', 'parsing', 'analyzing', 'summarizing', 'completed'] as const

// Honest progress steps mapped to real backend stages. The filing-type label is
// derived from the actual filing (no more hard-coded "10-Q"), and there is no
// "vectorizing"/"semantic analysis" step because the summary path does no embedding.
const buildLoadingSteps = (filingType: string) => [
  { stage: 'fetching', label: `Retrieving ${filingType || 'SEC'} filing from EDGAR` },
  { stage: 'parsing', label: 'Extracting financial statements, risk factors & MD&A' },
  { stage: 'analyzing', label: 'Cross-referencing standardized XBRL financials' },
  { stage: 'summarizing', label: 'Generating investment analysis' },
]

const STAGE_PROGRESS_MAP: Record<string, number> = {
  'queued': 5,
  'fetching': 10,
  'parsing': 25,
  'analyzing': 45,
  'summarizing': 75,
  'completed': 100,
  'error': 0,
  'initializing': 0
}

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
    queryKey: ['ticker-company', normalizedTicker],
    queryFn: () => getCompany(normalizedTicker),
    retry: 1,
  })

  const { data: filings, isLoading: filingsLoading, error: filingsError } = useQuery<Filing[]>({
    queryKey: ['ticker-filings', normalizedTicker],
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
                    className="group flex flex-col gap-3 rounded-2xl border border-border-light dark:border-white/10 bg-panel-light hover:bg-brand-weak dark:bg-slate-900/50 dark:hover:bg-slate-900/80 p-5 transition hover:border-brand-border dark:hover:border-brand-dark/60"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">{filing.filing_type}</p>
                        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                          {filing.filing_date ? format(new Date(filing.filing_date), 'MMM dd, yyyy') : 'Date TBD'}
                        </p>
                      </div>
                      <span className="rounded-full bg-brand-strong/10 px-3 py-1 text-xs font-medium text-brand-strong dark:bg-brand-dark/15 dark:text-brand-strong-dark">
                        Generate AI summary
                      </span>
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
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isAuthenticated = Boolean(currentUser)

  const { data: filing, isLoading: filingLoading } = useQuery<Filing>({
    queryKey: ['filing', filingId],
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
    queryKey: ['summary', filingId],
    queryFn: () => getSummary(filingId),
    retry: false,
    enabled: !!filing,
  })

  const { data: subscription } = useQuery({
    queryKey: ['subscription'],
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!isAuthenticated,
  })

  const { data: savedSummaries } = useQuery<SavedSummary[]>({
    queryKey: ['saved-summaries'],
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
    queryKey: ['summary-progress', filingId],
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
      queryClient.invalidateQueries({ queryKey: ['saved-summaries'] })
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
          queryClient.invalidateQueries({ queryKey: ['summary', filingId] })
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
          <h1 className="text-2xl font-bold mb-4 text-text-primary-light dark:text-text-primary-dark">Filing not found</h1>
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
      <header className="bg-panel-light dark:bg-panel-dark shadow-lg border-b border-border-light dark:border-border-dark">
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
                      <h1 className="text-3xl font-bold text-text-primary-light dark:text-text-primary-dark tracking-tight">
                        {filing.company.name}
                      </h1>
                      <span className="px-3 py-1 bg-brand-strong text-white dark:bg-brand-dark dark:text-background-dark text-sm font-bold rounded-lg shadow-sm">
                        {filing.company.ticker}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                    <span className="px-3 py-1 bg-brand-weak dark:bg-white/5 rounded font-semibold text-text-secondary-light dark:text-text-secondary-dark">
                      {filing.filing_type}
                    </span>
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
                  <h1 className="text-3xl font-bold text-text-primary-light dark:text-text-primary-dark tracking-tight mb-2">
                    {filing.filing_type} Summary
                  </h1>
                  <p className="text-text-secondary-light dark:text-text-secondary-dark">
                    Filed: {format(new Date(filing.filing_date), 'MMMM dd, yyyy')}
                  </p>
                </>
              )}
            </div>

            {/* Tech badge */}
            <div className="hidden md:flex items-center space-x-2 px-4 py-2 bg-brand-weak dark:bg-white/5 rounded-lg border border-brand-border">
              <div className="w-2 h-2 bg-brand-strong dark:bg-brand-strong-dark rounded-full animate-pulse"></div>
              <span className="text-xs font-semibold text-brand-strong dark:text-brand-strong-dark">AI Analysis</span>
            </div>
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

function StreamingSummaryDisplay({
  streamingText,
  stage,
  message,
  filing,
  error,
  onRetry,
  elapsedSeconds = 0,
}: {
  streamingText: string
  stage: string
  message: string
  filing: Filing
  error?: string | null
  onRetry?: () => void
  elapsedSeconds?: number
}) {
  const [isClient, setIsClient] = useState(false)
  const [whimsyMessage, setWhimsyMessage] = useState('')
  const [showWhimsy, setShowWhimsy] = useState(false)
  const [optimisticProgress, setOptimisticProgress] = useState(0)

  const isError = stage === 'error' || !!error

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time client detection to gate SSR-unsafe rendering (avoids hydration mismatch)
    setIsClient(true)
  }, [])

  // Whimsy rotation effect
  useEffect(() => {
    if (stage === 'completed' || isError) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs whimsy-message visibility to the async streaming generation stage
      setShowWhimsy(false)
      return
    }

    setShowWhimsy(true)
    // Initial random message
    setWhimsyMessage(WHIMSY_MESSAGES[Math.floor(Math.random() * WHIMSY_MESSAGES.length)])

    const intervalId = setInterval(() => {
      setWhimsyMessage(WHIMSY_MESSAGES[Math.floor(Math.random() * WHIMSY_MESSAGES.length)])
    }, 4000)

    return () => clearInterval(intervalId)
  }, [stage, isError])

  // Stalled state detection
  const [isStalled, setIsStalled] = useState(false)

  useEffect(() => {
    // Normal generation runs ~30-60s; only flag a genuine stall well past that window
    // so we never signal "failure" during a healthy run (was 15s — inside the normal window).
    if (elapsedSeconds > 45 && stage !== 'completed' && stage !== 'summarizing' && !isError) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- derives a stall flag from async streaming elapsed time + generation stage
      setIsStalled(true)
    } else {
      setIsStalled(false)
    }
  }, [elapsedSeconds, stage, isError])

  // Optimistic progress effect - uses real elapsed time from backend but asymptotic approach
  useEffect(() => {
    if (stage === 'completed') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- syncs optimistic progress bar to the async streaming generation stage
      setOptimisticProgress(100)
      return
    }
    if (isError) return

    // Get base progress for current stage
    const baseProgress = STAGE_PROGRESS_MAP[stage] || 0

    // Calculate next stage target using map for cleaner code
    const NEXT_TARGET_MAP: Record<string, number> = {
      'initializing': 10,
      'queued': 10,
      'fetching': 25,
      'parsing': 45,
      'analyzing': 75,
      'summarizing': 98, // Allow getting very close to 100%
    }
    const nextTarget = NEXT_TARGET_MAP[stage] || 95

    // Use elapsed time from backend for smoother progress within stage
    // Each stage gets a time bonus based on how long it's been running
    const stageRange = nextTarget - baseProgress
    const timeBonus = Math.min(stageRange * 0.6, elapsedSeconds * 1.5) // Faster initial ramp

    // Set target to approach
    const targetProgress = Math.min(nextTarget, baseProgress + timeBonus)

    setOptimisticProgress(prev => Math.max(prev, targetProgress))

    // Fallback: Asymptotic approach to nextTarget if backend assumes silence
    // Instead of hard stop at nextTarget - 1, we asymptotically approach nextTarget
    const interval = setInterval(() => {
      setOptimisticProgress(current => {
        // Asymptotic formula: move 5% of the remaining distance every tick
        const dist = nextTarget - current
        if (dist < 0.1) return current // Stop if very close
        return current + (dist * 0.05)
      })
    }, 200)

    return () => clearInterval(interval)
  }, [stage, isError, elapsedSeconds])

  // Clean up progress when complete
  useEffect(() => {
    if (stage === 'completed') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- finalizes progress to 100% when the async streaming generation completes
      setOptimisticProgress(100)
    }
  }, [stage])

  if (!isClient) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-panel-light dark:bg-panel-dark rounded-xl shadow-e2 dark:shadow-none border border-border-light dark:border-white/10 p-8">
          {/* SkeletonText carries its own role="status" — the wrapper must stay
              role-less so live regions never nest. */}
          <div className="space-y-6">
            <Skeleton className="h-6 w-1/3" />
            <SkeletonText lines={3} />
            <Skeleton className="h-32 rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  const displayText = streamingText || ''
  const isGenerating = !isError && (stage === 'summarizing' || displayText.length > 0 || optimisticProgress < 100)

  // Use whimsy message if available and generation is active but not showing text yet
  // or if we are in a long running state.
  // Actually, let's show whimsy message as a sub-text or rotating label
  const activeMessage = error || message || stage

  // Honest, backend-driven progress log: steps reflect the real streamed stage.
  const loadingSteps = buildLoadingSteps(filing.filing_type)
  const currentStageIdx = STAGE_ORDER.indexOf(stage as (typeof STAGE_ORDER)[number])
  // On the error path `stage` becomes 'error' (not in STAGE_ORDER → index -1). Fall back to the
  // furthest stage the persisted progress implies so the step log keeps its completed steps instead
  // of collapsing to all-pending — staying consistent with the circular indicator, which also
  // retains its last value on error.
  const displayStageIdx = currentStageIdx > -1
    ? currentStageIdx
    : STAGE_ORDER.reduce((acc, s, i) => ((STAGE_PROGRESS_MAP[s] ?? 0) <= optimisticProgress ? i : acc), -1)

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Progress Header */}
      <div className="bg-panel-light dark:bg-panel-dark rounded-xl shadow-lg border border-border-light dark:border-border-dark p-8 relative overflow-hidden">
        {/* Shimmer overlay for active generation */}
        {isGenerating && (
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full animate-shimmer motion-reduce:animate-none" />
        )}

        <div className="flex flex-col md:flex-row gap-8 relative z-10">
          {/* Left: Heartbeat Indicator */}
          <div className="flex flex-col items-center justify-center space-y-4 md:w-1/3 border-b md:border-b-0 md:border-r border-border-light dark:border-border-dark pb-6 md:pb-0 md:pr-6">
            <div className="relative w-32 h-32 flex-shrink-0">
              {/* Outer Ring */}
              <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 128 128">
                <circle
                  cx="64"
                  cy="64"
                  r="60"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="6"
                  className="text-border-light dark:text-border-dark"
                />
                <circle
                  cx="64"
                  cy="64"
                  r="60"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="6"
                  strokeDasharray={`${2 * Math.PI * 60}`}
                  strokeDashoffset={`${2 * Math.PI * 60 * (1 - optimisticProgress / 100)}`}
                  strokeLinecap="round"
                  className={`transition duration-slow ease-out ${isError ? 'text-error-light dark:text-error-dark' : 'text-brand-strong dark:text-brand-strong-dark'}`}
                />
              </svg>

              {/* Center Heartbeat Orb */}
              <div className="absolute inset-0 flex items-center justify-center">
                <div className={`relative w-16 h-16 rounded-full flex items-center justify-center transition-colors duration-slow ${isError
                  ? 'bg-error-light/10 dark:bg-error-dark/10'
                  : 'bg-brand-weak dark:bg-white/5'
                  }`}>
                  <div className={`w-8 h-8 rounded-full ${isError
                    ? 'bg-error-light dark:bg-error-dark'
                    : 'bg-brand-strong dark:bg-brand-strong-dark'
                    } ${isGenerating && !isError ? 'animate-pulse' : ''} shadow-lg shadow-brand-strong/20`} />

                  {/* Ripple effect */}
                  {isGenerating && !isError && (
                    <div className="absolute inset-0 rounded-full border border-brand-border animate-ping" />
                  )}
                </div>
              </div>
            </div>

            <div className="text-center">
              <h3 className={`text-lg font-semibold ${isError ? 'text-error-light dark:text-error-dark' : 'text-text-primary-light dark:text-text-primary-dark'}`}>
                {Math.round(optimisticProgress)}% Complete
              </h3>
              <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                {filing.filing_type} • {isError ? 'Failed' : isGenerating ? 'Processing...' : 'Ready'}
              </p>
              {isGenerating && !isError && (
                <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                  This usually takes 30–60 seconds
                </p>
              )}
            </div>
          </div>

          {/* Right: Live Log & Whimsy */}
          <div className="flex-1 flex flex-col justify-center min-w-0">
            {/* Whimsy Message Area */}
            <div className="mb-6 bg-background-light dark:bg-background-dark rounded-lg p-4 border border-border-light dark:border-border-dark">
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  <span className="text-xl">✨</span>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark animate-fadeIn">
                    {isError
                      ? "We hit a snag, but don't worry."
                      : isStalled
                        ? "Taking longer than usual, but we're still working on it..."
                        : (showWhimsy ? whimsyMessage : "Initializing...")
                    }
                  </p>
                  <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                    {isStalled ? "Complex filing detected" : "AI Analyst System"}
                  </p>
                </div>
              </div>
            </div>

            {/* Vertical Live Log */}
            <div className="flex flex-col space-y-4 relative">
              <div className="absolute left-3 top-2 bottom-2 w-0.5 bg-border-light dark:bg-border-dark lg:block hidden" />

              {/* Dynamically generate log steps based on progress */}
              {loadingSteps.map((step) => {
                const stepIdx = STAGE_ORDER.indexOf(step.stage as (typeof STAGE_ORDER)[number])
                const status = (stage === 'completed' || (displayStageIdx > -1 && displayStageIdx > stepIdx))
                  ? 'complete'
                  : (displayStageIdx === stepIdx ? 'active' : 'pending')

                return (
                  <div key={step.stage} className={`flex items-center gap-3 transition-opacity duration-base ${status === 'pending' ? 'opacity-40' : 'opacity-100'}`}>
                    <div className={`relative z-10 w-6 h-6 rounded-full flex items-center justify-center border transition duration-base ${status === 'complete'
                      ? 'bg-brand-strong border-brand-strong text-white dark:bg-brand-dark dark:border-brand-dark dark:text-background-dark'
                      : status === 'active'
                        ? 'bg-panel-light dark:bg-panel-dark border-brand-border text-brand-strong dark:text-brand-strong-dark'
                        : 'bg-background-light dark:bg-background-dark border-border-light dark:border-border-dark'
                      }`}>
                      {status === 'complete' && (
                        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                      {status === 'active' && (
                        <div className="w-2 h-2 rounded-full bg-brand-strong dark:bg-brand-strong-dark animate-pulse" />
                      )}
                    </div>
                    <span className={`text-sm ${status === 'active' ? 'font-medium text-text-primary-light dark:text-text-primary-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}>
                      {step.label}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Streaming Content */}
      {isError && (
        <GuidanceCard
          variant="error"
          title="Generation interrupted"
          description={error || message || 'Generation timed out. Please retry to continue.'}
          action={
            onRetry ? (
              // Secondary, per the GuidanceCard convention (error retry is never the page's primary action)
              <Button variant="secondary" onClick={onRetry}>
                Retry generation
              </Button>
            ) : undefined
          }
        />
      )}

      {displayText && (
        <div className="bg-panel-light dark:bg-panel-dark rounded-xl shadow-lg border border-border-light dark:border-border-dark p-8">
          <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-border-light dark:border-border-dark">
            <div className="w-2 h-2 bg-brand-strong dark:bg-brand-strong-dark rounded-full"></div>
            <h2 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">AI-Generated Summary</h2>
            {isGenerating && (
              <span className="px-2.5 py-1 text-xs font-semibold text-brand-strong dark:text-brand-strong-dark bg-brand-weak dark:bg-white/5 rounded-full">
                Live
              </span>
            )}
          </div>
          <div className="prose prose-lg dark:prose-invert max-w-none">
            <div className="text-text-secondary-light dark:text-text-secondary-dark whitespace-pre-wrap leading-relaxed font-sans">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mt-6 mb-4" {...props} />,
                  h2: ({ node, ...props }) => <h2 className="text-xl font-bold mt-5 mb-3" {...props} />,
                  h3: ({ node, ...props }) => <h3 className="text-lg font-bold mt-4 mb-2" {...props} />,
                  p: ({ node, ...props }) => <p className="mb-4" {...props} />,
                  ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-4" {...props} />,
                  ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-4" {...props} />,
                  li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                }}
              >
                {displayText}
              </ReactMarkdown>
              {isGenerating && (
                <span className="inline-block w-0.5 h-5 bg-brand-strong dark:bg-brand-strong-dark ml-1 align-middle animate-pulse"></span>
              )}
            </div>
          </div>
        </div>
      )}

      {!displayText && !isError && (
        <div className="bg-panel-light dark:bg-panel-dark rounded-xl p-8 border border-border-light dark:border-border-dark shadow-lg">
          <div className="flex items-start space-x-4">
            <div className="flex-shrink-0">
              <CircleNotchIcon className="h-8 w-8 text-brand-strong dark:text-brand-strong-dark animate-spin" />
            </div>
            <div className="flex-1">
              <p className="text-text-primary-light dark:text-text-primary-dark font-semibold text-lg mb-1">
                {activeMessage}
              </p>
              <p className="text-text-secondary-light dark:text-text-secondary-dark text-sm">
                Analyzing risk factors, financials &amp; management discussion for investment insights...
              </p>
            </div>
          </div>

          {/* Streaming placeholder — mono rhythm (the summary streams into the data face) */}
          <SkeletonText lines={5} mono className="mt-6" />
        </div>
      )}
    </div>
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
    queryKey: ['what-changed', filing.id],
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
                <button
                  onClick={() => saveMutation.mutate(summary.id)}
                  disabled={saveMutation.isPending || isSaved}
                  className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors bg-success-light/10 text-success-light dark:bg-success-dark/10 dark:text-success-dark cursor-not-allowed"
                >
                  <BookmarkSimpleIcon className="h-4 w-4 mr-2" />
                  Saved
                </button>
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
        <div className="bg-warning-light/10 dark:bg-warning-dark/10 border border-warning-light/30 rounded-lg p-6">
          <WarningCircleIcon className="h-6 w-6 text-warning-light dark:text-warning-dark mb-2" />
          <p className="text-warning-light dark:text-warning-dark">{fallbackMessage}</p>
        </div>
      ) : (
        <>
          {hasPolishedMarkdown && (
            <section className="bg-panel-light dark:bg-panel-dark rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-2">
                  <FileTextIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark" />
                  <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Summary</h2>
                  {/* S4 quality badge: honest signal of full vs partial output.
                      Suppressed in demo mode so a first-time visitor never meets "Partial" on the
                      curated example (plan item 1.3) — the badge still shows on user-chosen filings. */}
                  {!demoMode && ENABLE_QUALITY_BADGE && quality?.tier && (
                    <span
                      title={quality.reasons && quality.reasons.length ? quality.reasons.join('; ') : undefined}
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
                        quality.tier === 'full'
                          ? 'bg-brand-weak dark:bg-white/5 text-brand-strong dark:text-brand-strong-dark ring-brand-border'
                          : 'bg-warning-light/10 dark:bg-warning-dark/10 text-warning-light dark:text-warning-dark ring-warning-light/30'
                      }`}
                    >
                      {quality.tier === 'full'
                        ? 'Full summary'
                        : `Partial${quality.reasons && quality.reasons.length ? ` — ${quality.reasons[0]}` : ''}`}
                    </span>
                  )}
                </div>
                {/* Retry button - shown for partial results or fallback summaries.
                    Suppressed in demo mode (no "regenerate" affordance on the curated example). */}
                {!demoMode && (isPartial || writerFallback || isPartialQuality) && onRetry && (
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
            </section>
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
        <section className="bg-panel-light dark:bg-panel-dark rounded-lg shadow border border-brand-border p-6">
          <h3 className="text-lg font-semibold text-brand-strong dark:text-brand-strong-dark mb-1">Suggested Follow-Ups</h3>
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
        </section>
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

