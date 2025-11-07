'use client'

import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { fmtCurrency, fmtPercent, fmtScale, parseNumeric } from '@/lib/format'

interface FinancialMetric {
  metric: string
  current_period: string
  prior_period: string
  commentary?: string
}

interface FinancialMetricsTableProps {
  metrics?: FinancialMetric[]
  notes?: string
}

export default function FinancialMetricsTable({ metrics, notes }: FinancialMetricsTableProps) {
  if (!metrics || metrics.length === 0) {
    return null
  }

  const hasComparatives = metrics.some((metric) => parseNumeric(metric.prior_period) !== null)

  const calculateChange = (current: string, prior: string): { change: number | null; percent: number | null } => {
    const currentVal = parseNumeric(current)
    const priorVal = parseNumeric(prior)

    if (currentVal === null || priorVal === null || priorVal === 0) {
      return { change: null, percent: null }
    }

    const change = currentVal - priorVal
    const percent = (change / Math.abs(priorVal)) * 100

    return { change, percent }
  }

  const formatMetricValue = (value: string): string => {
    if (!value) {
      return ''
    }

    const numeric = parseNumeric(value)
    if (numeric === null) {
      return value
    }

    if (value.includes('%')) {
      return fmtPercent(numeric)
    }

    if (value.includes('$')) {
      return fmtCurrency(numeric)
    }

    return fmtScale(numeric, { digits: 2 })
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">Financial Highlights</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Metric
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Current Period
              </th>
              {hasComparatives && (
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Prior Period
                </th>
              )}
              {hasComparatives && (
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Change
                </th>
              )}
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Investor Takeaway
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {metrics.map((metric, index) => {
              const { change, percent } = calculateChange(metric.current_period, metric.prior_period)
              const isPositive = change !== null && change > 0
              const isNegative = change !== null && change < 0
              
              return (
                <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {metric.metric}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">
                    {formatMetricValue(metric.current_period)}
                  </td>
                  {hasComparatives && (
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-600">
                      {formatMetricValue(metric.prior_period)}
                    </td>
                  )}
                  {hasComparatives && (
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                      {change !== null && percent !== null ? (
                        <div
                          className={`inline-flex items-center space-x-1 ${
                            isPositive ? 'text-green-600' : isNegative ? 'text-red-600' : 'text-gray-600'
                          }`}
                        >
                          {isPositive ? (
                            <TrendingUp className="h-4 w-4" />
                          ) : isNegative ? (
                            <TrendingDown className="h-4 w-4" />
                          ) : (
                            <Minus className="h-4 w-4" />
                          )}
                          <span className="font-medium">
                            {fmtPercent(percent, { digits: 1, signed: true })}
                          </span>
                        </div>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                  )}
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {metric.commentary || '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {notes && (
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
          <p className="text-sm text-gray-600">{notes}</p>
        </div>
      )}
    </div>
  )
}

