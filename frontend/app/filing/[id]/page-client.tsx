'use client'

import { useParams } from 'next/navigation'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getFiling, getSummary, generateSummary, generateSummaryStream, Filing, Summary, getSubscriptionStatus, saveSummary, getSavedSummaries, getSummaryProgress, SummaryProgressData, getCompany, getCompanyFilings, Company } from '@/lib/api'
import { Loader2, AlertCircle, FileText, Download, FileDown, Bookmark, BookmarkCheck } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import dynamic from 'next/dynamic'
import { format } from 'date-fns'
import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import SubscriptionGate from '@/components/SubscriptionGate'
import FinancialMetricsTable from '@/components/FinancialMetricsTable'
import SummaryProgress from '@/components/SummaryProgress'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import { AxiosError, isAxiosError } from 'axios'

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

export default function FilingPageClient() {
  const params = useParams()
  const identifier = params.id as string
  const isTickerView = !/^\d+$/.test(identifier)

  if (isTickerView) {
    return <TickerFilingsView ticker={identifier.toUpperCase()} />
  }

  const filingId = parseInt(identifier, 10)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingStage, setStreamingStage] = useState<string>('')
  const [streamingMessage, setStreamingMessage] = useState<string>('')
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [hasStartedGeneration, setHasStartedGeneration] = useState(false)

  // Check authentication client-side only
  useEffect(() => {
    setIsAuthenticated(typeof window !== 'undefined' && !!localStorage.getItem('token'))
  }, [])

  useEffect(() => {
    if (!isAuthenticated) {
      setGenerationError('Log in to generate AI summaries.')
      setStreamingStage('error')
      setStreamingMessage('Authentication required.')
      setIsStreaming(false)
    } else if (!isStreaming) {
      setGenerationError(null)
    }
  }, [isAuthenticated, isStreaming])

  const { data: filing, isLoading: filingLoading } = useQuery<Filing>({
    queryKey: ['filing', filingId],
    queryFn: () => getFiling(filingId),
  })

  const { data: summary, isLoading: summaryLoading, refetch, error: summaryError } = useQuery<Summary | null>({
    queryKey: ['summary', filingId],
    queryFn: () => getSummary(filingId),
    retry: false,
    enabled: !!filing, // Only fetch when filing is loaded
  })

  const { data: subscription } = useQuery({
    queryKey: ['subscription'],
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: isAuthenticated,
  })

  const { data: savedSummaries } = useQuery({
    queryKey: ['saved-summaries'],
    queryFn: getSavedSummaries,
    retry: false,
    enabled: isAuthenticated, // Only fetch if user is logged in
  })

  const queryClient = useQueryClient()

  const getFriendlyErrorMessage = (error: unknown): string | null => {
    if (!error) return null

    if (isAxiosError(error)) {
      const payload = error.response?.data as { detail?: string; message?: string } | string | undefined
      if (typeof payload === 'string') {
        return payload
      }
      if (payload?.detail) {
        return payload.detail
      }
      if (payload?.message) {
        return payload.message
      }
      if (error.code === 'ECONNABORTED' || error.message?.toLowerCase().includes('timeout')) {
        return 'Generation timed out, please retry.'
      }
      return error.message
    }

    if (error instanceof Error) {
      return error.message
    }

    if (typeof error === 'string') {
      return error
    }

    return 'Unexpected error occurred while loading the summary.'
  }

  const saveMutation = useMutation({
    mutationFn: (summaryId: number) => saveSummary(summaryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-summaries'] })
    },
  })

  const isSaved = summary && savedSummaries?.some((s: any) => s.summary_id === summary.id)
  const summaryErrorMessage = getFriendlyErrorMessage(summaryError)
  const activeErrorMessage = generationError || summaryErrorMessage

  const handleGenerateSummary = async () => {
    if (!isAuthenticated) {
      setGenerationError('Log in to generate AI summaries.')
      setStreamingStage('error')
      setStreamingMessage('Authentication required.')
      setIsStreaming(false)
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
        (stage: string, message: string) => {
          setGenerationError(null)
          setStreamingStage(stage)
          setStreamingMessage(message)
        },
        (summaryId: number) => {
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
        }
      )
    } catch (error: any) {
      const message = error?.message || 'Failed to generate summary'
      setGenerationError(message)
      setStreamingStage('error')
      setStreamingMessage(message)
    } finally {
      setIsStreaming(false)
    }
  }

  const summaryHasPlaceholder = !!(summary?.business_overview && summary.business_overview.includes('Generating summary'))
  const hasSummaryContent = !!(summary?.business_overview && !summaryHasPlaceholder)

  // Poll progress when generating (for non-streaming fallback)
  const isGenerating = isStreaming || summaryHasPlaceholder
  const { data: progress } = useQuery<SummaryProgressData>({
    queryKey: ['summary-progress', filingId],
    queryFn: () => getSummaryProgress(filingId),
    enabled: !!filing && !!isGenerating,
    refetchInterval: (query) => {
      const data = query.state.data
      // Stop polling if completed or error
      if (data?.stage === 'completed' || data?.stage === 'error') {
        return false
      }
      // Poll every 1 second while generating
      return 1000
    },
  })

  // Auto-generate summary when page loads if no summary exists
  useEffect(() => {
    if (
      filing &&
      isAuthenticated &&
      !summaryLoading &&
      !isStreaming &&
      !hasSummaryContent &&
      !hasStartedGeneration
    ) {
      handleGenerateSummary()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filing, summary, summaryLoading, isStreaming, hasStartedGeneration, hasSummaryContent, isAuthenticated])

  useEffect(() => {
    if (hasSummaryContent) {
      setGenerationError(null)
    }
  }, [hasSummaryContent])

  if (filingLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!filing) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Filing not found</h1>
          <Link href="/" className="text-primary-600 hover:underline">
            Go back home
          </Link>
        </div>
      </div>
    )
  }


  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-white via-gray-50 to-white shadow-lg border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Link href="/" className="text-primary-600 hover:text-primary-700 mb-4 inline-flex items-center space-x-1 transition-colors group">
            <span className="group-hover:-translate-x-1 transition-transform">←</span>
            <span>Back</span>
          </Link>
          
          <div className="flex items-start justify-between">
            <div className="flex-1">
              {filing.company ? (
                <>
                  <div className="flex items-center space-x-3 mb-2">
                    <div className="flex items-center space-x-2">
                      <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
                        {filing.company.name}
                      </h1>
                      <span className="px-3 py-1 bg-gradient-to-r from-primary-600 to-blue-600 text-white text-sm font-bold rounded-lg shadow-sm">
                        {filing.company.ticker}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4 text-sm text-gray-600">
                    <span className="px-3 py-1 bg-gray-100 rounded-md font-semibold text-gray-700">
                      {filing.filing_type}
                    </span>
                    <span className="flex items-center space-x-1">
                      <span>Filed:</span>
                      <span className="font-medium">{format(new Date(filing.filing_date), 'MMMM dd, yyyy')}</span>
                    </span>
                    {filing.company.exchange && (
                      <span className="text-gray-500">
                        {filing.company.exchange}
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <h1 className="text-3xl font-bold text-gray-900 tracking-tight mb-2">
                    {filing.filing_type} Summary
                  </h1>
                  <p className="text-gray-600">
                    Filed: {format(new Date(filing.filing_date), 'MMMM dd, yyyy')}
                  </p>
                </>
              )}
            </div>
            
            {/* Tech badge */}
            <div className="hidden md:flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-primary-50 to-blue-50 rounded-lg border border-primary-200">
              <div className="w-2 h-2 bg-primary-600 rounded-full animate-pulse"></div>
              <span className="text-xs font-semibold text-primary-700">AI Analysis</span>
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
          />
        ) : summary && hasSummaryContent && filing ? (
          <SummaryDisplay summary={summary} filing={filing} isPro={subscription?.is_pro || false} saveMutation={saveMutation} isSaved={!!isSaved} />
        ) : (
          <StreamingSummaryDisplay 
            streamingText=""
            stage={activeErrorMessage ? 'error' : 'initializing'}
            message={activeErrorMessage || 'Initializing AI analysis...'}
            filing={filing}
            error={activeErrorMessage}
            onRetry={handleGenerateSummary}
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
}: {
  streamingText: string
  stage: string
  message: string
  filing: Filing
  error?: string | null
  onRetry?: () => void
}) {
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    setIsClient(true)
  }, [])

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

  const getStageProgress = () => {
    switch (stage) {
      case 'fetching':
        return { percentage: 20, label: 'Fetching filing document...', icon: '📥' }
      case 'parsing':
        return { percentage: 40, label: 'Parsing document structure...', icon: '🔍' }
      case 'analyzing':
        return { percentage: 60, label: 'Analyzing content...', icon: '🧠' }
      case 'summarizing':
        return { percentage: 80, label: 'Generating insights...', icon: '✨' }
      case 'initializing':
        return { percentage: 5, label: 'Initializing AI analysis...', icon: '⚡' }
      case 'error':
        return { percentage: 95, label: 'Generation failed', icon: '⛔️' }
      default:
        return { percentage: 10, label: 'Preparing...', icon: '⚡' }
    }
  }

  const progress = getStageProgress()
  const displayText = streamingText || ''
  const isError = stage === 'error' || !!error
  const isGenerating = !isError && (stage === 'summarizing' || displayText.length > 0)
  const activeMessage = error || message || progress.label

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Progress Header */}
      <div className="bg-gradient-to-br from-white via-primary-50/30 to-blue-50/30 rounded-xl shadow-xl border border-gray-200/50 p-8 relative overflow-hidden">
        {/* Animated background gradient */}
        <div className="absolute inset-0 bg-gradient-to-r from-primary-100/20 via-transparent to-blue-100/20 animate-pulse"></div>
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-4 flex-1">
              <div className="relative w-20 h-20">
                {/* Outer ring with pulse */}
                <div className="absolute inset-0 rounded-full border-4 border-gray-200"></div>
                <div 
                  className="absolute inset-0 rounded-full border-4 border-primary-600 border-t-transparent animate-spin"
                  style={{ 
                    animation: isGenerating ? 'spin 1s linear infinite' : 'none'
                  }}
                ></div>
                {/* Pulsing ring */}
                <div className="absolute inset-0 rounded-full border-4 border-primary-400/50 animate-ping"></div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-xl font-bold text-primary-600 drop-shadow-sm">{progress.percentage}%</span>
                </div>
              </div>
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <span className={`text-3xl ${isError ? '' : 'animate-bounce'}`}>{progress.icon}</span>
                  <h3 className={`text-xl font-bold ${isError ? 'text-red-700' : 'text-gray-900'}`}>
                    {activeMessage}
                  </h3>
                </div>
                <p className="text-sm text-gray-600 font-medium">{filing.filing_type} Filing Analysis</p>
                {/* Dynamic status text */}
                <p
                  className={`text-xs mt-1 ${
                    isError ? 'text-red-600' : 'text-gray-500 animate-pulse'
                  }`}
                >
                  {isError && 'Generation failed. Please retry when ready.'}
                  {!isError && stage === 'initializing' && 'Preparing AI engine...'}
                  {!isError && stage === 'fetching' && 'Downloading SEC filing from EDGAR...'}
                  {!isError && stage === 'parsing' && 'Extracting critical sections (Item 1A & Item 7)...'}
                  {!isError && stage === 'analyzing' && 'Processing with AI model...'}
                  {!isError && stage === 'summarizing' && 'Generating investment insights...'}
                  {!isError && !stage && 'Initializing...'}
                </p>
              </div>
            </div>
          </div>
          
          {/* Enhanced Progress Bar */}
          <div className="w-full bg-gray-200/50 rounded-full h-4 overflow-hidden shadow-inner backdrop-blur-sm">
            <div 
              className="bg-gradient-to-r from-primary-500 via-primary-600 to-blue-600 h-4 rounded-full transition-all duration-700 ease-out relative overflow-hidden"
              style={{ width: `${Math.max(progress.percentage, 5)}%` }}
            >
              {/* Shimmer effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer"></div>
              {/* Glow effect */}
              <div className="absolute inset-0 bg-primary-400/30 blur-sm"></div>
            </div>
          </div>
          
          {/* Enhanced Stage indicator with animations */}
          <div className="mt-6 flex items-center justify-between text-xs">
            {[
              { key: 'fetching', label: 'Fetching', active: stage === 'fetching' || stage === 'parsing' || stage === 'analyzing' || stage === 'summarizing' },
              { key: 'parsing', label: 'Parsing', active: stage === 'parsing' || stage === 'analyzing' || stage === 'summarizing' },
              { key: 'analyzing', label: 'Analyzing', active: stage === 'analyzing' || stage === 'summarizing' },
              { key: 'generating', label: 'Generating', active: stage === 'summarizing' }
            ].map((step, index, array) => (
              <div key={step.key} className="flex items-center flex-1">
                <div className="flex items-center space-x-2 flex-1">
                  <div className="relative">
                    <div className={`w-3 h-3 rounded-full transition-all duration-500 ${step.active ? 'bg-primary-600 scale-125' : 'bg-gray-300'}`}>
                      {step.active && (
                        <div className="absolute inset-0 rounded-full bg-primary-400 animate-ping"></div>
                      )}
                    </div>
                  </div>
                  <span className={`font-medium transition-colors duration-300 ${step.active ? 'text-primary-700 font-semibold' : 'text-gray-400'}`}>
                    {step.label}
                  </span>
                </div>
                {index < array.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 transition-all duration-500 ${step.active ? 'bg-primary-300' : 'bg-gray-200'}`}>
                    <div className={`h-full bg-primary-600 transition-all duration-500 ${step.active ? 'w-full' : 'w-0'}`}></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Streaming Content */}
      {isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 shadow-md">
          <div className="flex items-start space-x-3">
            <AlertCircle className="h-6 w-6 text-red-600 mt-1" />
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-red-700 mb-2">Generation interrupted</h2>
              <p className="text-sm text-red-600">
                {error || message || 'Generation timed out. Please retry to continue.'}
              </p>
              {error?.toLowerCase().includes('log in') && (
                <Link
                  href="/login"
                  className="mt-3 inline-flex items-center text-sm font-semibold text-primary-700 hover:text-primary-600"
                >
                  Go to login →
                </Link>
              )}
              {onRetry && (
                <button
                  onClick={onRetry}
                  className="mt-4 inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors"
                >
                  Retry generation
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {displayText && (
        <div className="bg-white rounded-xl shadow-xl border border-gray-200 p-8 animate-fadeIn">
          <div className="flex items-center space-x-3 mb-6">
            <div className="relative">
              <div className="w-3 h-3 bg-primary-600 rounded-full animate-pulse"></div>
              <div className="absolute inset-0 w-3 h-3 bg-primary-600 rounded-full animate-ping opacity-75"></div>
            </div>
            <h2 className="text-2xl font-bold text-gray-900">AI-Generated Summary</h2>
            {isGenerating && (
              <span className="px-2 py-1 text-xs font-semibold text-primary-700 bg-primary-100 rounded-full animate-pulse">Live</span>
            )}
          </div>
          <div className="prose prose-lg max-w-none">
            <div className="text-gray-800 whitespace-pre-wrap leading-relaxed font-sans">
              {displayText}
              {isGenerating && (
                <span className="inline-block w-2 h-5 bg-primary-600 ml-1 animate-pulse align-middle"></span>
              )}
            </div>
          </div>
        </div>
      )}

      {!displayText && !isError && (
        <div className="bg-gradient-to-br from-primary-50 via-blue-50 to-indigo-50 rounded-xl p-8 border border-primary-200 shadow-lg relative overflow-hidden">
          {/* Animated background */}
          <div className="absolute inset-0 bg-gradient-to-r from-primary-100/50 via-transparent to-blue-100/50 animate-pulse"></div>
          <div className="relative z-10">
            <div className="flex items-center space-x-4">
              <div className="relative">
                <Loader2 className="h-10 w-10 text-primary-600 animate-spin" />
                <div className="absolute inset-0 h-10 w-10 border-4 border-primary-200 rounded-full animate-ping"></div>
              </div>
              <div className="flex-1">
                <p className="text-primary-900 font-semibold text-lg mb-1 animate-pulse">{activeMessage}</p>
                <p className="text-primary-700 text-sm">Analyzing critical sections (Item 1A & Item 7) for investment insights...</p>
              </div>
            </div>
            
            {/* Skeleton loader for content preview */}
            <div className="mt-6 space-y-3 animate-pulse">
              <div className="h-4 bg-primary-200/50 rounded w-3/4"></div>
              <div className="h-4 bg-primary-200/50 rounded w-full"></div>
              <div className="h-4 bg-primary-200/50 rounded w-5/6"></div>
              <div className="h-4 bg-primary-200/50 rounded w-4/5 mt-4"></div>
              <div className="h-4 bg-primary-200/50 rounded w-full"></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryDisplay({ summary, filing, isPro, saveMutation, isSaved }: { summary: Summary; filing: Filing; isPro: boolean; saveMutation: any; isSaved: boolean }) {
  const markdownContent = summary.business_overview || ''
  const cleanedMarkdown = useMemo(() => stripInternalNotices(markdownContent), [markdownContent])
  const rawSummary = summary.raw_summary && typeof summary.raw_summary === 'object'
    ? summary.raw_summary
    : null

  const fallbackMessage = 'Summary temporarily unavailable — please retry.'
  const writerError = rawSummary?.writer_error
  const writerFallback = rawSummary?.writer?.fallback_used === true
  const fallbackReason = rawSummary?.writer?.fallback_reason
  const trimmedMarkdown = cleanedMarkdown.trim()
  const isFallbackMessage = trimmedMarkdown === fallbackMessage
  const hasPolishedMarkdown = trimmedMarkdown.length > 0 && !isFallbackMessage && !writerError

  const isError = Boolean(writerError) || isFallbackMessage || (!hasPolishedMarkdown && trimmedMarkdown.length === 0)

  const metadata = rawSummary
    ? (rawSummary.sections ?? null)
    : null

  const handleExportPDF = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
    const url = `${apiUrl}/api/summaries/filing/${filing.id}/export/pdf`
    
    fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
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
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
    const url = `${apiUrl}/api/summaries/filing/${filing.id}/export/csv`
    
    fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
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
      <div className="flex items-center justify-between mb-4">
        {typeof window !== 'undefined' && localStorage.getItem('token') && (
          <div>
            {summary && summary.id && (
              <button
                onClick={() => saveMutation.mutate(summary.id)}
                disabled={saveMutation.isPending || isSaved}
                className={`inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isSaved
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
          <div className="flex items-center space-x-3">
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

function stripInternalNotices(markdown: string): string {
  if (!markdown) {
    return ''
  }

  const disclaimerPatterns = [
    /^(\*|_)?auto-generated from structured data/i,
    /^(\*|_)?writer output failed validation/i,
    /^(\*|_)?summary generated from structured data/i,
  ]

  const lines = markdown.split('\n')
  let startIndex = 0

  while (startIndex < lines.length) {
    const trimmed = lines[startIndex].trim()
    if (!trimmed) {
      startIndex += 1
      continue
    }

    const matchesDisclaimer = disclaimerPatterns.some((pattern) => pattern.test(trimmed))
    if (matchesDisclaimer) {
      startIndex += 1
      continue
    }

    break
  }

  return lines.slice(startIndex).join('\n')
}

