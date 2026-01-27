'use client'

import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts'

interface SparklineProps {
  data: Array<{ label: string; value: number }>
  unit?: 'USD' | 'PCT' | 'EPS'
}

const areaColor = '#1f2937'

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
            cursor={{ stroke: '#1f2937', strokeWidth: 1, strokeDasharray: '3 3' }}
            contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb', boxShadow: '0 4px 12px rgba(15,23,42,0.08)' }}
            formatter={(value) => fmtValue(Number(value), unit)}
            labelStyle={{ color: '#111827', fontWeight: 500 }}
          />
          <Area type="monotone" dataKey="value" stroke={areaColor} strokeWidth={2} fill="url(#sparklineFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export default Sparkline
