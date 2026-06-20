'use client'

import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { FundamentalSeries, FundamentalsData, FundamentalPoint } from '@/features/companies/api/companies-api'
import { fmtCurrency } from '@/lib/format'

// Human labels + canonical display order for the concepts the backend emits.
const CONCEPT_LABELS: Record<string, string> = {
  revenue: 'Revenue',
  net_income: 'Net Income',
  gross_profit: 'Gross Profit',
  operating_income: 'Operating Income',
  free_cash_flow: 'Free Cash Flow',
  operating_cash_flow: 'Operating Cash Flow',
  capital_expenditures: 'CapEx',
  total_assets: 'Total Assets',
  cash_and_equivalents: 'Cash & Equiv.',
  shareholders_equity: 'Shareholders’ Equity',
  long_term_debt: 'Long-Term Debt',
  earnings_per_share: 'EPS (Basic)',
  eps_diluted: 'EPS (Diluted)',
  net_margin: 'Net Margin',
  gross_margin: 'Gross Margin',
  operating_margin: 'Operating Margin',
}
const CONCEPT_ORDER = Object.keys(CONCEPT_LABELS)

function conceptLabel(concept: string): string {
  return CONCEPT_LABELS[concept] ?? concept.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

// Values are unit-typed: USD → compact $, USD/shares → $x.xx, pure → already percentage points.
function formatValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (unit === 'pure') return `${value.toFixed(1)}%`
  if (unit === 'USD/shares') return fmtCurrency(value, { digits: 2, compact: false })
  return fmtCurrency(value, { digits: 1, compact: true })
}

// Compact Y-axis ticks: $391B, $6, 24%.
function formatTick(value: number, unit: string): string {
  if (unit === 'pure') return `${Math.round(value)}%`
  if (unit === 'USD/shares') return fmtCurrency(value, { digits: 0, compact: false })
  return fmtCurrency(value, { digits: 0, compact: true })
}

function periodLabel(p: Pick<FundamentalPoint, 'fiscal_year' | 'fiscal_period' | 'period_end'>): string {
  if (p.fiscal_period === 'FY' && p.fiscal_year) return `FY${p.fiscal_year}`
  if (p.fiscal_period && p.fiscal_year) return `${p.fiscal_period} ${p.fiscal_year}`
  return p.period_end // 10-Q with unknown quarter → fall back to the period-end date
}

interface Props {
  data: FundamentalsData
}

/**
 * Multi-year fundamentals chart. One concept at a time (pick via the metric pills), values shown
 * exactly as reported in SEC filings. Renders nothing when there are no facts yet, so it stays
 * invisible until the backfill has populated this company.
 */
export default function FundamentalsChart({ data }: Props) {
  const concepts = useMemo(() => {
    const withPoints = data.concepts.filter((c) => c.points.length > 0)
    return [...withPoints].sort((a, b) => {
      const ia = CONCEPT_ORDER.indexOf(a.concept)
      const ib = CONCEPT_ORDER.indexOf(b.concept)
      return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib)
    })
  }, [data.concepts])

  const [selected, setSelected] = useState<string>(
    () => (concepts.find((c) => c.concept === 'revenue') ?? concepts[0])?.concept ?? '',
  )

  if (concepts.length === 0) return null

  const active: FundamentalSeries = concepts.find((c) => c.concept === selected) ?? concepts[0]
  const chartData = active.points.map((p) => ({ label: periodLabel(p), value: p.value }))
  const latest = active.points[active.points.length - 1]

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">Fundamentals</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            As reported in SEC filings · {active.points.length} period{active.points.length === 1 ? '' : 's'}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Select metric">
          {concepts.map((c) => {
            const isActive = c.concept === active.concept
            return (
              <button
                key={c.concept}
                type="button"
                aria-pressed={isActive}
                onClick={() => setSelected(c.concept)}
                className={
                  isActive
                    ? 'rounded-full bg-emerald-600 px-3 py-1 text-xs font-medium text-white'
                    : 'rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                }
              >
                {conceptLabel(c.concept)}
              </button>
            )
          })}
        </div>
      </div>

      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} dy={8} />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: '#64748b' }}
              width={56}
              tickFormatter={(v) => formatTick(v as number, active.unit)}
            />
            <Tooltip
              cursor={{ fill: '#f8fafc' }}
              contentStyle={{
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
              }}
              formatter={(v) => [formatValue(v as number, active.unit), conceptLabel(active.concept)]}
            />
            <Bar dataKey="value" name={conceptLabel(active.concept)} fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={56} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {latest && (
        <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
          Latest: {formatValue(latest.value, active.unit)} ({periodLabel(latest)}
          {latest.form ? `, ${latest.form}` : ''}). Figures are as-reported and may be partial until all
          filings are processed.
        </p>
      )}
    </section>
  )
}
