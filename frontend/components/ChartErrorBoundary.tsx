'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Card, cx } from '@/components/ui'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  /** What the boundary wraps, so the fallback names it truly: one chart, or a grid of charts. */
  noun?: 'chart' | 'charts'
  /** The default fallback card's place on the page, the margin the card it stands in for keeps (the company page's
   *  Sector peers panel). */
  className?: string
}

interface State {
  hasError: boolean
  error?: Error
}

export class ChartErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Chart rendering error:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      
      // Says only what failed. On the filing page the boundary wraps one chart with no table below
      // it; on Multi-Period Analysis it wraps the whole grid of trend charts (TrendCharts passes
      // noun="charts") and MetricsTable sits below, outside it; on the company page it wraps the
      // Sector peers panel and stands where the panel stood.
      return (
        <Card className={cx(this.props.className, 'p-cap-6 text-center')}>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {this.props.noun === 'charts' ? 'These charts could not be drawn.' : 'This chart could not be drawn.'}
          </p>
        </Card>
      )
    }

    return this.props.children
  }
}

