'use client'

import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import dynamic from 'next/dynamic'
import { useCountUp } from '../hooks/useCountUp'

const StatCardSparkline = dynamic(
  () => import('./charts/StatCardSparkline'),
  { ssr: false }
)
import { ShimmeringLoader } from './ShimmeringLoader'

interface StatCardProps {
  label: string
  value: number | null | undefined
  unit?: 'currency' | 'percent' | 'number'
  change?: number | null
  trendData?: number[] // For Sparkline
  isLoading?: boolean
}

const formatValue = (value: number | null | undefined, unit: StatCardProps['unit']): string => {
  // Handle null/undefined/NaN - show "N/A" instead of $0.00M
  // Using != null to check both null and undefined (loose equality)
  if (value == null || !Number.isFinite(value)) {
    return 'N/A'
  }

  // Handle actual zero differently from missing data
  // Zero is a valid financial value (e.g., zero net income)
  switch (unit) {
    case 'currency':
      // Check for billions vs millions
      if (Math.abs(value) >= 1_000_000_000) {
        return `$${(value / 1_000_000_000).toFixed(2)}B`
      }
      return `$${(value / 1_000_000).toFixed(2)}M`
    case 'percent':
      return `${value.toFixed(2)}%`
    default:
      return value.toLocaleString()
  }
}

export function StatCard({ label, value, unit = 'number', change, trendData, isLoading }: StatCardProps) {
  // Check for valid numeric values (!= null catches both null and undefined)
  const hasValidValue = value != null && Number.isFinite(value)
  const hasValidChange = change != null && Number.isFinite(change)

  // useCountUp expects a number - use 0 for animation when no valid value
  const displayValue = useCountUp(hasValidValue ? value : 0, 1000)

  if (isLoading) {
    return <StatCard.Skeleton />
  }

  // Only show positive/negative indicators if we have valid data
  const isPositive = hasValidChange && change > 0
  const isNegative = hasValidChange && change < 0

  // Bloomberg-Lite Colors
  const deltaColors = {
    positive: 'text-emerald-600 bg-emerald-50 border-emerald-100',
    negative: 'text-rose-600 bg-rose-50 border-rose-100',
    neutral: 'text-slate-500 bg-slate-50 border-slate-100'
  }

  const currentDeltaColor = isPositive
    ? deltaColors.positive
    : isNegative
      ? deltaColors.negative
      : deltaColors.neutral

  const ChangeIcon = isPositive ? ArrowUpRight : isNegative ? ArrowDownRight : Minus

  // Pulse effect for significant gains (>10%)
  const showPulse = isPositive && hasValidChange && change > 10

  const sparklineData = trendData?.map((val, i) => ({ i, val })) || []

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-200 hover:shadow-md">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-2xl font-semibold tracking-tight text-slate-900 font-mono tabular-nums">
              {hasValidValue ? formatValue(displayValue, unit) : 'N/A'}
            </h3>
          </div>
        </div>

        {/* Sparkline */}
        {sparklineData.length > 1 && (
          <div className="h-10 w-24 opacity-50">
            <StatCardSparkline data={sparklineData} isNegative={!!isNegative} />
          </div>
        )}
      </div>

      {/* Only show comparison if we have valid data */}
      {hasValidValue ? (
        <div className="mt-3 flex items-center gap-2">
          <div className={`
            flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium
            ${currentDeltaColor}
            ${showPulse ? 'relative' : ''}
          `}>
            {showPulse && (
              <span className="absolute -right-1 -top-1 flex h-3 w-3">
                <span className="animate-radar-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500"></span>
              </span>
            )}
            <ChangeIcon className="h-3 w-3" />
            <span>{hasValidChange ? `${Math.abs(change).toFixed(1)}%` : 'N/A'}</span>
          </div>
          <span className="text-xs text-slate-400">vs prior period</span>
        </div>
      ) : (
        <div className="mt-3">
          <span className="text-xs text-slate-400">Data not available</span>
        </div>
      )}
    </div>
  )
}

StatCard.Skeleton = function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <ShimmeringLoader className="mb-2 h-4 w-1/3" />
      <ShimmeringLoader className="h-8 w-2/3 mb-4" />
      <div className="flex gap-2">
        <ShimmeringLoader className="h-5 w-16 rounded-full" />
        <ShimmeringLoader className="h-5 w-24" />
      </div>
    </div>
  )
}
