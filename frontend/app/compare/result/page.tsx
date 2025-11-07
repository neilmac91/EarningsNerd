'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ComparisonData } from '@/lib/api'
import { TrendingUp, TrendingDown, AlertCircle, BarChart3, X } from 'lucide-react'
import Link from 'next/link'
import { format } from 'date-fns'
import type { RiskFactor } from '../../../types/summary'
import { evaluateComparisonQuality } from '@/lib/QualityGate'
import { fmtPercent, fmtScale, fmtCurrency, parseNumeric } from '@/lib/format'

export default function CompareResultPage() {
  const router = useRouter()
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null)

  useEffect(() => {
    const data = sessionStorage.getItem('comparisonData')
    if (data) {
      setComparisonData(JSON.parse(data))
    } else {
      router.push('/compare')
    }
  }, [router])

  const [qualityError, setQualityError] = useState<string | null>(null)

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

  const { filings, comparison } = comparisonData

  const resolveMetricValue = (raw: any): string => {
    if (raw === null || raw === undefined) {
      return ''
    }

    if (typeof raw === 'number') {
      return fmtScale(raw, { digits: 2 })
    }

    const text = String(raw).trim()
    if (!text) {
      return ''
    }

    const numeric = parseNumeric(text)
    if (numeric === null) {
      return text
    }

    if (text.includes('%')) {
      return fmtPercent(numeric)
    }

    if (text.includes('$')) {
      return fmtCurrency(numeric)
    }

    return fmtScale(numeric, { digits: 2 })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <Link href="/compare" className="text-primary-600 hover:text-primary-700">
              ← Back to Compare
            </Link>
            <button
              onClick={() => router.push('/compare')}
              className="text-gray-600 hover:text-gray-900"
            >
              New Comparison
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Filing Comparison</h1>
          <p className="text-gray-600">
            Comparing {filings.length} {filings.length === 1 ? 'filing' : 'filings'}
          </p>
        </div>

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
                  {comparison.financial_metrics[0]?.metrics?.slice(0, 10).map((metric: any, index: number) => (
                    <tr key={index}>
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{metric.metric}</td>
                      {comparison.financial_metrics.map((fm) => {
                        const cell = fm.metrics[index]
                        const value = resolveMetricValue(cell?.current_period ?? cell?.currentPeriod)
                        return (
                          <td key={fm.filing_id} className="px-4 py-3 text-sm text-gray-600">
                            {value}
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

                const formatEvidence = (value: any): string => {
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

                    const normalizeRisk = (risk: any): RiskFactor | null => {
                  if (!risk || typeof risk !== 'object') {
                    return null
                  }
                  const title = typeof risk.title === 'string' ? risk.title.trim() : null
                  const description = typeof risk.description === 'string' ? risk.description.trim() : null
                  const summaryCandidate =
                    (typeof risk.summary === 'string' && risk.summary.trim()) ||
                    (description && description) ||
                    (title && title) ||
                    ''

                  if (!summaryCandidate) {
                    return null
                  }

                  const supportingEvidence = formatEvidence(
                    (risk.supporting_evidence ?? risk.supportingEvidence ?? risk.evidence ?? risk.source) as unknown
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

