'use client'

import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
// import CountUp from 'react-countup' // AIGENT_NOTE: Could not install react-countup automatically. Add this back after manual installation.
import { ShimmeringLoader } from './ShimmeringLoader'

interface StatCardProps {
  label: string
  value: number
  unit?: 'currency' | 'percent' | 'none'
  change?: number
  isLoading?: boolean
}

const formatValue = (value: number, unit: StatCardProps['unit']) => {
  switch (unit) {
    case 'currency':
      return `$${(value / 1_000_000_000).toFixed(2)}B`
    case 'percent':
      return `${value.toFixed(2)}%`
    default:
      return value.toString()
  }
}

export function StatCard({ label, value, unit = 'none', change, isLoading }: StatCardProps) {
  if (isLoading) {
    return <StatCard.Skeleton />
  }

  const ChangeIcon = !change || change === 0 ? Minus : change > 0 ? ArrowUpRight : ArrowDownRight
  const changeColor = !change || change === 0 ? 'text-text-tertiary-light dark:text-text-tertiary-dark' : change > 0 ? 'text-mint-600 dark:text-mint-500' : 'text-red-600 dark:text-red-500'

  return (
    <div className="rounded-lg border border-border-light bg-panel-light p-4 dark:border-border-dark dark:bg-panel-dark">
      <p className="mb-1 text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark">{label}</p>
      <div className="flex items-baseline gap-2">
        <h3 className="text-3xl font-bold text-text-primary-light dark:text-text-primary-dark">
          {/* <CountUp end={value} formattingFn={(val) => formatValue(val, unit)} duration={1} /> */}
          {formatValue(value, unit)}
        </h3>
        {change !== undefined && (
          <div className={`flex items-center text-sm font-semibold ${changeColor}`}>
            <ChangeIcon className="h-4 w-4" />
            <span>{Math.abs(change).toFixed(2)}%</span>
          </div>
        )}
      </div>
    </div>
  )
}

StatCard.Skeleton = function StatCardSkeleton() {
  return (
    <div className="rounded-lg border border-border-light bg-panel-light p-4 dark:border-border-dark dark:bg-panel-dark">
      <ShimmeringLoader className="mb-2 h-5 w-2/3" />
      <div className="flex items-baseline gap-2">
        <ShimmeringLoader className="h-8 w-1/3" />
        <ShimmeringLoader className="h-5 w-1/4" />
      </div>
    </div>
  )
}
