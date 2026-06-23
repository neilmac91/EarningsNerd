'use client'

import { useContext } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
 CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { ThemeContext } from '@/components/ThemeProvider'

interface DataPoint {
  label: string
  value: number
}

interface ComparisonMetricChartProps {
  data: Array<{ label: string; value: number | null }>
  color?: string
}

export default function ComparisonMetricChart({
  data,
  color = '#2563eb',
}: ComparisonMetricChartProps) {
  // Recharts colours are props, not classes. Read theme off the context (not useTheme) with a
  // light fallback so provider-less renders/SSR/tests never throw.
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const axisText = dark ? '#9CA3AF' : '#6B7280'
  const gridStroke = dark ? '#374151' : '#E5E7EB'
  const tooltipBg = dark ? '#1F2937' : '#FBFAF6'
  const tooltipBorder = dark ? 'rgba(255,255,255,0.1)' : '#E5E7EB'
  const tooltipText = dark ? '#D7DADC' : '#1A1A17'

  const cleaned: DataPoint[] = data
    .filter((point): point is { label: string; value: number } => point.value !== null)
    .map((point) => ({
      label: point.label,
      value: point.value as number,
    }))

  if (cleaned.length < 2) {
    return null
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={cleaned} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12, fill: axisText }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: axisText }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip
          contentStyle={{ borderRadius: 8, border: `1px solid ${tooltipBorder}`, backgroundColor: tooltipBg, color: tooltipText }}
          labelStyle={{ color: tooltipText }}
          itemStyle={{ color: tooltipText }}
          formatter={(value) => typeof value === 'number' ? value.toLocaleString() : ''}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={{ r: 3, strokeWidth: 1, fill: color }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

