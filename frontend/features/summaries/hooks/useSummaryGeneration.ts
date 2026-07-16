'use client'

import { useCallback, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import {
  getSummary,
  generateSummaryStream,
  isPaywallStreamError,
  getSummaryProgress,
  type Summary,
  type SummaryProgressData,
} from '../api/summaries-api'
import type { Filing } from '@/features/filings/api/filings-api'
import { queryKeys } from '@/lib/queryKeys'
import analytics from '@/lib/analytics'

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

const PROGRESS_POLL_INTERVAL_MS = 1000

// The backend writes exactly THREE terminal progress stages — completed, error, and partial
// (summary_generation_service.py `record_progress(..., "partial")` on the timeout / low-coverage
// path). All three must stop the poll: otherwise a placeholder-summary page whose backing run ends
// `partial` (e.g. the flag-off legacy cron that discards partials) re-polls every second forever
// (L1). `SummaryProgressData.stage` is typed narrower than the runtime, so accept a bare string.
const TERMINAL_PROGRESS_STAGES: ReadonlySet<string> = new Set(['completed', 'error', 'partial'])

/** Progress-poll cadence: stop (`false`) on any terminal stage, else re-poll. Exported for testing. */
export function progressRefetchInterval(stage: string | undefined): number | false {
  return stage && TERMINAL_PROGRESS_STAGES.has(stage) ? false : PROGRESS_POLL_INTERVAL_MS
}

export interface UseSummaryGenerationArgs {
  filingId: number
  filing: Filing | undefined
  isAuthenticated: boolean
  /** Whether the /me auth query has SETTLED. On mount it's false while isAuthenticated is also
   * false — indistinguishable from a guest without this flag — so the auto-generate effect must
   * wait for it or a logged-in user's page would flash the signup gate (and a guest's would fire
   * a doomed request). */
  isAuthResolved: boolean
  entryPoint: string
  /** Server-fetched seed for the summary query (SEO/ISR — see filing/[id]/page.tsx). `null` means
   * the backend confirmed no summary exists (matches getSummary's normalization); `undefined`
   * means no seed — the query loads client-side as before. */
  initialSummary?: Summary | null
}

export interface SummaryGeneration {
  summary: Summary | null | undefined
  summaryLoading: boolean
  streamingText: string
  streamingStage: string
  streamingMessage: string
  elapsedSeconds: number
  generationError: string | null
  activeErrorMessage: string | null
  isStreaming: boolean
  hasStartedGeneration: boolean
  isGenerating: boolean
  hasSummaryContent: boolean
  handleGenerateSummary: (options?: { force?: boolean }) => Promise<void>
  handleRegenerateSummary: () => void
  refetchSummary: () => void
}

/**
 * The filing page's summary-generation state machine, extracted from page-client.tsx (F2).
 * Owns the streaming lifecycle, the summary + progress queries, and the auto-generate effect;
 * the view consumes the returned surface and stays layout-only.
 */
export function useSummaryGeneration({
  filingId,
  filing,
  isAuthenticated,
  isAuthResolved,
  entryPoint,
  initialSummary,
}: UseSummaryGenerationArgs): SummaryGeneration {
  const queryClient = useQueryClient()

  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingStage, setStreamingStage] = useState<string>('')
  const [streamingMessage, setStreamingMessage] = useState<string>('')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [hasStartedGeneration, setHasStartedGeneration] = useState(false)

  // initialDataUpdatedAt: 0 marks the ISR-cached seed as already stale so the client refetches
  // on mount — the seed only guarantees the first paint (and the crawler HTML).
  const {
    data: summary,
    isLoading: summaryLoading,
    refetch,
    error: summaryError,
  } = useQuery<Summary | null>({
    queryKey: queryKeys.summary(filingId),
    queryFn: () => getSummary(filingId),
    retry: false,
    enabled: !!filing,
    initialData: initialSummary,
    initialDataUpdatedAt: 0,
  })

  const summaryHasPlaceholder = !!(summary?.business_overview && summary.business_overview.includes('Generating summary'))
  const hasSummaryContent = !!(summary?.business_overview && !summaryHasPlaceholder)
  // L1: a surfaced terminal error also ends generation. Without this, an errored run that left the
  // "Generating summary" placeholder in place would keep isGenerating — and the 1s progress poll —
  // alive indefinitely. Partial/full results carry real content, so they clear via the placeholder.
  const isGenerating = (isStreaming || summaryHasPlaceholder) && !generationError

  // Progress poll drives the generation UI. Gated off once real content has arrived and stopped on
  // ANY of the backend's three terminal stages (completed/error/partial), so it can never outlive
  // the generation it reports on (L1 — the poll's terminal set must match record_progress's).
  useQuery<SummaryProgressData>({
    queryKey: queryKeys.summaryProgress(filingId),
    queryFn: () => getSummaryProgress(filingId),
    enabled: !!filing && isGenerating && !hasSummaryContent,
    refetchInterval: (query) => progressRefetchInterval(query.state.data?.stage),
  })

  const handleGenerateSummary = useCallback(
    async (options?: { force?: boolean }) => {
      // Generation requires an account (the backend 401s guests). The page renders a signup gate
      // for unauthenticated visitors, so this is a defensive backstop, not the primary UX.
      if (!isAuthenticated) {
        setGenerationError('Please sign in to generate summaries.')
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
          { force: options?.force, entryPoint },
        )
      } catch (error: unknown) {
        // Reuse the shared friendly-error mapping (Axios detail/message + timeout) rather than a
        // bare .message, so a thrown generation error reads the same as a failed summary fetch.
        const message = getFriendlyErrorMessage(error) || 'Failed to generate summary'
        setGenerationError(message)
        setStreamingStage('error')
        setStreamingMessage(message)
        setIsStreaming(false)
        setStreamingText('')
      } finally {
        setIsStreaming(false)
      }
    },
    [filingId, filing, refetch, queryClient, isAuthenticated, entryPoint],
  )

  const handleRegenerateSummary = useCallback(() => {
    handleGenerateSummary({ force: true })
  }, [handleGenerateSummary])

  // Auto-generate summary when page loads if no summary exists. Signed-in users only, and only
  // once the /me query has SETTLED — before that, isAuthenticated is false for everyone, so firing
  // early would send a logged-in user's request without their session resolved and a guest's
  // straight into the backend's 401. Guests instead get the page's signup gate.
  useEffect(() => {
    const shouldAutoGenerate = isAuthResolved && isAuthenticated

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
  }, [
    filing,
    summaryLoading,
    isStreaming,
    hasSummaryContent,
    hasStartedGeneration,
    generationError,
    handleGenerateSummary,
    isAuthenticated,
    isAuthResolved,
  ])

  useEffect(() => {
    if (hasSummaryContent) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- clears stale error state once async-streamed summary content arrives
      setGenerationError(null)
    }
  }, [hasSummaryContent])

  const summaryErrorMessage = getFriendlyErrorMessage(summaryError)
  const activeErrorMessage = generationError || summaryErrorMessage

  return {
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
    isGenerating,
    hasSummaryContent,
    handleGenerateSummary,
    handleRegenerateSummary,
    refetchSummary: refetch,
  }
}
