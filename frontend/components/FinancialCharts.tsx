'use client'

import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { fmtCurrency, fmtPercent, parseNumeric } from '@/lib/format'

interface FinancialChartsProps {
  metrics?: Array<{
    metric: string
    current_period: string
    prior_period: string
    commentary?: string
  }>
}

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444']

export default function FinancialCharts({ metrics }: FinancialChartsProps) {
  if (!metrics || metrics.length === 0) {
    return null
  }

  const hasComparatives = metrics.some((metric) => parseNumeric(metric.prior_period) !== null)

  // Extract revenue, EPS, and cash flow data for line charts
  const timeSeriesData = metrics
    .filter(m => {
      const metric = m.metric.toLowerCase()
      return metric.includes('revenue') || metric.includes('eps') || metric.includes('cash flow')
    })
    .map(m => {
      const current = parseNumeric(m.current_period)
      const prior = parseNumeric(m.prior_period)
      return {
        metric: m.metric,
        current: current,
        prior: prior,
        change: current && prior ? ((current - prior) / Math.abs(prior)) * 100 : null,
      }
    })
    .filter(m => m.current !== null)

  // Bar chart data for key metrics
  const barChartData = metrics
    .slice(0, 6) // Top 6 metrics
    .map(m => {
      const current = parseNumeric(m.current_period)
      const prior = parseNumeric(m.prior_period)
      return {
        name: m.metric.length > 20 ? m.metric.substring(0, 20) + '...' : m.metric,
        current: current ?? 0,
        prior: prior ?? undefined,
      }
    })

  const showPriorSeries = hasComparatives && barChartData.some(item => typeof item.prior === 'number')

  if (timeSeriesData.length === 0 && barChartData.length === 0) {
    return null
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics Comparison Bar Chart */}
      {barChartData.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Key Financial Metrics Comparison</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="name" 
                angle={-45}
                textAnchor="end"
                height={100}
                tick={{ fontSize: 12 }}
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number) => {
                  if (typeof value === 'number') {
                    return fmtCurrency(value, { digits: 2 })
                  }
                  return value
                }}
              />
              <Legend />
              <Bar dataKey="current" fill="#3b82f6" name="Current Period" />
              {showPriorSeries && (
                <Bar dataKey="prior" fill="#94a3b8" name="Prior Period" data-testid="prior-series" />
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Revenue/EPS/Cash Flow Trends */}
      {timeSeriesData.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Financial Trends</h3>
          <div className="grid md:grid-cols-2 gap-6">
            {timeSeriesData.map((item, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-700 mb-3">{item.metric}</h4>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart
                    data={[
                      ...(showPriorSeries && item.prior !== null
                        ? [{ period: 'Prior', value: item.prior }]
                        : []),
                      ...(item.current !== null ? [{ period: 'Current', value: item.current }] : []),
                    ]}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" />
                    <YAxis />
                    <Tooltip
                      formatter={(value: number) => {
                        if (typeof value === 'number') {
                          return fmtCurrency(value, { digits: 2 })
                        }
                        return value
                      }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="value" 
                      stroke="#3b82f6" 
                      strokeWidth={2}
                      dot={{ fill: '#3b82f6', r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
                {item.change !== null && (
                  <div
                    className={`mt-2 text-sm font-medium ${
                      item.change > 0 ? 'text-green-600' : item.change < 0 ? 'text-red-600' : 'text-gray-600'
                    }`}
                  >
                    {fmtPercent(item.change, { digits: 1, signed: true })} change
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

