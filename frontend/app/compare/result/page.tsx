'use client'

import { useEffect, useMemo, useState } from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from 'next/navigation'
import { ComparisonData } from '@/lib/api'
import { TrendingUp, TrendingDown, AlertCircle, BarChart3 } from 'lucide-react'
import { format } from 'date-fns'
import type { RiskFactor } from '../../../types/summary'
import { evaluateComparisonQuality } from '@/lib/QualityGate'
import { fmtPercent, fmtScale, fmtCurrency, parseNumeric } from '@/lib/format'
import SecondaryHeader from '@/components/SecondaryHeader'

const ComparisonMetricChart = dynamic(
  () => import('@/components/ComparisonMetricChart'),
  { ssr: false }
)

export default function CompareResultPage() {
  const router = useRouter()
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null)
  const [qualityError, setQualityError] = useState<string | null>(null)

  useEffect(() => {
    const data = sessionStorage.getItem('comparisonData')
    if (data) {
      setComparisonData(JSON.parse(data))
    } else {
      router.push('/compare')
    }
  }, [router])

  const qualityGate = useMemo(() => {
    if (!comparisonData) {
      return { ok: true }
    }
    return evaluateComparisonQuality(comparisonData)
  }, [comparisonData])

  useEffect(() => {
    if (!qualityGate.ok) {
      setQualityError(qualityGate.message ?? 'Comparison data failed quality checks.')
    } else {
      setQualityError(null)
    }
  }, [qualityGate])

  // All hooks must be called before conditional returns
  // Memoize filings and comparison to avoid useMemo dependency issues
  const filings = useMemo(() => comparisonData?.filings ?? [], [comparisonData?.filings])
  const comparison = useMemo(() => comparisonData?.comparison ?? { financial_metrics: [], risk_factors: [], summary_count: 0 }, [comparisonData?.comparison])

  const filingLabels = useMemo(() => {
    return filings.reduce<Record<number, string>>((acc, filing) => {
      const label = `${filing.company.ticker} ${filing.filing_date ? format(new Date(filing.filing_date), 'MMM yyyy') : ''}`.trim()
      acc[filing.id] = label
      return acc
    }, {})
  }, [filings])

  type MetricSeriesPoint = {
    filingId: number
    label: string
    display: string
    numeric: number | null
    delta: number | null
  }

  type MetricInsight = {
    metric: string
    series: MetricSeriesPoint[]
    baseIndex: number
  }

  interface MetricData {
    metric?: string
    name?: string
    current_period?: string | number | null
    currentPeriod?: string | number | null
    value?: string | number | null
    amount?: string | number | null
  }

  const metricInsights: MetricInsight[] = useMemo(() => {
    if (!comparison.financial_metrics.length) {
      return []
    }

    const metricsMap = new Map<string, MetricInsight>()

    comparison.financial_metrics.forEach((fm) => {
      const seriesMetrics = fm.metrics || []
      seriesMetrics.forEach((metric: MetricData, index: number) => {
        const metricName = metric.metric || metric.name || `Metric ${index + 1}`
        if (!metricsMap.has(metricName)) {
          metricsMap.set(metricName, {
            metric: metricName,
            series: [],
            baseIndex: 0,
          })
        }
        const entry = metricsMap.get(metricName)!
        const rawValue =
          metric.current_period ??
          metric.currentPeriod ??
          metric.value ??
          metric.amount ??
          ''
        const displayValue = (() => {
          if (rawValue === null || rawValue === undefined) return ''
          if (typeof rawValue === 'number') return fmtScale(rawValue, { digits: 2 })
          const text = String(rawValue).trim()
          if (!text) return ''
          const numeric = parseNumeric(text)
          if (numeric === null) return text
          if (text.includes('%')) return fmtPercent(numeric)
          if (text.includes('$')) return fmtCurrency(numeric)
          return fmtScale(numeric, { digits: 2 })
        })()
        const numericValue = (() => {
          if (rawValue === null || rawValue === undefined) return null
          if (typeof rawValue === 'number' && Number.isFinite(rawValue)) return rawValue
          const numeric = parseNumeric(String(rawValue))
          return Number.isFinite(numeric as number) ? (numeric as number) : null
        })()

        entry.series.push({
          filingId: fm.filing_id,
          label: filingLabels[fm.filing_id] ?? String(fm.filing_id),
          display: displayValue,
          numeric: numericValue,
          delta: null,
        })
      })
    })

    const insightsArray = Array.from(metricsMap.values()).map((insight) => {
      const baseIndex = insight.series.findIndex((point) => point.numeric !== null)
      const referenceIndex = baseIndex >= 0 ? baseIndex : 0
      const referenceValue =
        insight.series[referenceIndex]?.numeric ?? null

      insight.series = insight.series.map((point, idx) => {
        if (
          referenceValue !== null &&
          point.numeric !== null &&
          idx !== referenceIndex &&
          referenceValue !== 0
        ) {
          return {
            ...point,
            delta: (point.numeric - referenceValue) / Math.abs(referenceValue),
          }
        }
        return {
          ...point,
          delta: idx === referenceIndex ? 0 : null,
        }
      })

      return {
        ...insight,
        baseIndex: referenceIndex,
      }
    })

    return insightsArray
  }, [comparison.financial_metrics, filingLabels])

  // Early returns after all hooks
  if (!comparisonData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Loading comparison...</p>
        </div>
      </div>
    )
  }

  if (qualityError) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
        <div className="max-w-lg bg-white border border-red-200 shadow-lg rounded-xl p-8 space-y-4">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-full bg-red-100 flex items-center justify-center">
              <AlertCircle className="h-6 w-6 text-red-600" />
            </div>
            <h1 className="text-xl font-semibold text-red-700">Quality Gate Failed</h1>
          </div>
          <p className="text-sm text-red-600 leading-relaxed">
            {qualityError}
          </p>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => router.push('/compare')}
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
            >
              Start a new comparison
            </button>
            <button
              onClick={() => {
                sessionStorage.removeItem('comparisonData')
                router.push('/compare')
              }}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Clear cached data
            </button>
          </div>
        </div>
      </div>
    )
  }

  const deltaHighlights = (() => {
    const deltas: Array<{
      metric: string
      label: string
      delta: number
      display: string
    }> = []

    metricInsights.forEach((insight) => {
      insight.series.forEach((point, idx) => {
        if (idx === insight.baseIndex || point.delta === null) return
        deltas.push({
          metric: insight.metric,
          label: point.label,
          delta: point.delta,
          display: point.display,
        })
      })
    })

    return deltas
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
      .slice(0, 6)
  })()

  const metricsWithTrend = metricInsights.filter(
    (insight) =>
      insight.series.filter((point) => point.numeric !== null).length >= 2
  ).slice(0, 4)

  return (
    <div className="min-h-screen bg-slate-50">
      <SecondaryHeader
        title="Filing Comparison"
        subtitle={`Comparing ${filings.length} ${filings.length === 1 ? 'filing' : 'filings'}`}
        backHref="/compare"
        backLabel="Back to compare"
        actions={
          <button
            onClick={() => router.push('/compare')}
            className="text-sm font-medium text-slate-600 hover:text-slate-900"
          >
            New comparison
          </button>
        }
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        {/* Filings Header */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {filings.map((filing) => (
              <div key={filing.id} className="border border-gray-200 rounded-lg p-4">
                <div className="font-semibold text-gray-900">{filing.company.ticker}</div>
                <div className="text-sm text-gray-600">{filing.filing_type}</div>
                <div className="text-xs text-gray-500 mt-1">
                  {filing.filing_date && format(new Date(filing.filing_date), 'MMM yyyy')}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Financial Metrics Comparison */}
        {comparison.financial_metrics.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="flex items-center space-x-2 mb-4">
              <BarChart3 className="h-6 w-6 text-primary-600" />
              <h2 className="text-xl font-semibold text-gray-900">Financial Metrics</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Metric</th>
                    {filings.map((filing) => (
                      <th key={filing.id} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        {filing.company.ticker} ({filing.filing_date && format(new Date(filing.filing_date), 'MMM yyyy')})
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {metricInsights.slice(0, 12).map((insight) => (
                    <tr key={insight.metric}>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{insight.metric}</td>
                      {insight.series.map((point, idx) => {
                        const isBaseline = idx === insight.baseIndex
                        const delta = point.delta
                        const positive = typeof delta === 'number' && delta > 0
                        const negative = typeof delta === 'number' && delta < 0
                        return (
                          <td key={`${insight.metric}-${point.filingId}`} className="px-4 py-3 text-sm text-gray-700">
                            <div className="flex flex-col">
                              <span>{point.display || '—'}</span>
                              {!isBaseline && delta !== null && (
                                <span
                                  className={`inline-flex items-center text-xs font-semibold mt-1 ${
                                    positive
                                      ? 'text-green-600'
                                      : negative
                                      ? 'text-red-600'
                                      : 'text-gray-500'
                                  }`}
                                >
                                  {positive && <TrendingUp className="h-3 w-3 mr-1" />}
                                  {negative && <TrendingDown className="h-3 w-3 mr-1" />}
                                  {`${delta > 0 ? '+' : ''}${(delta * 100).toFixed(1)}% vs baseline`}
                                </span>
                              )}
                              {isBaseline && (
                                <span className="inline-flex items-center text-xs font-medium text-gray-400 mt-1">
                                  Baseline
                                </span>
                              )}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Delta Highlights */}
        {deltaHighlights.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-primary-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Key Movements</h2>
            <div className="grid md:grid-cols-2 gap-4">
              {deltaHighlights.map((item, idx) => {
                const positive = item.delta > 0
                const percentLabel = `${item.delta > 0 ? '+' : ''}${(item.delta * 100).toFixed(1)}%`
                return (
                  <div
                    key={`${item.metric}-${item.label}-${idx}`}
                    className="border border-gray-200 rounded-lg p-4 flex items-start justify-between"
                  >
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{item.metric}</p>
                      <p className="text-sm text-gray-600">{item.label}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        Value: <span className="font-medium text-gray-700">{item.display || '—'}</span>
                      </p>
                    </div>
                    <div className={`flex items-center text-sm font-semibold ${positive ? 'text-green-600' : 'text-red-600'}`}>
                      {positive ? <TrendingUp className="h-4 w-4 mr-1" /> : <TrendingDown className="h-4 w-4 mr-1" />}
                      {percentLabel}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Trend Charts */}
        {metricsWithTrend.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Trend Overlays</h2>
            <div className="grid md:grid-cols-2 gap-6">
              {metricsWithTrend.map((insight) => (
                <div key={insight.metric} className="border border-gray-100 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-gray-900">{insight.metric}</h3>
                    <span className="text-xs text-gray-500">
                      Baseline: {insight.series[insight.baseIndex]?.label}
                    </span>
                  </div>
                  <ComparisonMetricChart
                    data={insight.series.map((point) => ({
                      label: point.label,
                      value: point.numeric,
                    }))}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Risk Factors Comparison */}
        {comparison.risk_factors.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center space-x-2 mb-4">
              <AlertCircle className="h-6 w-6 text-red-600" />
              <h2 className="text-xl font-semibold text-gray-900">Risk Factors</h2>
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-4">
              {filings.map((filing) => {
                const risks = comparison.risk_factors.find(rf => rf.filing_id === filing.id)?.risks || []
                const evidenceKeys = ['excerpt', 'text', 'quote', 'source', 'reference', 'tag', 'xbrl_tag', 'xbrlTag', 'citation']

                const formatEvidence = (value: unknown): string => {
                  if (!value) return ''
                  if (Array.isArray(value)) {
                    const parts = value.map((item) => formatEvidence(item)).filter(Boolean)
                    return parts.join('; ')
                  }
                  if (typeof value === 'object') {
                    const parts: string[] = []
                    evidenceKeys.forEach((key) => {
                      if (value && typeof value === 'object' && key in value) {
                        const part = formatEvidence((value as Record<string, unknown>)[key])
                        if (part) {
                          parts.push(part)
                        }
                      }
                    })
                    if (parts.length === 0 && 'value' in (value as Record<string, unknown>)) {
                      const fallback = formatEvidence((value as Record<string, unknown>).value)
                      if (fallback) {
                        parts.push(fallback)
                      }
                    }
                    return parts.join(' | ')
                  }
                  if (typeof value === 'string') {
                    return value.trim()
                  }
                  return String(value).trim()
                }

                    const normalizeRisk = (risk: unknown): RiskFactor | null => {
                  if (!risk || typeof risk !== 'object') {
                    return null
                  }
                  const riskObj = risk as Record<string, unknown>
                  const title = typeof riskObj.title === 'string' ? riskObj.title.trim() : null
                  const description = typeof riskObj.description === 'string' ? riskObj.description.trim() : null
                  const summaryCandidate =
                    (typeof riskObj.summary === 'string' && riskObj.summary.trim()) ||
                    (description && description) ||
                    (title && title) ||
                    ''

                  if (!summaryCandidate) {
                    return null
                  }

                  const supportingEvidence = formatEvidence(
                    riskObj.supporting_evidence ?? riskObj.supportingEvidence ?? riskObj.evidence ?? riskObj.source
                  )

                  if (!supportingEvidence) {
                    return null
                  }

                  return {
                    summary: summaryCandidate,
                    supporting_evidence: supportingEvidence,
                    title: title || null,
                    description: description || null,
                  }
                }

                const normalizedRisks = Array.isArray(risks)
                  ? risks
                      .map((risk) => normalizeRisk(risk))
                      .filter((risk): risk is RiskFactor => Boolean(risk && risk.supporting_evidence))
                  : []
                return (
                  <div key={filing.id} className="border border-gray-200 rounded-lg p-4">
                    <h3 className="font-semibold text-gray-900 mb-2">
                      {filing.company.ticker}
                    </h3>
                    {normalizedRisks.length > 0 ? (
                      <ul className="space-y-2">
                        {normalizedRisks.slice(0, 5).map((risk, index) => {
                          const label = risk.title
                            ? `${risk.title}${risk.description ? `: ${risk.description}` : ''}`
                            : risk.summary
                          return (
                            <li key={`${risk.summary}-${index}`} className="text-sm text-gray-700 space-y-1">
                              <div>{label}</div>
                              <div className="text-xs text-gray-500">
                                <span className="font-medium">Evidence:</span> {risk.supporting_evidence}
                              </div>
                            </li>
                          )
                        })}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-500">No supported risks identified.</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

