'use client'

import { useContext } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtUSD } from '@/lib/guards'
import { ThemeContext } from '@/components/ThemeProvider'

interface DeltaBarProps {
  label: string
  current?: number
  prior?: number
  unit?: 'USD' | 'PCT' | 'EPS'
}

const formatValue = (value: number | undefined, unit: 'USD' | 'PCT' | 'EPS') => {
  if (value === undefined) return ''
  if (unit === 'USD') return fmtUSD(value)
  if (unit === 'PCT') return `${(value * 100).toFixed(1)}%`
  if (unit === 'EPS') return value.toFixed(2)
  return value.toString()
}

export const DeltaBar = ({ label, current, prior, unit = 'USD' }: DeltaBarProps) => {
  // Recharts colours are props, not classes. Read theme off the context (not useTheme) with a
  // light fallback so provider-less renders/SSR/tests never throw.
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const axisText = dark ? '#9CA3AF' : '#6B7280'
  const gridStroke = dark ? '#374151' : '#E5E7EB'
  const tooltipBg = dark ? '#1F2937' : '#FBFAF6'
  const tooltipBorder = dark ? 'rgba(255,255,255,0.1)' : '#E5E7EB'
  const tooltipText = dark ? '#D7DADC' : '#1A1A17'
  const cursorFill = dark ? 'rgba(148,163,184,0.12)' : 'rgba(17, 24, 39, 0.04)'
  const palette = {
    current: '#3E8E84', // chart.1 (teal)
    prior: dark ? '#475569' : '#94A3B8', // neutral, theme-aware
  }

  if (typeof current !== 'number' || typeof prior !== 'number') {
    return null
  }

  const data = [{ label, current, prior }]

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 16 }}>
          <CartesianGrid stroke={gridStroke} vertical={false} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: axisText, fontSize: 12 }} />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: axisText, fontSize: 12 }}
            tickFormatter={(value) => formatValue(value as number, unit)}
          />
          <Tooltip
            cursor={{ fill: cursorFill }}
            contentStyle={{ borderRadius: 8, border: `1px solid ${tooltipBorder}`, backgroundColor: tooltipBg, color: tooltipText, boxShadow: '0 4px 12px rgba(15,23,42,0.08)' }}
            labelStyle={{ color: tooltipText }}
            itemStyle={{ color: tooltipText }}
            formatter={(value) => typeof value === 'number' ? formatValue(value, unit) : ''}
          />
          <Bar dataKey="prior" fill={palette.prior} radius={[4, 4, 0, 0]} barSize={28} />
          <Bar dataKey="current" fill={palette.current} radius={[4, 4, 0, 0]} barSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default DeltaBar
