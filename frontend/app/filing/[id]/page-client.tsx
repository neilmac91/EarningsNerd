'use client'

import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getFiling, getCompanyFilings, Filing } from '@/features/filings/api/filings-api'
import { getSummary, generateSummaryStream, Summary, saveSummary, getSavedSummaries, getSummaryProgress, SummaryProgressData, SavedSummary } from '@/features/summaries/api/summaries-api'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import { getCompany, Company } from '@/features/companies/api/companies-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getApiUrl } from '@/lib/api/client'
import { Loader2, AlertCircle, FileText, Download, FileDown, Bookmark, BookmarkCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { format } from 'date-fns'
import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import SubscriptionGate from '@/components/SubscriptionGate'
import FinancialMetricsTable from '@/components/FinancialMetricsTable'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import { isAxiosError } from 'axios'
import { stripInternalNotices } from '@/lib/stripInternalNotices'
import { ThemeToggle } from '@/components/ThemeToggle'
import analytics from '@/lib/analytics'

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

const LOADING_STEPS = [
  { id: '1', label: 'Retrieving 10-Q filing from EDGAR', threshold: 10, nextTarget: 25 },
  { id: '2', label: 'Extracting Item 1A (Risk Factors) & MD&A', threshold: 25, nextTarget: 45 },
  { id: '3', label: 'Vectorizing content for semantic analysis', threshold: 45, nextTarget: 75 },
  { id: '4', label: 'Synthesizing investment insights', threshold: 75, nextTarget: 95 }
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
const FinancialCharts = dynamic(() => import('@/components/FinancialCharts'), {
  ssr: false,
  loading: () => <ChartsSkeleton />,
})

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
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="flex h-full min-h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-sky-400" />
        </div>
      </div>
    )
  }

  if (!company || companyError) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
          <h1 className="text-3xl font-semibold text-white">Filings unavailable</h1>
          <p className="mt-4 text-sm text-slate-300">
            We couldn&apos;t load filings for <span className="font-semibold text-white">{normalizedTicker}</span> right now. Please try again later.
          </p>
          {companyError instanceof Error && (
            <p className="mt-3 text-xs text-slate-400/80">{companyError.message}</p>
          )}
          <Link
            href="/"
            className="mt-6 inline-flex items-center rounded-full bg-white px-5 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-100"
          >
            Back to home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-white">{company.name}</h1>
            <p className="text-sm text-slate-300">
              {company.ticker} • Latest SEC filings
            </p>
          </div>
          <Link
            href={`/company/${company.ticker}`}
            className="inline-flex items-center rounded-full border border-white/20 bg-white/5 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-white/40 hover:bg-white/10"
          >
            View company dashboard
          </Link>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-[0_20px_50px_rgba(15,23,42,0.45)]">
          <h2 className="text-lg font-semibold text-white">Recent Filings</h2>
          <p className="mt-1 text-sm text-slate-300">
            Select a filing below to open it and generate an AI summary instantly.
          </p>

          <div className="mt-6 space-y-3">
            {filingsLoading && (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="h-20 animate-pulse rounded-2xl border border-white/10 bg-white/10" />
                ))}
              </div>
            )}

            {filingsError instanceof Error && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
                Unable to load filings right now. {filingsError.message}
              </div>
            )}

            {!filingsLoading && !filingsError && filings && filings.length === 0 && (
              <div className="rounded-xl border border-white/10 bg-white/10 p-6 text-center text-sm text-slate-300">
                No filings available yet for {company.ticker}. Check back soon.
              </div>
            )}

            {filings && filings.length > 0 && (
              <div className="grid gap-3">
                {filings.map((filing) => (
                  <Link
                    key={filing.id}
                    href={`/filing/${filing.id}`}
                    className="group flex flex-col gap-3 rounded-2xl border border-white/10 bg-slate-900/50 p-5 transition hover:border-sky-400/60 hover:bg-slate-900/80"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-base font-semibold text-white">{filing.filing_type}</p>
                        <p className="text-sm text-slate-300">
                          {filing.filing_date ? format(new Date(filing.filing_date), 'MMM dd, yyyy') : 'Date TBD'}
                        </p>
                      </div>
                      <span className="rounded-full bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-300">
                        Generate AI summary
                      </span>
                    </div>
                    <div className="text-xs text-slate-400">Accession: {filing.accession_number}</div>
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
  const hasTrackedFilingView = useRef(false)
  const hasTrackedSummaryGenerated = useRef(false)

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

  const handleGenerateSummary = useCallback(async () => {
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
    setStreamingMessage('Initializing AI analysis...')

    try {
      await generateSummaryStream(
        filingId,
        (chunk: string) => {
          setGenerationError(null)
          setStreamingText(prev => prev + chunk)
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
        }
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
  }, [filingId, refetch, queryClient])

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
      handleGenerateSummary()
    }
  }, [filing, summaryLoading, isStreaming, hasSummaryContent, hasStartedGeneration, generationError, handleGenerateSummary, isAuthenticated])

  useEffect(() => {
    if (hasSummaryContent) {
      setGenerationError(null)
    }
  }, [hasSummaryContent])

  useEffect(() => {
    if (!hasTrackedFilingView.current && filing) {
      analytics.filingViewed(
        filing.id,
        filing.company?.ticker ?? null,
        filing.filing_type
      )
      hasTrackedFilingView.current = true
    }
  }, [filing])

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

  if (filingLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600 dark:text-primary-400" />
      </div>
    )
  }

  if (!filing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Filing not found</h1>
          <Link href="/" className="text-primary-600 hover:underline dark:text-primary-400 dark:hover:text-primary-300">
            Go back home
          </Link>
        </div>
      </div>
    )
  }


  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-gradient-to-r from-white via-gray-50 to-white dark:from-gray-800 dark:via-gray-900 dark:to-gray-800 shadow-lg border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
            <button
              onClick={handleBack}
              className="text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 inline-flex items-center space-x-1 transition-colors group"
            >
              <span className="group-hover:-translate-x-1 transition-transform">←</span>
              <span>Back</span>
            </button>
            <ThemeToggle />
          </div>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex-1">
              {filing.company ? (
                <>
                  <div className="flex flex-wrap items-center gap-3 mb-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">
                        {filing.company.name}
                      </h1>
                      <span className="px-3 py-1 bg-gradient-to-r from-primary-600 to-blue-600 text-white text-sm font-bold rounded-lg shadow-sm">
                        {filing.company.ticker}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
                    <span className="px-3 py-1 bg-gray-100 dark:bg-gray-700 rounded-md font-semibold text-gray-700 dark:text-gray-300">
                      {filing.filing_type}
                    </span>
                    <span className="flex items-center space-x-1">
                      <span>Filed:</span>
                      <span className="font-medium">{format(new Date(filing.filing_date), 'MMMM dd, yyyy')}</span>
                    </span>
                    {filing.company.exchange && (
                      <span className="text-gray-500 dark:text-gray-400">
                        {filing.company.exchange}
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <h1 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight mb-2">
                    {filing.filing_type} Summary
                  </h1>
                  <p className="text-gray-600 dark:text-gray-400">
                    Filed: {format(new Date(filing.filing_date), 'MMMM dd, yyyy')}
                  </p>
                </>
              )}
            </div>

            {/* Tech badge */}
            <div className="hidden md:flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-primary-50 to-blue-50 dark:from-primary-900/20 dark:to-blue-900/20 rounded-lg border border-primary-200 dark:border-primary-800">
              <div className="w-2 h-2 bg-primary-600 dark:bg-primary-400 rounded-full animate-pulse"></div>
              <span className="text-xs font-semibold text-primary-700 dark:text-primary-300">AI Analysis</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isStreaming || (hasStartedGeneration && !hasSummaryContent) ? (
          <StreamingSummaryDisplay
            streamingText={streamingText}
            stage={streamingStage}
            message={streamingMessage}
            filing={filing}
            error={generationError}
            onRetry={handleGenerateSummary}
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
            isAuthenticated={isAuthenticated}
            onRetry={handleGenerateSummary}
          />
        ) : (
          <StreamingSummaryDisplay
            streamingText=""
            stage={activeErrorMessage ? 'error' : 'initializing'}
            message={activeErrorMessage || 'Initializing AI analysis...'}
            filing={filing}
            error={activeErrorMessage}
            onRetry={handleGenerateSummary}
            elapsedSeconds={0}
          />
        )}
      </main>
    </div>
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
    setIsClient(true)
  }, [])

  // Whimsy rotation effect
  useEffect(() => {
    if (stage === 'completed' || isError) {
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
    if (elapsedSeconds > 15 && stage !== 'completed' && stage !== 'summarizing' && !isError) {
      setIsStalled(true)
    } else {
      setIsStalled(false)
    }
  }, [elapsedSeconds, stage, isError])

  // Optimistic progress effect - uses real elapsed time from backend but asymptotic approach
  useEffect(() => {
    if (stage === 'completed') {
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
      setOptimisticProgress(100)
    }
  }, [stage])

  if (!isClient) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="bg-white rounded-xl shadow-xl border border-gray-200/50 p-8">
          <div className="animate-pulse space-y-6">
            <div className="h-6 bg-primary-100/70 rounded w-1/3"></div>
            <div className="h-4 bg-primary-100/50 rounded w-full"></div>
            <div className="h-4 bg-primary-100/40 rounded w-5/6"></div>
            <div className="h-4 bg-primary-100/40 rounded w-2/3"></div>
            <div className="h-32 bg-primary-50 rounded-lg"></div>
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

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Progress Header */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-8 relative overflow-hidden">
        {/* Shimmer overlay for active generation */}
        {isGenerating && (
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full animate-[shimmer_2s_infinite]" />
        )}

        <div className="flex flex-col md:flex-row gap-8 relative z-10">
          {/* Left: Heartbeat Indicator */}
          <div className="flex flex-col items-center justify-center space-y-4 md:w-1/3 border-b md:border-b-0 md:border-r border-gray-100 dark:border-gray-700 pb-6 md:pb-0 md:pr-6">
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
                  className="text-gray-100 dark:text-gray-800"
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
                  className={`transition-all duration-700 ease-out ${isError ? 'text-rose-500' : 'text-primary-600 dark:text-primary-400'}`}
                />
              </svg>

              {/* Center Heartbeat Orb */}
              <div className="absolute inset-0 flex items-center justify-center">
                <div className={`relative w-16 h-16 rounded-full flex items-center justify-center transition-colors duration-500 ${isError
                  ? 'bg-rose-100 dark:bg-rose-900/30'
                  : 'bg-primary-50 dark:bg-primary-900/20'
                  }`}>
                  <div className={`w-8 h-8 rounded-full ${isError
                    ? 'bg-rose-500'
                    : 'bg-primary-600 dark:bg-primary-400'
                    } ${isGenerating && !isError ? 'animate-pulse' : ''} shadow-lg shadow-primary-500/20`} />

                  {/* Ripple effect */}
                  {isGenerating && !isError && (
                    <div className="absolute inset-0 rounded-full border border-primary-500/30 animate-ping" />
                  )}
                </div>
              </div>
            </div>

            <div className="text-center">
              <h3 className={`text-lg font-semibold ${isError ? 'text-rose-600' : 'text-gray-900 dark:text-white'}`}>
                {Math.round(optimisticProgress)}% Complete
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {filing.filing_type} • {isError ? 'Failed' : isGenerating ? 'Processing...' : 'Ready'}
              </p>
            </div>
          </div>

          {/* Right: Live Log & Whimsy */}
          <div className="flex-1 flex flex-col justify-center min-w-0">
            {/* Whimsy Message Area */}
            <div className="mb-6 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800/50 dark:to-gray-800 rounded-lg p-4 border border-gray-100 dark:border-gray-700/50">
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  <span className="text-xl">✨</span>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200 animate-[fadeIn_0.5s_ease-out]">
                    {isError
                      ? "We hit a snag, but don't worry."
                      : isStalled
                        ? "Taking longer than usual, but we're still working on it..."
                        : (showWhimsy ? whimsyMessage : "Initializing...")
                    }
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {isStalled ? "Complex filing detected" : "AI Analyst System"}
                  </p>
                </div>
              </div>
            </div>

            {/* Vertical Live Log */}
            <div className="flex flex-col space-y-4 relative">
              <div className="absolute left-3 top-2 bottom-2 w-0.5 bg-gray-100 dark:bg-gray-700 lg:block hidden" />

              {/* Dynamically generate log steps based on progress */}
              {LOADING_STEPS.map((step) => {
                const status = optimisticProgress > step.threshold
                  ? 'complete'
                  : optimisticProgress > (step.threshold - 10) ? 'active' : 'pending'

                return (
                  <div key={step.id} className={`flex items-center gap-3 transition-opacity duration-300 ${status === 'pending' ? 'opacity-40' : 'opacity-100'}`}>
                    <div className={`relative z-10 w-6 h-6 rounded-full flex items-center justify-center border transition-all duration-300 ${status === 'complete'
                      ? 'bg-emerald-500 border-emerald-500 text-white'
                      : status === 'active'
                        ? 'bg-white dark:bg-gray-800 border-primary-500 text-primary-600'
                        : 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700'
                      }`}>
                      {status === 'complete' && (
                        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                      {status === 'active' && (
                        <div className="w-2 h-2 rounded-full bg-primary-600 dark:bg-primary-400 animate-pulse" />
                      )}
                    </div>
                    <span className={`text-sm ${status === 'active' ? 'font-medium text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-400'}`}>
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
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6 shadow-sm">
          <div className="flex items-start space-x-3">
            <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400 mt-1 flex-shrink-0" />
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-red-700 dark:text-red-400 mb-2">
                Generation interrupted
              </h2>
              <p className="text-sm text-red-600 dark:text-red-300 mb-4">
                {error || message || 'Generation timed out. Please retry to continue.'}
              </p>
              <div className="flex items-center gap-3 flex-wrap">
                {onRetry && (
                  <button
                    onClick={onRetry}
                    className="inline-flex items-center px-4 py-2 bg-primary-600 dark:bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-700 dark:hover:bg-primary-600 transition-colors"
                  >
                    Retry generation
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {displayText && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-8">
          <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
            <div className="w-2 h-2 bg-primary-600 dark:bg-primary-400 rounded-full"></div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">AI-Generated Summary</h2>
            {isGenerating && (
              <span className="px-2.5 py-1 text-xs font-semibold text-primary-700 dark:text-primary-300 bg-primary-100 dark:bg-primary-900/50 rounded-full">
                Live
              </span>
            )}
          </div>
          <div className="prose prose-lg dark:prose-invert max-w-none">
            <div className="text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed font-sans">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // eslint-disable-next-line @typescript-eslint/no-unused-vars
                  h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mt-6 mb-4" {...props} />,
                  // eslint-disable-next-line @typescript-eslint/no-unused-vars
                  h2: ({ node, ...props }) => <h2 className="text-xl font-bold mt-5 mb-3" {...props} />,
                  // eslint-disable-next-line @typescript-eslint/no-unused-vars
                  h3: ({ node, ...props }) => <h3 className="text-lg font-bold mt-4 mb-2" {...props} />,
                  // eslint-disable-next-line @typescript-eslint/no-unused-vars
                  p: ({ node, ...props }) => <p className="mb-4" {...props} />,
                  // eslint-disable-next-line @typescript-eslint/no-unused-vars
                  ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-4" {...props} />,
                  // eslint-disable-next-line @typescript-eslint/no-unused-vars
                  ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-4" {...props} />,
                  // eslint-disable-next-line @typescript-eslint/no-unused-vars
                  li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                }}
              >
                {displayText}
              </ReactMarkdown>
              {isGenerating && (
                <span className="inline-block w-0.5 h-5 bg-primary-600 dark:bg-primary-400 ml-1 align-middle animate-pulse"></span>
              )}
            </div>
          </div>
        </div>
      )}

      {!displayText && !isError && (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-8 border border-gray-200 dark:border-gray-700 shadow-lg">
          <div className="flex items-start space-x-4">
            <div className="flex-shrink-0">
              <Loader2 className="h-8 w-8 text-primary-600 dark:text-primary-400 animate-spin" />
            </div>
            <div className="flex-1">
              <p className="text-gray-900 dark:text-white font-semibold text-lg mb-1">
                {activeMessage}
              </p>
              <p className="text-gray-600 dark:text-gray-400 text-sm">
                Analyzing critical sections (Item 1A & Item 7) for investment insights...
              </p>
            </div>
          </div>

          {/* Clean skeleton loader */}
          <div className="mt-6 space-y-3">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 animate-pulse"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full animate-pulse delay-75"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6 animate-pulse delay-150"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-4/5 mt-4 animate-pulse delay-200"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-full animate-pulse delay-300"></div>
          </div>
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
  isAuthenticated,
  onRetry,
}: {
  summary: Summary
  filing: Filing
  isPro: boolean
  saveMutation: SaveMutation
  isSaved: boolean
  debug?: boolean
  isAuthenticated: boolean
  onRetry?: () => void
}) {
  const markdownContent = summary.business_overview || ''
  const cleanedMarkdown = useMemo(() => stripInternalNotices(markdownContent), [markdownContent])
  const rawSummary = summary.raw_summary && typeof summary.raw_summary === 'object' ? summary.raw_summary : null

  const fallbackMessage = 'Summary temporarily unavailable — please retry.'
  const writerError = rawSummary?.writer_error
  const writerFallback = rawSummary?.writer?.fallback_used === true
  const fallbackReason = rawSummary?.writer?.fallback_reason
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

  const coverageSnapshot = rawSummary?.section_coverage as
    | { covered_count?: number; total_count?: number; coverage_ratio?: number }
    | undefined
  const hasCoverageSnapshot =
    !!coverageSnapshot &&
    typeof coverageSnapshot.covered_count === 'number' &&
    typeof coverageSnapshot.total_count === 'number' &&
    coverageSnapshot.total_count > 0

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
        a.download = `${filing.filing_type}_${filing.filing_date ? format(new Date(filing.filing_date), 'yyyyMMdd') : 'summary'}.pdf`
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
        a.download = `${filing.filing_type}_${filing.filing_date ? format(new Date(filing.filing_date), 'yyyyMMdd') : 'summary'}.csv`
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
              <button
                onClick={() => saveMutation.mutate(summary.id)}
                disabled={saveMutation.isPending || isSaved}
                className={`inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors ${isSaved
                  ? 'bg-green-100 text-green-700 cursor-not-allowed'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
              >
                {isSaved ? (
                  <>
                    <BookmarkCheck className="h-4 w-4 mr-2" />
                    Saved
                  </>
                ) : (
                  <>
                    <Bookmark className="h-4 w-4 mr-2" />
                    Save Summary
                  </>
                )}
              </button>
            )}
          </div>
        )}
        <SubscriptionGate requirePro={false}>
          <div className="flex flex-wrap items-center gap-3">
            {isPro ? (
              <>
                <button
                  onClick={handleExportPDF}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export PDF
                </button>
                <button
                  onClick={handleExportCSV}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors"
                >
                  <FileDown className="h-4 w-4 mr-2" />
                  Export CSV
                </button>
              </>
            ) : (
              <Link
                href="/pricing"
                className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
              >
                Upgrade to Export
              </Link>
            )}
          </div>
        </SubscriptionGate>
      </div>

      {isError ? (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <AlertCircle className="h-6 w-6 text-yellow-600 mb-2" />
          <p className="text-yellow-800">{fallbackMessage}</p>
        </div>
      ) : (
        <>
          {hasPolishedMarkdown && (
            <section className="bg-white rounded-lg shadow-md p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-2">
                  <FileText className="h-6 w-6 text-primary-600" />
                  <h2 className="text-xl font-semibold text-gray-900">Editorial Summary</h2>
                </div>
                <div className="flex items-center space-x-3">
                  {hasCoverageSnapshot && (
                    <span className="inline-flex items-center rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-800">
                      {coverageSnapshot.covered_count}/{coverageSnapshot.total_count} sections populated
                    </span>
                  )}
                  {writerFallback && (
                    <span className="inline-flex items-center rounded-full border border-amber-400/40 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                      Auto-generated summary
                      {fallbackReason && (
                        <span className="ml-2 text-amber-600" title={fallbackReason}>
                          ⚠️
                        </span>
                      )}
                    </span>
                  )}
                  {isPartial && (
                    <span className="inline-flex items-center rounded-full border border-yellow-200 bg-yellow-50 px-3 py-1 text-xs font-medium text-yellow-800">
                      Partial Result
                    </span>
                  )}
                  {isPartial && onRetry && (
                    <button
                      onClick={onRetry}
                      className="ml-2 inline-flex items-center px-3 py-1 text-xs font-medium text-primary-700 bg-primary-50 rounded-full hover:bg-primary-100 transition-colors border border-primary-200"
                    >
                      Retry Full Analysis
                    </button>
                  )}
                </div>
              </div>
              <ReactMarkdown remarkPlugins={[remarkGfm]} className="markdown-body text-gray-800">
                {cleanedMarkdown}
              </ReactMarkdown>
            </section>
          )}

          {/* Financial Metrics Table */}
          {metadata?.financial_highlights?.table && Array.isArray(metadata.financial_highlights.table) && (
            <>
              <FinancialMetricsTable
                metrics={metadata.financial_highlights.table}
                notes={metadata.financial_highlights.notes}
              />
              <ChartErrorBoundary>
                <FinancialCharts metrics={metadata.financial_highlights.table} />
              </ChartErrorBoundary>
            </>
          )}

          {/* Structured Summary with Tabs */}
          <SummarySections
            summary={summary}
            metrics={metadata?.financial_highlights?.table}
          />
        </>
      )}

      {metadata?.action_items && Array.isArray(metadata.action_items) && metadata.action_items.length > 0 && (
        <section className="bg-white rounded-lg shadow border border-blue-100 p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-3">Suggested Follow-Ups</h3>
          <ul className="list-disc list-inside text-sm text-blue-800 space-y-2">
            {metadata.action_items.map((item: string, index: number) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {debug && rawSummary && (
        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4 text-xs text-gray-100">
          <h3 className="text-sm font-semibold mb-2">Debug: raw summary payload</h3>
          <pre className="whitespace-pre-wrap break-all">
            {JSON.stringify(rawSummary, null, 2)}
          </pre>
        </section>
      )}
    </div>
  )
}

function ChartsSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 animate-pulse">
      <div className="h-5 w-48 bg-gray-200 rounded mb-4" />
      <div className="h-64 bg-gray-100 rounded" />
    </div>
  )
}

function SummarySectionsSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-md border border-gray-200 p-6 animate-pulse space-y-4">
      <div className="h-4 w-32 bg-gray-200 rounded" />
      <div className="space-y-2">
        <div className="h-3 bg-gray-100 rounded" />
        <div className="h-3 bg-gray-100 rounded w-5/6" />
        <div className="h-3 bg-gray-100 rounded w-2/3" />
      </div>
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

