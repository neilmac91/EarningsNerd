'use client'

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtUSD } from '@/lib/guards'

interface DeltaBarProps {
  label: string
  current?: number
  prior?: number
  unit?: 'USD' | 'PCT' | 'EPS'
}

const palette = {
  current: '#1f2937',
  prior: '#9ca3af',
}

const formatValue = (value: number | undefined, unit: 'USD' | 'PCT' | 'EPS') => {
  if (value === undefined) return ''
  if (unit === 'USD') return fmtUSD(value)
  if (unit === 'PCT') return `${(value * 100).toFixed(1)}%`
  if (unit === 'EPS') return value.toFixed(2)
  return value.toString()
}

export const DeltaBar = ({ label, current, prior, unit = 'USD' }: DeltaBarProps) => {
  if (typeof current !== 'number' || typeof prior !== 'number') {
    return null
  }

  const data = [{ label, current, prior }]

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: 16 }}>
          <CartesianGrid stroke="#e5e7eb" vertical={false} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#6b7280', fontSize: 12 }} />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#6b7280', fontSize: 12 }}
            tickFormatter={(value) => formatValue(value as number, unit)}
          />
          <Tooltip
            cursor={{ fill: 'rgba(17, 24, 39, 0.04)' }}
            contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb', boxShadow: '0 4px 12px rgba(15,23,42,0.08)' }}
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
