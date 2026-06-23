'use client'

import { useContext } from 'react'
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ThemeContext } from '@/components/ThemeProvider'

interface SparklineProps {
  data: Array<{ label: string; value: number }>
  unit?: 'USD' | 'PCT' | 'EPS'
}

// Series colour from the design-system chart palette (chart.1, teal).
const areaColor = '#3E8E84'

const fmtValue = (value: number, unit: 'USD' | 'PCT' | 'EPS') => {
  if (unit === 'USD') {
    const abs = Math.abs(value)
    if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
    if (abs >= 1e6) return `$${(value / 1e6).toFixed(2)}M`
    return `$${value.toFixed(0)}`
  }
  if (unit === 'PCT') {
    return `${(value * 100).toFixed(1)}%`
  }
  return value.toFixed(2)
}

export const Sparkline = ({ data, unit = 'USD' }: SparklineProps) => {
  // Recharts colours are props, not classes. Read theme off the context (not useTheme) with a
  // light fallback so provider-less renders/SSR/tests never throw.
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const cursorStroke = dark ? '#9CA3AF' : '#6B7280'
  const tooltipBg = dark ? '#1F2937' : '#FBFAF6'
  const tooltipBorder = dark ? 'rgba(255,255,255,0.1)' : '#E5E7EB'
  const tooltipText = dark ? '#D7DADC' : '#1A1A17'

  if (!data || data.length === 0) return null
  return (
    <div className="h-24 w-full">
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, bottom: 0, left: 0, right: 0 }}>
          <defs>
            <linearGradient id="sparklineFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={areaColor} stopOpacity={0.16} />
              <stop offset="95%" stopColor={areaColor} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Tooltip
            cursor={{ stroke: cursorStroke, strokeWidth: 1, strokeDasharray: '3 3' }}
            contentStyle={{ borderRadius: 8, border: `1px solid ${tooltipBorder}`, backgroundColor: tooltipBg, color: tooltipText, boxShadow: '0 4px 12px rgba(15,23,42,0.08)' }}
            itemStyle={{ color: tooltipText }}
            formatter={(value) => typeof value === 'number' ? fmtValue(value, unit) : ''}
            labelStyle={{ color: tooltipText, fontWeight: 500 }}
          />
          <Area type="monotone" dataKey="value" stroke={areaColor} strokeWidth={2} fill="url(#sparklineFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export default Sparkline
