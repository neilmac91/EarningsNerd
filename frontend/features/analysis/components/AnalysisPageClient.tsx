'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import CompanySearch from '@/features/companies/components/CompanySearch'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge, Button, Card, Notice, Skeleton } from '@/components/ui'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'
import analytics from '@/lib/analytics'

import {
  analysisPdfUrl,
  getAnalysisCoverage,
  getAnalysisDataset,
  isAnalysisPaywallError,
  streamAnalysis,
  type AnalysisCoverage,
  type AnalysisDataset,
  type AnalysisMode,
} from '@/features/analysis/api/analysis-api'
import AiDisclaimer from '@/components/AiDisclaimer'
import { downloadDatasetCsv } from '@/features/analysis/lib/chartExport'
import AnalysisTeaser from './AnalysisTeaser'
import KpiStrip from './KpiStrip'
import MetricsTable from './MetricsTable'
import NarrativePane, { type NarrativeState } from './NarrativePane'
import PeriodPicker, { defaultRange, type PeriodRange } from './PeriodPicker'
import TrendCharts from './TrendCharts'

/**
 * Multi-Period Analysis — the Pro flagship page.
 *
 * Flow: pick a company (CompanySearch in onSelect mode) → coverage loads the real period chips
 * (auth-only; lazily syncs the SEC companyfacts history server-side) → pick Annual/Quarterly +
 * a period range → Run: the deterministic dataset renders the KPI strip / charts / metrics grid
 * instantly, then the AI narrative streams in with verified citations. Free users get the full
 * picker plus the PeekLocked sample instead of live results (zero AI cost, maximum clarity about
 * what Pro unlocks).
 */
export default function AnalysisPageClient() {
  const [ticker, setTicker] = useState<string | null>(null)
  const [mode, setMode] = useState<AnalysisMode>('annual')
  const [range, setRange] = useState<PeriodRange | null>(null)
  const [dataset, setDataset] = useState<AnalysisDataset | null>(null)
  const [datasetError, setDatasetError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [narrative, setNarrative] = useState<NarrativeState>({ status: 'idle', text: '' })
  const abortRef = useRef<AbortController | null>(null)
  const queryClient = useQueryClient()

  // Tri-state auth: undefined = resolving, null = guest, object = signed in (Header's contract).
  // Keys come from the F1 registry so this page shares the Header's auth/subscription cache and can
  // never drift into a split-brain key.
  const { data: user } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 60_000 })
  const { data: subscription } = useQuery({
    queryKey: queryKeys.subscription(),
    queryFn: getSubscriptionStatus,
    enabled: !!user,
    staleTime: 60_000,
  })
  const isPro = !!subscription?.is_pro
  const authResolved = user !== undefined

  const {
    data: coverage,
    isLoading: coverageLoading,
    error: coverageError,
  } = useQuery<AnalysisCoverage>({
    queryKey: queryKeys.analysisCoverage(ticker),
    queryFn: () => getAnalysisCoverage(ticker as string),
    enabled: !!ticker && !!user,
    // First-touch server sync can answer `syncing: true` — poll until the periods arrive.
    refetchInterval: (query) => (query.state.data?.syncing ? 4000 : false),
    staleTime: 10 * 60 * 1000,
    retry: (failureCount, err) =>
      err instanceof ApiError && err.isRetryable ? failureCount < 2 : false,
  })

  // New coverage / mode → reset the range to the newest window and clear stale results.
  useEffect(() => {
    if (coverage) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync selection to freshly-loaded coverage (external data), not derivable at render time
      setRange(defaultRange(coverage, mode))
    }
  }, [coverage, mode])

  const resetResults = useCallback(() => {
    abortRef.current?.abort()
    setDataset(null)
    setDatasetError(null)
    setNarrative({ status: 'idle', text: '' })
    setRunning(false)
  }, [])

  const selectCompany = useCallback(
    (nextTicker: string) => {
      resetResults()
      setMode('annual')
      setTicker(nextTicker.toUpperCase())
    },
    [resetResults]
  )

  const startNarrative = useCallback(
    (force: boolean) => {
      if (!ticker || !range) return
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setNarrative({ status: 'streaming', text: '', stage: 'assembling' })
      void streamAnalysis(
        ticker,
        { mode, start_period: range.start, end_period: range.end, force },
        {
          onProgress: (stage) => setNarrative((s) => (s.status === 'streaming' ? { ...s, stage } : s)),
          onToken: (text) => setNarrative((s) => ({ ...s, status: 'streaming', text: s.text + text })),
          onComplete: (completion) => {
            setNarrative({ status: 'done', text: completion.narrative, completion })
            setRunning(false)
            // A fresh generation consumed quota — keep the settings usage meter honest.
            if (!completion.cached) void queryClient.invalidateQueries({ queryKey: queryKeys.usage() })
          },
          onError: (message) => {
            setNarrative({ status: 'error', text: '', error: message })
            setRunning(false)
          },
        },
        controller.signal
      )
    },
    [ticker, range, mode, queryClient]
  )

  const run = useCallback(async () => {
    if (!ticker || !range || running) return
    setRunning(true)
    setDatasetError(null)
    setNarrative({ status: 'idle', text: '' })
    analytics.analysisRun({ ticker, mode, start: range.start, end: range.end })
    try {
      const result = await getAnalysisDataset(ticker, {
        mode,
        start_period: range.start,
        end_period: range.end,
      })
      setDataset(result)
      startNarrative(false)
    } catch (err) {
      setRunning(false)
      setDataset(null)
      setDatasetError(
        err instanceof ApiError ? err.detail : 'Could not build the dataset. Please try again.'
      )
    }
  }, [ticker, range, mode, running, startNarrative])

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), [])

  // Blob download with credentials (bearer/cookie ride the fetch) — the filing-page export pattern.
  const exportPdf = useCallback(() => {
    const analysisId = narrative.completion?.analysis_id
    if (analysisId == null || !ticker) return
    void fetch(analysisPdfUrl(analysisId), { credentials: 'include' })
      .then((response) => {
        if (!response.ok) throw new Error(`Export failed (${response.status})`)
        return response.blob()
      })
      .then((blob) => {
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${ticker}_multi_period_analysis.pdf`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
      })
      .catch(() => setDatasetError('PDF export failed. Please try again.'))
  }, [narrative.completion?.analysis_id, ticker])

  const unsupported = coverage && !coverage.supported
  const paywalled = narrative.status === 'error' && isAnalysisPaywallError(narrative.error || '')

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
      <header className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Multi-Period Analysis
          </h1>
          <Badge variant="pro">Pro</Badge>
        </div>
        <p className="max-w-2xl text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Pick a company and up to 10 fiscal years or 12 quarters. Get the full trend picture —
          growth, margins, cash, balance sheet — with an AI analysis where every cited figure is
          verified against SEC XBRL.
        </p>
      </header>

      <Card className="p-5">
        <div className="mb-1 text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
          Company
        </div>
        <CompanySearch onSelect={selectCompany} />
        {ticker && (
          <div className="mt-3 flex items-center gap-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            <CompanyLogo ticker={ticker} name={coverage?.company_name || ticker} size={20} />
            <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">
              {coverage?.company_name || ticker}
            </span>
            <span className="tnum font-data">{ticker}</span>
          </div>
        )}

        {/* Signed-out: the picker needs auth for real coverage — invite sign-in, show the sample below. */}
        {ticker && authResolved && !user && (
          <Notice
            variant="info"
            className="mt-4"
            title={
              <>
                <Link href="/login" className="font-semibold underline">
                  Sign in
                </Link>{' '}
                to see which periods are available for {ticker}.
              </>
            }
          />
        )}

        {ticker && !!user && (
          <div className="mt-4">
            {coverageLoading && !coverage ? (
              <div role="status" aria-label="Loading available periods">
                <Skeleton className="h-16 w-full rounded-lg" />
                <span className="sr-only">Loading…</span>
              </div>
            ) : coverageError ? (
              <Notice
                variant="error"
                title={
                  coverageError instanceof ApiError
                    ? coverageError.detail
                    : 'Could not load available periods. Please try again.'
                }
              />
            ) : coverage?.syncing ? (
              <Notice
                variant="info"
                title={`Fetching ${ticker}'s full SEC reporting history — this takes a few seconds on first touch.`}
              />
            ) : unsupported ? (
              <Notice
                variant="info"
                title={
                  coverage?.reason === 'ifrs_filer'
                    ? 'This company reports under IFRS (foreign filer) — multi-period analysis for IFRS filers is coming later.'
                    : 'No analyzable reporting history found for this company yet.'
                }
              />
            ) : coverage ? (
              <div className="flex flex-col gap-4">
                <PeriodPicker
                  coverage={coverage}
                  mode={mode}
                  range={range}
                  onModeChange={(nextMode) => {
                    setMode(nextMode)
                    resetResults()
                  }}
                  onRangeChange={setRange}
                />
                {isPro && (
                  <div>
                    <Button onClick={run} loading={running} disabled={!range || running}>
                      Run analysis
                    </Button>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        )}
      </Card>

      {/* Free users (and guests): the real experience, sample data, locked. */}
      {authResolved && (!user || (subscription && !isPro)) && <AnalysisTeaser forTicker={ticker || undefined} />}

      {isPro && datasetError && <Notice variant="error" title={datasetError} />}
      {isPro && paywalled && (
        <Notice
          variant="info"
          title={narrative.error}
          description={
            <Link href="/pricing" className="font-semibold underline">
              See plans
            </Link>
          }
        />
      )}

      {isPro && dataset && (
        <div className="flex flex-col gap-4">
          <KpiStrip dataset={dataset} />
          <TrendCharts dataset={dataset} exportEnabled />
          <NarrativePane
            state={narrative}
            onRefresh={() => startNarrative(true)}
            refreshDisabled={narrative.status === 'streaming'}
            onExport={exportPdf}
          />
          <MetricsTable dataset={dataset} onExportCsv={() => downloadDatasetCsv(dataset)} />
          <AiDisclaimer lead={false}>
            All figures from SEC XBRL (companyfacts). Growth rates, margins and ratios are
            computed server-side — the AI narrative only cites values from this dataset. † =
            computed Q4.
          </AiDisclaimer>
        </div>
      )}

      {/* Legal one-liner: outside every result/Pro gate so guests, free users viewing the sample,
          and Pro users all see it (drafted in the audit's legal review; pending counsel polish). */}
      <AiDisclaimer lead={false}>
        This analysis is AI-generated, for informational purposes only, and is not investment
        advice or a recommendation; past performance does not predict future results. Verify
        against the original filings on SEC EDGAR. See our{' '}
        <Link href="/terms" className="underline">
          Terms
        </Link>
        .
      </AiDisclaimer>
    </div>
  )
}
