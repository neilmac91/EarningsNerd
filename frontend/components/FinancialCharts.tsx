'use client'

import { useContext } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { fmtCurrency, parseNumeric } from '@/lib/format'
import { StatCard } from './StatCard'
import { ThemeContext } from './ThemeProvider'

interface FinancialChartsProps {
  metrics?: Array<{
    metric: string
    current_period: string
    prior_period: string
    commentary?: string
  }>
}

export default function FinancialCharts({ metrics }: FinancialChartsProps) {
  // Recharts colours are props, not classes, so theme them off the resolved theme. Read the context
  // directly (not useTheme) with a light fallback so bare renders/SSR/tests never throw.
  const isDark = useContext(ThemeContext)?.theme === 'dark'
  const chart = isDark
    ? { grid: '#334155', tick: '#94a3b8', cursor: 'rgba(148,163,184,0.12)', tipBg: '#1e293b', tipBorder: '#334155', tipText: '#e2e8f0' }
    : { grid: '#f1f5f9', tick: '#64748b', cursor: '#f8fafc', tipBg: '#ffffff', tipBorder: '#e2e8f0', tipText: '#0f172a' }

  if (!metrics || metrics.length === 0) {
    return null
  }

  // 1. Process Metrics for StatCards
  // We look for specific keys to promote to the top
  const keyMetrics = metrics.filter(m => {
    const name = m.metric.toLowerCase()
    return (
      name.includes('revenue') || 
      name.includes('income') || 
      name.includes('earnings') || 
      name.includes('eps') ||
      name.includes('cash flow')
    )
  }).slice(0, 4) // Limit to top 4 cards

  const statCardsData = keyMetrics.map(m => {
    const current = parseNumeric(m.current_period) || 0
    const prior = parseNumeric(m.prior_period) || 0
    const change = prior !== 0 ? ((current - prior) / Math.abs(prior)) * 100 : undefined
    
    // Determine unit
    const name = m.metric.toLowerCase()
    let unit: 'currency' | 'percent' | 'number' = 'number'
    if (name.includes('margin') || name.includes('rate') || name.includes('return')) {
      unit = 'percent'
    } else if (name.includes('revenue') || name.includes('income') || name.includes('cash') || name.includes('eps')) {
      unit = 'currency'
    }

    return {
      label: m.metric,
      value: current,
      unit,
      change,
      trendData: [prior, current]
    }
  })

  // 2. Bar Chart Data (Comparison)
  // Used for the secondary view
  const barChartData = metrics
    .slice(0, 6)
    .map(m => {
      const current = parseNumeric(m.current_period)
      const prior = parseNumeric(m.prior_period)
      return {
        name: m.metric.length > 20 ? m.metric.substring(0, 20) + '...' : m.metric,
        current: current ?? 0,
        prior: prior ?? undefined,
      }
    })

  const hasComparatives = metrics.some((metric) => parseNumeric(metric.prior_period) !== null)
  const showPriorSeries = hasComparatives && barChartData.some(item => typeof item.prior === 'number')

  return (
    <div className="space-y-8">
      {/* 1. The "At-a-Glance" Grid */}
      {statCardsData.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {statCardsData.map((stat) => (
            <StatCard 
              key={stat.label}
              label={stat.label}
              value={stat.value}
              unit={stat.unit}
              change={stat.change}
              trendData={stat.trendData}
            />
          ))}
        </div>
      )}

      {/* 2. Detailed Comparison Chart */}
      {barChartData.length > 0 && (
        <div className="rounded-xl border border-border-light bg-panel-light p-6 shadow-sm dark:border-border-dark dark:bg-panel-dark">
          <div className="mb-6 flex items-center justify-between">
            <h3 className="text-lg font-semibold tracking-tight text-text-primary-light dark:text-text-primary-dark">
              Metric Comparison
            </h3>
            <span className="text-xs font-medium text-text-tertiary-light uppercase tracking-wider dark:text-text-tertiary-dark">
              Current vs Prior
            </span>
          </div>
          
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barChartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: chart.tick }}
                  dy={10}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 11, fill: chart.tick }}
                  tickFormatter={(value) => {
                    if (value >= 1_000_000_000) return `$${(value / 1e9).toFixed(1)}B`
                    if (value >= 1_000_000) return `$${(value / 1e6).toFixed(0)}M`
                    return `${value}`
                  }}
                />
                <Tooltip
                  cursor={{ fill: chart.cursor }}
                  contentStyle={{
                    borderRadius: '8px',
                    border: `1px solid ${chart.tipBorder}`,
                    backgroundColor: chart.tipBg,
                    color: chart.tipText,
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                  }}
                  labelStyle={{ color: chart.tipText }}
                  itemStyle={{ color: chart.tipText }}
                  formatter={(value) => [
                    fmtCurrency(value as number, { digits: 2, compact: true }),
                    ''
                  ]}
                />
                <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
                <Bar 
                  dataKey="current" 
                  name="Current Period" 
                  fill="#10b981" // emerald-500
                  radius={[4, 4, 0, 0]} 
                  barSize={32}
                />
                {showPriorSeries && (
                  <Bar 
                    dataKey="prior" 
                    name="Prior Period" 
                    fill="#94a3b8" // slate-400
                    radius={[4, 4, 0, 0]} 
                    barSize={32}
                  />
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
