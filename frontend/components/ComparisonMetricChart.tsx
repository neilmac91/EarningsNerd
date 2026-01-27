'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
 CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

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
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12, fill: '#6b7280' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: '#6b7280' }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip
          contentStyle={{ borderRadius: 8, borderColor: '#e5e7eb' }}
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

