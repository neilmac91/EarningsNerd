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

export interface UseSummaryGenerationArgs {
  filingId: number
  filing: Filing | undefined
  isAuthenticated: boolean
  entryPoint: string
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
  entryPoint,
}: UseSummaryGenerationArgs): SummaryGeneration {
  const queryClient = useQueryClient()

  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingStage, setStreamingStage] = useState<string>('')
  const [streamingMessage, setStreamingMessage] = useState<string>('')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [hasStartedGeneration, setHasStartedGeneration] = useState(false)

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
  })

  const summaryHasPlaceholder = !!(summary?.business_overview && summary.business_overview.includes('Generating summary'))
  const hasSummaryContent = !!(summary?.business_overview && !summaryHasPlaceholder)
  // L1: a surfaced terminal error also ends generation. Without this, an errored run that left the
  // "Generating summary" placeholder in place would keep isGenerating — and the 1s progress poll —
  // alive indefinitely. Partial/full results carry real content, so they clear via the placeholder.
  const isGenerating = (isStreaming || summaryHasPlaceholder) && !generationError

  // Progress poll drives the generation UI. Gated off once real content has arrived and stopped on a
  // terminal progress stage, so it can never outlive the generation it reports on (L1).
  useQuery<SummaryProgressData>({
    queryKey: queryKeys.summaryProgress(filingId),
    queryFn: () => getSummaryProgress(filingId),
    enabled: !!filing && isGenerating && !hasSummaryContent,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.stage === 'completed' || data?.stage === 'error') {
        return false
      }
      return 1000
    },
  })

  const handleGenerateSummary = useCallback(
    async (options?: { force?: boolean }) => {
      // Feature flag for auth requirement (default to false implies POC mode/open access)
      const requireAuth = process.env.NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY === 'true'

      if (requireAuth && !isAuthenticated) {
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
    },
    [filingId, filing, refetch, queryClient, isAuthenticated, entryPoint],
  )

  const handleRegenerateSummary = useCallback(() => {
    handleGenerateSummary({ force: true })
  }, [handleGenerateSummary])

  // Auto-generate summary when page loads if no summary exists
  useEffect(() => {
    const requireAuth = process.env.NEXT_PUBLIC_REQUIRE_AUTH_FOR_SUMMARY === 'true'
    const shouldAutoGenerate = !requireAuth || isAuthenticated

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
