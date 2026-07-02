'use client'

import { useContext } from 'react'
import { ArrowDownRightIcon, ArrowUpRightIcon, MinusIcon } from '@/lib/icons'
import { useCountUp } from '../hooks/useCountUp'
import { directionOf, directionChip } from '../lib/financialTone'
import { ThemeContext } from './ThemeProvider'
import { TrendSparkline, SkeletonStat } from './ui'

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

  // useCountUp v2 interpolates 0 → value over --duration-slow and returns the
  // formatted string (reduced motion / SSR render the final value instantly).
  const displayValue = useCountUp(hasValidValue ? value : 0, {
    format: (v) => formatValue(v, unit),
  })
  // TrendSparkline colours are SVG props — read theme off the context (not useTheme)
  // so provider-less renders never throw.
  const dark = useContext(ThemeContext)?.theme === 'dark'

  if (isLoading) {
    return <StatCard.Skeleton />
  }

  // Calm directional tone (mint up / muted slate down) — never a casino red/green delta.
  const dir = hasValidChange ? directionOf(change) : 'flat'
  const ChangeIcon = dir === 'up' ? ArrowUpRightIcon : dir === 'down' ? ArrowDownRightIcon : MinusIcon

  return (
    <div className="relative overflow-hidden rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark p-5 shadow-e2 dark:shadow-none">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-text-tertiary-light dark:text-text-secondary-dark">{label}</p>
          <div className="flex items-baseline gap-2">
            <h3 className="tabular text-2xl font-semibold tracking-tight text-text-primary-light dark:text-text-primary-dark">
              {hasValidValue ? displayValue : 'N/A'}
            </h3>
          </div>
        </div>

        {/* Sparkline */}
        {(trendData?.length ?? 0) > 1 && (
          <TrendSparkline
            data={trendData as number[]}
            dir={dir}
            dark={dark}
            width={96}
            height={40}
            className="opacity-70"
            label={`${label} trend`}
          />
        )}
      </div>

      {/* Only show comparison if we have valid data */}
      {hasValidValue ? (
        <div className="mt-3 flex items-center gap-2">
          <div className={`
            flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium
            ${directionChip[dir]}
          `}>
            <ChangeIcon className="h-3 w-3" />
            <span>{hasValidChange ? `${Math.abs(change).toFixed(1)}%` : 'N/A'}</span>
          </div>
          <span className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">vs prior period</span>
        </div>
      ) : (
        <div className="mt-3">
          <span className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">Data not available</span>
        </div>
      )}
    </div>
  )
}

StatCard.Skeleton = function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark p-5 shadow-e2 dark:shadow-none">
      <SkeletonStat />
    </div>
  )
}
