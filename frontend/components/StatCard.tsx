'use client'

import { ArrowDownRight, ArrowUpRight, Minus, TrendingUp } from 'lucide-react'
import { ResponsiveContainer, AreaChart, Area } from 'recharts'
import { useCountUp } from '../hooks/useCountUp'
import { ShimmeringLoader } from './ShimmeringLoader'

interface StatCardProps {
  label: string
  value: number
  unit?: 'currency' | 'percent' | 'number'
  change?: number
  trendData?: number[] // For Sparkline
  isLoading?: boolean
}

const formatValue = (value: number, unit: StatCardProps['unit']) => {
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
  const displayValue = useCountUp(value, 1000)

  if (isLoading) {
    return <StatCard.Skeleton />
  }

  const isPositive = change && change > 0
  const isNegative = change && change < 0
  const isNeutral = !change || change === 0
  
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
  const showPulse = isPositive && change > 10

  const sparklineData = trendData?.map((val, i) => ({ i, val })) || []

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-200 hover:shadow-md">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p>
          <div className="flex items-baseline gap-2">
             <h3 className="text-2xl font-semibold tracking-tight text-slate-900 font-mono tabular-nums">
              {formatValue(displayValue, unit)}
            </h3>
          </div>
        </div>
        
        {/* Sparkline */}
        {sparklineData.length > 1 && (
          <div className="h-10 w-24 opacity-50">
             <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparklineData}>
                <Area 
                  type="monotone" 
                  dataKey="val" 
                  stroke={isNegative ? '#e11d48' : '#059669'} 
                  fill={isNegative ? '#ffe4e6' : '#d1fae5'} 
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

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
          <span>{change ? Math.abs(change).toFixed(1) : '0.0'}%</span>
        </div>
        <span className="text-xs text-slate-400">vs prior period</span>
      </div>
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
