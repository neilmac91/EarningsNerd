'use client'

import { useState, useEffect } from 'react'
import { StatCard } from './StatCard'
import { ShimmeringLoader } from './ShimmeringLoader'

const FAKE_DATA = {
  company: {
    name: 'Apple Inc.',
    ticker: 'AAPL',
  },
  metrics: [
    { label: 'Total Revenue', value: 383_290_000_000, unit: 'currency' as const, change: -2.8 },
    { label: 'Net Income', value: 96_995_000_000, unit: 'currency' as const, change: -0.9 },
    { label: 'Gross Margin', value: 44.13, unit: 'percent' as const, change: 1.2 },
    { label: 'EPS (Diluted)', value: 6.13, unit: 'none' as const, change: 0.82 },
  ],
}

function ChartPlaceholder() {
  return (
    <div className="h-60 rounded-lg border border-border-light bg-panel-light p-4 dark:border-border-dark dark:bg-panel-dark">
      <div className="h-full w-full rounded-md bg-background-light dark:bg-background-dark flex items-center justify-center">
        <p className="text-sm text-text-tertiary-light dark:text-text-tertiary-dark">[ Chart Placeholder ]</p>
      </div>
    </div>
  )
}

ChartPlaceholder.Skeleton = function ChartPlaceholderSkeleton() {
  return <ShimmeringLoader className="h-60 w-full" />
}

export default function DashboardPreview() {
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsLoading(false)
    }, 1500) // Simulate a network request
    return () => clearTimeout(timer)
  }, [])

  if (isLoading) {
    return <DashboardPreview.Skeleton />
  }

  return (
    <div className="w-full max-w-7xl mx-auto">
      <div className="mb-6 flex items-baseline justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
            {FAKE_DATA.company.name} ({FAKE_DATA.company.ticker})
          </h2>
          <p className="text-base text-text-secondary-light dark:text-text-secondary-dark">
            Showing key metrics from the latest annual filing
          </p>
        </div>
        <a href="/company/AAPL" className="text-sm font-medium text-mint-600 hover:text-mint-500 dark:text-mint-400 dark:hover:text-mint-300">
          View Full Analysis &rarr;
        </a>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FAKE_DATA.metrics.map(metric => (
          <StatCard key={metric.label} {...metric} />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartPlaceholder />
        <ChartPlaceholder />
      </div>
    </div>
  )
}

DashboardPreview.Skeleton = function DashboardPreviewSkeleton() {
  return (
    <div className="w-full max-w-7xl mx-auto">
      <div className="mb-6 flex items-baseline justify-between">
        <div>
          <ShimmeringLoader className="h-8 w-64 mb-2" />
          <ShimmeringLoader className="h-5 w-80" />
        </div>
        <ShimmeringLoader className="h-5 w-32" />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard.Skeleton />
        <StatCard.Skeleton />
        <StatCard.Skeleton />
        <StatCard.Skeleton />
      </div>
      
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartPlaceholder.Skeleton />
        <ChartPlaceholder.Skeleton />
      </div>
    </div>
  )
}
